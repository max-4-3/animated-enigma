from bs4 import BeautifulSoup
from .converters import convert_views
import aiohttp
from http.cookies import SimpleCookie

async def extract_videos_from_webpage(sem, session: aiohttp.ClientSession, page_link: str, **kwargs):
    async with sem:
        async with session.get(page_link, **kwargs) as r:
            set_cookie_header = r.headers.getall('Set-Cookie', [])
            for cookie_str in set_cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_str)
                # Convert to a dict that aiohttp can understand
                cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                session.cookie_jar.update_cookies(cookies_dict, r.url)
            
            if r.cookies:
                session.cookie_jar.update_cookies(r.cookies)
            try:
                r.raise_for_status()
                page = await r.text()

                soup = BeautifulSoup(page, 'html.parser')
                list_items = soup.findAll('li', {'class': 'pcVideoListItem'})
                if not list_items:
                    raise ValueError('Error: Unable to find appropiate div element!\nMaybe wait a while before retrying?')
                
                videos = []
                for item in list_items:
                    video = {}
                    a = item.find('span', attrs={'class': 'title'}).find('a')
                    video['title'] = a.text.strip()
                    video['id'] = a.attrs.get('href').split('=')[-1]
                    video['viewkey'] = video['id']
                    video['url'] = f"https://www.pornhub.org{a.attrs.get('href')}"
                    video['path'] = a.attrs.get('href')
                    video['duration'] = item.find('var', attrs={'class': 'duration'}).text.strip()
                    video['views'] = convert_views(item.find('span', attrs={'class': 'views'}).find('var').text.strip())
                    videos.append(video)
                
                print(f'Extracted "{videos.__len__()}" videos!')
                videos = sorted(videos, key=lambda x: x.get('views'), reverse=True)

                return videos

            except Exception as e:
                print(f'Unable to get videos from page "{page_link}": {e}')
                return []