import aiohttp, re
from fake_useragent import UserAgent
from contextlib import asynccontextmanager

DOMAIN = "https://okxxx1.com"
link_pattern = re.compile(
    r"""^https?://(?:[a-z0-9-]+\.)*okxxx\d{1,1}\.(?:com|org).*/$"""
)


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
