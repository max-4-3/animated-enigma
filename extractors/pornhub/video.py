from bs4 import BeautifulSoup
import aiohttp, json, re
from ..converters import convert_views
from datetime import datetime
from . import DOMAIN, get_text_wrapper
from .page import extract_all_thumb_videos
from ..models import (
    ExternalLink,
    Recommendations,
    VideoLinks,
    Media,
    MediaItem,
    Metadata,
    Video,
    Thumbnail,
)
from http.cookies import SimpleCookie


def get_resolutions(flash_var: dict) -> dict:
    res = {}
    for media in flash_var["mediaDefinitions"]:
        if media.get("remote") is not None:
            continue
        res[int(media["quality"])] = {
            "format": media["format"],
            "url": media["videoUrl"],
        }
    return dict(sorted(res.items(), key=lambda x: x[0], reverse=True))


async def extract_video(
    sem,
    session: aiohttp.ClientSession,
    video_link: str,
    include_var: bool = False,
    **kwargs,
):
    async with sem:
        async with session.get(
            re.sub(r"https?://[^/]+", "", video_link), **kwargs
        ) as r:
            set_cookie_header = r.headers.getall("Set-Cookie", [])
            for cookie_str in set_cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_str)
                # Convert to a dict that aiohttp can understand
                cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                session.cookie_jar.update_cookies(cookies_dict, r.url)

            if r.cookies:
                session.cookie_jar.update_cookies(r.cookies)
            try:
                r.raise_for_status()
                page = await r.text()

                if not page:
                    raise ValueError("Empty Response!")

                soup = BeautifulSoup(page, "html.parser")
                flash_var_match = re.search(
                    r"""var (flashvars_\d*) = (?P<dict>{.*});\n""", page
                )
                if not flash_var_match:
                    raise ValueError("Unable to find flash vars")
                flash_var = json.loads(flash_var_match.group("dict"))

                # Extract metadata
                metadata = Metadata(
                    duration=flash_var.get("video_duration") or 0,
                    upload_date=datetime.fromtimestamp(
                        flash_var.get("playbackTracking", {}).get("video_timestamp")
                        or 0
                    ).strftime("%d/%m/%Y, %H:%M:%S"),
                    views=convert_views(
                        get_text_wrapper(
                            lambda: soup.select_one("div.views span.count").get_text(
                                strip=True
                            ),
                            default=0,
                        )
                    ),
                    extras={
                        "likes": get_text_wrapper(
                            lambda: soup.select_one("span.votesUp").get_text(
                                strip=True
                            ),
                            0,
                        )
                    },
                )

                # Tags, Categories, PornStars, Model Attribution, Production
                links = []
                for info_raw in soup.select(
                    "div.video-detailed-info div.video-info-row"
                ):
                    if not info_raw:
                        continue

                    if (
                        info_raw.select_one("div.userInfoBlock")
                        or (not info_raw.select_one("p"))
                        or (not info_raw.select("a"))
                    ):
                        continue

                    vidlinks = VideoLinks(
                        title=get_text_wrapper(
                            lambda: info_raw.select_one("p").get_text(strip=True),
                            "Unknowm Links Category",
                        ),
                        links=[],
                    )
                    for a in info_raw.select("a"):
                        try:
                            vidlinks.links.append(
                                ExternalLink(
                                    name=get_text_wrapper(
                                        lambda: a.get_text(strip=True), "Unknown Name"
                                    ),
                                    url="https://" + DOMAIN + a.attrs.get("href"),
                                )
                            )
                        except:
                            pass
                    links.append(vidlinks)

                # User Related Info
                userinfo = soup.select_one("div.userInfoBlock")
                if userinfo:
                    user = {
                        "avatar": userinfo.select_one("div.userAvatar img").attrs.get(
                            "src"
                        ),
                        "name": get_text_wrapper(
                            lambda: userinfo.select_one(
                                "div.userInfo span.usernameBadgesWrapper a"
                            ).get_text(strip=True),
                            "Unknown User",
                        ),
                        "url": "https://"
                        + DOMAIN
                        + userinfo.select_one(
                            "div.userInfo span.usernameBadgesWrapper a"
                        ).attrs.get("href", "/"),
                        "titles": [
                            i.attrs.get("data-title")
                            for i in userinfo.select(
                                "div.userInfo span.usernameBadgesWrapper i"
                            )
                        ],
                        "total_videos": get_text_wrapper(
                            lambda: userinfo.select(
                                "div.userInfo span:not(.line):not(.usernameBadgesWrapper)"
                            )[0].get_text(strip=True),
                            "N/A",
                        ),
                        "total_subs": get_text_wrapper(
                            lambda: userinfo.select(
                                "div.userInfo span:not(.line):not(.usernameBadgesWrapper)"
                            )[1].get_text(strip=True),
                            "N/A",
                        ),
                    }
                else:
                    user = {}

                # Recommendations
                relateds = []
                if kwargs.get("recommendations", True):
                    for recomends in soup.select('div[data-tab-content*="re"]'):
                        try:
                            r = Recommendations(
                                title=recomends.attrs.get(
                                    "data-tab-content", "N/A"
                                ).upper(),
                                contents=await extract_all_thumb_videos(recomends),
                            )
                            relateds.append(r)
                        except:
                            pass

                # Media
                media = Media(base_url="No BaseUrl For this!", items=[])
                for defination in flash_var.get("mediaDefinitions", [])[:-1]:
                    if defination.get("remote"):
                        continue
                    media.items.append(
                        MediaItem(
                            idx=len(media.items) + 1,
                            url=defination.get("videoUrl", None),
                            resolution=defination.get("quality") + "p",
                        )
                    )

                return Video(
                    title=flash_var.get("video_title")
                    or get_text_wrapper(
                        lambda: soup.select_one("title").get_text(strip=True),
                        "Unnamed Video!",
                    ),
                    url=video_link,
                    metadata=metadata,
                    thumbnail=Thumbnail(
                        url=soup.select_one('meta[property="og:image"]').attrs.get(
                            "content"
                        )
                    ),
                    media=media,
                    tags=[],
                    links=links,
                    recommendations=relateds,
                    extras={
                        "user": user,
                        "flash_vars": flash_var if include_var else None,
                    },
                )
            except Exception as e:
                print(f'Unable to ectract video from "{video_link}": {e}')
                raise e
