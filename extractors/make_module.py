import os
from rich import print

FILES = {
    "__init__.py": r"""
import aiohttp, re
from fake_useragent import UserAgent
from contextlib import asynccontextmanager

DOMAIN = "PLACEHOLDER"
link_pattern = re.compile(
    r"^https?://(?:[a-z0-9-]+\.)*{DOMAIN_NAME}\.(?:com|org).*" # This matches: https://123abc-1.DOMAIN_NAME.com/something
)

if DOMAIN == "PLACEHOLDER":
    raise NotImplementedError()

@asynccontextmanager
async def make_session():
    session = aiohttp.ClientSession(headers={"User-Agent": UserAgent().random})
    try:
        yield session
    finally:
        await session.close()


def is_valid_link(link: str) -> bool:
    return link_pattern.match(link)


def is_video_link(link: str) -> bool:
    return "video" in link and is_valid_link(link)


def is_page_link(link: str) -> bool:
    return is_valid_link(link)

    """,
    "video.py": """
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

    """,
    "page.py": """
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

    """
}
name = input("Enter the name for module: ").strip()
if not name:
    raise ValueError("Name is required")

root_path = os.path.join(os.getcwd(), name)
os.makedirs(root_path, exist_ok=True)

print("Generating files...")
for file, content in FILES.items():
    fp = os.path.join(root_path, file)
    with open(fp, "w", errors="ignore") as file:
        file.write(content)

print("File Generated!")
print("Edit your files in:", root_path)

