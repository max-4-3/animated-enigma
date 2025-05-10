from bs4 import BeautifulSoup, Tag
from rich import print
from http.cookies import SimpleCookie

from ..converters import convert_duration, convert_views
from ..models import ThumbVideo, Thumbnail, Metadata

import asyncio, aiohttp

def get_text(elem):
    try:
        return elem.text
    except:
        return "Field Not Found!"

async def parse_video_element(video_element: Tag) -> ThumbVideo | None:
    try:
        title = get_text(video_element.select_one('div.thumb-under p a'))
        url = "https://xnxx.health" + video_element.select_one('div.thumb-under p a').attrs.get('href', '')
        thumbnail = Thumbnail( url = video_element.select_one('div.thumb img').attrs.get('data-src'))

        right = video_element.select_one('span.right')
        views = get_text(right.contents[0]).strip()
        superfluous = get_text(right.select_one('span.superfluous')).strip()
        duration = get_text(video_element.select_one('p.metadata').contents[1]).strip()

        try:
            is_hd = int(get_text(video_element.select_one('span.video-hd').contents[1]).strip().replace("p", "")) >= 720
        except:
            is_hd = False
        
        return ThumbVideo(
            title=title,
            thumbnail=thumbnail,
            url = url,
            metadata = Metadata(
                views = convert_views(views),
                duration = convert_duration(duration),
                extras = {
                    "is_hd": is_hd,
                    "superfluous": superfluous
                }
            ),
            links = []
        )
    except Exception as e:
        print('Error While Getting info:', e)

async def get_videos_from_webpage(sem, session: aiohttp.ClientSession, page_url: str, **kwargs) -> list[ThumbVideo]:
    async with sem:
        try:
            async with session.get(page_url, **kwargs) as response:
                response.raise_for_status()
                set_cookie_header = response.headers.getall('Set-Cookie', [])
                for cookie_str in set_cookie_header:
                    cookie = SimpleCookie()
                    cookie.load(cookie_str)
                    # Convert to a dict that aiohttp can understand
                    cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                    session.cookie_jar.update_cookies(cookies_dict, response.url)
                
                if response.cookies:
                    session.cookie_jar.update_cookies(response.cookies)
                html = await response.text()

                soup = BeautifulSoup(html, 'html.parser')
                tasks = [asyncio.create_task(parse_video_element(video_div)) for video_div in soup.select('div[id^="video_"]') if video_div]
                return [data for data in await asyncio.gather(*tasks) if data]
        except Exception as e:
            print(f'[Parsing Error]:', e)

        return []

async def main():
    async with aiohttp.ClientSession() as session:
        data = await get_videos_from_webpage(asyncio.Semaphore(12), session, "https://xnxx.health/search/familial_relations?id=58418683")
        print(data)

if __name__ == "__main__":
    asyncio.run(main())
