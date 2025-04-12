import aiohttp
from bs4 import BeautifulSoup
import re, json
from urllib.parse import urljoin


async def get_resolutions(session, master_m3u8: str, **kw) -> dict[int, dict[str, str]]:
    try:
        async with session.get(master_m3u8, **kw) as r:
            r.raise_for_status()
            lines = (await r.text()).strip().splitlines()
    except Exception:
        return {}

    result = {}
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            try:
                props = dict(prop.split("=", 1) for prop in line.split(",") if "=" in prop)
                width, height = map(int, props["RESOLUTION"].split("x"))
                name = props.get("NAME", "").strip('"')
                media_url = media_url = "/".join(master_m3u8.split("/")[:-1]) + ("/" if not lines[i + 1].startswith("/") else "") + lines[i + 1]
                result[width * height] = {"name": name, "url": media_url}
            except Exception:
                continue

    return dict(sorted(result.items(), reverse=True))


def convert_var(vars: list[dict[str, str | int]]) -> list[dict]:
    new_data = []
    for var in vars:
        if not isinstance(var, dict):
            continue
        new_data.append({
            "id": var.get("id"),
            "title": var.get("t", "No Title"),
            "url": f"https://xnxx.health{var.get('u', '/')}",
            "thumbnail": var.get("ip") or var.get("if") or var.get("il") or var.get("i"),
            "duration": var.get("d", "00:00"),
            "rating": var.get("r", "0%"),
            "views": var.get("n", "0k"),
            "pornstar": {
                "title": var.get("pn") or var.get("p") or "No Title",
                "url": var.get("pu") or "https://xnxx.health/"
            },
            "is_hd": int(var.get("h", 0)) >= 1 or int(var.get("hp", 0)) >= 1
        })
    return new_data


async def extract_video_info(sem, session: aiohttp.ClientSession, video_url: str, recommendation: bool = True, **kwargs) -> dict:
    async with sem:
        try:
            async with session.get(video_url, **kwargs) as r:
                r.raise_for_status()
                text = await r.text()
        except Exception as e:
            print(f"[Fetch Error] {e}")
            return {}

        soup = BeautifulSoup(text, "html.parser")
        wrapper = soup.select_one("div.wrapper")
        if not wrapper:
            print("[Parse Error] Missing .wrapper")
            return {}

        # Fallback values
        result = {
            "title": "",
            "duration": "00:00",
            "views": 0,
            "rating": 0.0,
            "likes": 0,
            "dislikes": 0,
            "comments": 0,
            "tags": [],
            "is_hd": False,
            "media": {},
            "thumbnail": soup.select_one('meta[property*="og:image"]').get('content')
        }

        try:
            result["title"] = wrapper.select_one("h1").text.strip()

            metadata = wrapper.select_one("span.metadata").text.strip()
            parts = [part.strip() for part in metadata.split("-")]
            result["duration"] = parts[0]
            result["is_hd"] = int(parts[1].replace("p", "") or 0) >= 1080 if len(parts) > 1 else False
            result["views"] = int(parts[2].replace(",", "").replace(".", "")) if len(parts) > 2 else 0

            rating_el = wrapper.select_one('span[class*="rating-box value"]')
            if rating_el:
                result["rating"] = float(rating_el.text.strip().replace("%", ""))

            def get_int_value(selector):
                el = wrapper.select_one(selector)
                return int(el.text.strip().replace(",", "").replace(".", "")) if el else 0

            result["likes"] = get_int_value('a[class*="vote-action-good"] span.value')
            result["dislikes"] = get_int_value('a[class*="vote-action-bad"] span.value')
            result["comments"] = get_int_value('a[title*="Comments"] span.value')

            tag_els = wrapper.select('div[class*="video-tags"] a')
            result["tags"] = [
                {
                    "title": a.text.strip(),
                    "url": urljoin("https://xnxx.health", a.get("href", "/")),
                    "keyword": "is-keyword" in a.get("class", []),
                    "pornstar": "is-pornstar" in a.get("class", [])
                }
                for a in tag_els if a.get("href", "#") != "#"
            ]

            # media playlist
            bg_div = soup.select_one("div#video-player-bg")
            hls_match = re.search(r"""setVideoHLS\(['"](.+?)['"]\);""", bg_div.prettify() if bg_div else "")
            if hls_match:
                result["media"] = await get_resolutions(session, hls_match.group(1))
            else:
                print(f"[media Error] No hls match found in \"\n{bg_div.prettify()}\n\"")

            # recommendations
            if recommendation and bg_div:
                try:
                    related_match = re.search(r"""var\s+video_related\s*=\s*(\[.*?\]);""", bg_div.text)
                    if related_match:
                        data = json.loads(related_match.group(1))
                        result["recommendations"] = convert_var(data)
                except Exception as e:
                    print(f'[Recommendation Error] {e}')
        except Exception as e:
            print(f'[Parse Exception] {e}')

        return result
