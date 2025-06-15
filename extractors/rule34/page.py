
from bs4 import BeautifulSoup, Tag
from http.cookies import SimpleCookie
from . import DOMAIN
from ..converters import convert_views, convert_duration
from ..models import ThumbVideo, Metadata, ExternalLink, Thumbnail
import aiohttp

async def extract_thumb_info(thumb_list: list[Tag]) -> list[dict]:
    # Implement the logic for extracting info from a thumbnail 
    raise NotImplementedError()

async def extract_videos_from_page(
    sem, session: aiohttp.ClientSession, page_url: str, **request_kwargs
) -> list[ThumbVideo | None]:
    async with sem:
        async with session.get(page_url, **request_kwargs) as response:
            try:
                response.raise_for_status()

                set_cookie_header = response.headers.getall("Set-Cookie", [])
                for cookie_str in set_cookie_header:
                    cookie = SimpleCookie()
                    cookie.load(cookie_str)
                    # Convert to a dict that aiohttp can understand
                    cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                    session.cookie_jar.update_cookies(cookies_dict, response.url)

                if response.cookies:
                    session.cookie_jar.update_cookies(response.cookies)

                webpage = await response.text()
                thumbnail_selector = "" # Add CSS thumbnail selector
                
                soup = BeautifulSoup(webpage, 'html.parser')
                thumbnails = await asyncio.gather(*[asyncio.create_task(extract_thumb_info(thumb)) for thumb in soup.select(thumbnail_selector)])
                return [
                   ThumbVideo(...)  # Fill this thing
                   for thumb in thumbnails
                ]
            except Exception as e:
                print('Unable to extract videos from page "{}":'.format(page_url), e)
            return []

    
