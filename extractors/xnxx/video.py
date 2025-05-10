import aiohttp
from bs4 import BeautifulSoup
import re, json
from urllib.parse import urljoin
from http.cookies import SimpleCookie
from ..converters import convert_duration, convert_views
from ..models import Video, Media, MediaItem, Metadata, ExternalLink, ThumbVideo, Thumbnail, Recommendations


async def get_resolutions(session, master_m3u8: str, **kw) -> Media:
    try:
        async with session.get(master_m3u8, **kw) as r:
            r.raise_for_status()
            lines = (await r.text()).strip().splitlines()
    except Exception:
        return {}

    result = Media(
        base_url=master_m3u8,
        items = []
    )
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            try:
                props = dict(prop.split("=", 1) for prop in line.split(",") if "=" in prop)
                _, height = map(int, props["RESOLUTION"].split("x"))
                media_url = media_url = "/".join(master_m3u8.split("/")[:-1]) + ("/" if not lines[i + 1].startswith("/") else "") + lines[i + 1]
                result.items.append(
                    MediaItem(
                        idx=len(result.items) + 1,
                        url = media_url,
                        resolution = f"{height}p"
                    )
                )
            except Exception:
                continue

    return result


def convert_var(vars: list[dict[str, str | int]]) -> list[ThumbVideo]:
    new_data = []
    for var in vars:
        if not isinstance(var, dict):
            continue

        metadata = Metadata(
            views = convert_views(var.get("n", "0k")),
            duration = convert_duration(var.get('d', '00:00')),
            extras = {
                "rating": var.get("r"),
                "pornstar": {
                    "title": var.get("pn") or var.get("p") or "No Title",
                    "url": var.get("pu") or "https://xnxx.health/"
                },
                "is_hd": int(var.get("h", 0)) >= 1 or int(var.get("hp", 0)) >= 1
            }
        )

        new_data.append(
            ThumbVideo(
                title=var.get('t', 'no title'),
                thumbnail=Thumbnail(url=var.get("ip") or var.get("if") or var.get("il") or var.get("i")),
                url = f"https://xnxx.health{var.get('u', '/')}",
                metadata=metadata,
                links=[]
            )
        )
    return new_data


async def extract_video_info(sem, session: aiohttp.ClientSession, video_url: str, recommendation: bool = True, **kwargs) -> dict:
    async with sem:
        try:
            async with session.get(video_url, **kwargs) as r:
                r.raise_for_status()
                set_cookie_header = r.headers.getall('Set-Cookie', [])
                for cookie_str in set_cookie_header:
                    cookie = SimpleCookie()
                    cookie.load(cookie_str)
                    # Convert to a dict that aiohttp can understand
                    cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                    session.cookie_jar.update_cookies(cookies_dict, r.url)
                
                if r.cookies:
                    session.cookie_jar.update_cookies(r.cookies)
                text = await r.text()
        except Exception as e:
            print(f"[Fetch Error] {e}")
            return {}

        soup = BeautifulSoup(text, "html.parser")
        wrapper = soup.select_one("div.wrapper")
        if not wrapper:
            print("[Parse Error] Missing .wrapper")
            return 
        
        def wrap(expression, default = None):
            try:
                return expression()
            except:
                return default
        try:
            title = wrapper.select_one("h1").text.strip()

            metadata = wrapper.select_one("span.metadata").text.strip()
            parts = [part.strip() for part in metadata.split("-")]
            duration = wrap(lambda: convert_duration(parts[0]), 0)
            is_hd = wrap(lambda: int(parts[1].replace("p", "") or 0) >= 1080 if len(parts) > 1 else False, False)
            views = wrap(lambda: int(parts[2].replace(",", "").replace(".", "")) if len(parts) > 2 else 0, 0)

            rating_el = wrapper.select_one('span[class*="rating-box value"]')
            if rating_el:
                rating = float(rating_el.text.strip().replace("%", ""))

            def get_int_value(selector):
                el = wrapper.select_one(selector)
                return int(el.text.strip().replace(",", "").replace(".", "")) if el else 0

            likes = get_int_value('a[class*="vote-action-good"] span.value')
            dislikes = get_int_value('a[class*="vote-action-bad"] span.value')
            comments = get_int_value('a[title*="Comments"] span.value')

            tag_els = wrapper.select('div[class*="video-tags"] a')
            tags = [
                ExternalLink(
                    name = a.get_text(strip=True),
                    url = urljoin("https://xnxx.health", a.get('href', '/')),
                    extras = {
                        "kwyword": 'is-keyword' in a.get('class', []),
                        "pornstar": "is-pornstar" in a.get('class', [])
                    }
                )
                for a in tag_els if a.get('href', '#') != "#"
            ]

            # media playlist
            bg_div = soup.select_one("div#video-player-bg")
            hls_match = re.search(r"""setVideoHLS\(['"](.+?)['"]\);""", bg_div.prettify() if bg_div else "")
            media = Media(base_url="Nope", items = [])
            if hls_match:
                media = await get_resolutions(session, hls_match.group(1))
            else:
                print(f"[media Error] No hls match found in \"\n{bg_div.prettify()}\n\"")

            # recommendations
            recom = Recommendations()
            if recommendation and bg_div:
                try:
                    related_match = re.search(r"""var\s+video_related\s*=\s*(\[.*?\]);""", bg_div.text)
                    if related_match:
                        data = json.loads(related_match.group(1))
                        recom  = Recommendations(items = convert_var(data))
                except Exception as e:
                    print(f'[Recommendation Error] {e}')

            metadata = Metadata(
                views = views,
                duration = duration,
                extras = {
                    "is_hd": is_hd,
                    "rating": rating,
                    "likes": likes,
                    "dislikes": dislikes,
                    "comments": comments
                }
            )

            return Video(
                title = title,
                url = video_url,
                metadata = metadata,
                thumbnail = Thumbnail(url = soup.select_one('meta[property*="og:image"]').get('content')),
                media = media,
                tags = tags,
                links = [],
                recommendations = [recom]
            )
        except Exception as e:
            print(f'[Parse Exception] {e}')

        
