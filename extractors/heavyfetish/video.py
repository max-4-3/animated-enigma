from bs4 import BeautifulSoup
import aiohttp, re, json
from ..models import Video
from rich import print
from http.cookies import SimpleCookie


async def extract_video_info(sem, session: aiohttp.ClientSession, url: str, **kwargs):
    async with sem:
        async with session.get(url, **kwargs) as webpage:
            set_cookie_header = webpage.headers.getall("Set-Cookie", [])
            for cookie_str in set_cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_str)
                # Convert to a dict that aiohttp can understand
                cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                session.cookie_jar.update_cookies(cookies_dict, webpage.url)

            if webpage.cookies:
                session.cookie_jar.update_cookies(webpage.cookies)
            webpage.raise_for_status()

            text = await webpage.text()
            soup = BeautifulSoup(text, "html.parser")
            flashvars = re.search(r"flashvars\s*=\s*({[^;]*});", text)

            if not flashvars:
                raise ValueError("Unable to find flashvars")

            data = json.loads(flashvars.group(1))
            print(data)
