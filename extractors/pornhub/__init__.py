import aiohttp, re, ssl
from fake_useragent import UserAgent
from contextlib import asynccontextmanager

IP_ADDR = "66.254.114.41"
DOMAIN = "www.pornhub.org"
link_pattern = re.compile(r"""^https?://(?:[a-z0-9-]+\.)*pornhub\.(?:com|org)/.+$""")


@asynccontextmanager
async def make_session():
    headers = {"User-Agent": UserAgent().firefox, "Host": DOMAIN}
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    session = aiohttp.ClientSession(
        base_url=f"https://{IP_ADDR}",
        headers=headers,
        connector=aiohttp.TCPConnector(ssl=context),
    )
    try:
        yield session
    finally:
        await session.close()


def is_valid_link(link: str) -> bool:
    return link_pattern.match(link)


def is_video_link(link: str) -> bool:
    return "viewkey=" in link and is_valid_link(link)


def is_page_link(link: str) -> bool:
    return is_valid_link(link)


def get_text_wrapper(exp, default=None):
    try:
        return exp()
    except:
        return default
