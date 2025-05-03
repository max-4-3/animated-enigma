from bs4 import BeautifulSoup
from http.cookies import SimpleCookie
from .converters import convert_duration_to_seconds

async def extract_videos_from_webpage(sem, session, page_url: str):
    async with sem:
        async with session.get(page_url) as r:
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
                soup = BeautifulSoup(await r.text(), 'html.parser')

                video_list_element = soup.find('div', class_='list_video_wrapper')
                videos_list = []
                for thumb_video in video_list_element.select('div[class^="item thumb-bl thumb-bl-video"]'):
                    # Extract info from thumbnail
                    a_thumb_video = thumb_video.find('a')
                    img_thumb_video = thumb_video.find('img')
                    video = {
                        'title': a_thumb_video.attrs.get('title'),
                        'url': f"https://okxxx2.com{a_thumb_video.attrs.get('href')}",
                        'preview': a_thumb_video.attrs.get('data-preview-custom'),
                        'thumbnail': 'https:' + img_thumb_video.attrs.get('data-original')
                    }

                    # Extract info from thumbnail-info
                    thumb_meta_div = thumb_video.find('ul', class_='video-meta')
                    video['meta'] = {
                        'contents': [
                            {
                                'title': d.attrs.get('title'),
                                'url': f"https://okxxx2.com{d.attrs.get('href', '')}",
                                'verified': 'icon-verified' in d.find('svg').attrs.get('class', '')
                            } for d in thumb_video.find('div', {'class':'content_items'}).find_all('a') if d
                        ],
                        'duration': convert_duration_to_seconds(thumb_meta_div.find('i', class_='fa fa-clock-o').parent.find('span').text),
                        'views': thumb_meta_div.find('i', class_='fa fa-eye').parent.find('span').text,
                        'upload_date': thumb_meta_div.find('i', class_='fa fa-calendar-o').parent.find('span').text
                    }
                    videos_list.append(video)

                return videos_list
            except Exception as e:
                print(f"Unable to extract videos: {e}")
                return []
