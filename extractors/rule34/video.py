
from bs4 import BeautifulSoup, NavigableString
import re, aiohttp
from http.cookies import SimpleCookie
from ..converters import convert_duration
from ..models import (
    ExternalLink,
    Metadata,
    Media,
    MediaItem,
    Video,
    ThumbVideo,
    Thumbnail,
    VideoLinks,
    Recommendations,
)
from . import DOMAIN


async def extract_video_info(
    sem, session: aiohttp.ClientSession, video_url: str, with_recommendations: bool = True, **request_kwargs
) -> Video | None:
    async with sem:
        async with session.get(video_url, **request_kwargs) as response:
            try:
                response.raise_for_status()

                # Add cookies to the session
                set_cookie_header = response.headers.getall("Set-Cookie", [])
                for cookie_str in set_cookie_header:
                    cookie = SimpleCookie()
                    cookie.load(cookie_str)
                    # Convert to a dict that aiohttp can understand
                    cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                    session.cookie_jar.update_cookies(cookies_dict, response.url)

                if response.cookies:
                    session.cookie_jar.update_cookies(response.cookies)
                
                # Add the extraction logic here
                video = Video(...)

                # return the Video object
                return video
            except Exception as e:
                print(f"Unable to extract info from '{video_url}': {e}")
                return None

    
