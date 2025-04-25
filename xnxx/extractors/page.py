from bs4 import BeautifulSoup, Tag
from rich import print
import asyncio, aiohttp

def get_text(elem):
    try:
        return elem.text
    except:
        return "FiledNotFound!"

async def parse_video_element(video_element: Tag) -> dict | None:
    try:
        id = int(video_element.attrs.get('data-id') or 0)
        title = get_text(video_element.select_one('div.thumb-under p a'))
        url = "https://xnxx.health" + video_element.select_one('div.thumb-under p a').attrs.get('href', '')
        thumbnail = video_element.select_one('div.thumb img').attrs.get('data-src')

        right = video_element.select_one('span.right')
        views = get_text(right.contents[0]).strip()
        superfluous = get_text(right.select_one('span.superfluous')).strip()
        duration = get_text(video_element.select_one('p.metadata').contents[1]).strip()

        try:
            is_hd = int(get_text(video_element.select_one('span.video-hd').contents[1]).strip().replace("p", "")) >= 720
        except:
            is_hd = False
        
        return {
            'id': id,
            "title": title,
            "thumbnail": thumbnail,
            "duration": duration,
            "views": views,
            "superfluous": superfluous,
            "is_hd": is_hd,
            "url": url
        }
    except Exception as e:
        print('Error While Getting info:', e)

async def get_videos_from_webpage(sem, session: aiohttp.ClientSession, page_url: str, **kwargs) -> list[dict]:
    async with sem:
        try:
            async with session.get(page_url, **kwargs) as response:
                response.raise_for_status()
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
