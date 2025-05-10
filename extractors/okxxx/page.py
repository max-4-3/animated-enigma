from bs4 import BeautifulSoup
from http.cookies import SimpleCookie
from . import DOMAIN
from ..converters import convert_views, convert_duration
from ..models import ThumbVideo, Metadata, ExternalLink, Thumbnail

async def extract_all_thumb_bl_info(page_soup: BeautifulSoup) -> list[ThumbVideo | None]:
    results = []
    for thumb_video in page_soup.select('div[class*="item thumb-bl thumb-bl-video"]'):
        a_thumb_video = thumb_video.select_one('a')
        img_thumb_video = thumb_video.select_one('img')
        video = None
        metadata = None
        links = []

        try:
            # Extract info from thumbnail-info
            thumb_meta_div = thumb_video.select_one('ul.video-meta')
            metadata = Metadata(
                views=convert_views(thumb_meta_div.select_one('i.fa.fa-eye').parent.select_one('span').get_text(strip=True)),
                duration=convert_duration(thumb_meta_div.select_one('i.fa.fa-clock-o').parent.select_one('span').get_text(strip=True)),
                upload_date=thumb_meta_div.select_one('i.fa.fa-calendar-o').parent.select_one('span').get_text(strip=True),
                extras={
                    "preview": a_thumb_video.attrs.get('data-preview-custom')
                }
            )
        except Exception as e:
            print('Unable to extract meta:', e)
            metadata = Metadata()

        try:
            links = [
                ExternalLink(name=d.attrs.get('title'), url=DOMAIN + (d.attrs.get('href') or '/'), extras={'verified': 'icon-verified' in d.select_one('svg').attrs.get('class', 'N/A')})
                for d in thumb_video.select('div.content-items a') if d
            ]
        except:
            pass

        try:
            video = ThumbVideo(
                title=a_thumb_video.attrs.get('title') or 'Untitled Video',
                url=DOMAIN + (a_thumb_video.attrs.get('href') or "/"),
                thumbnail = Thumbnail(url = 'https:' + img_thumb_video.attrs.get('data-original')),
                metadata=metadata,
                links=links
            )
            results.append(video)
        except Exception as e:
            print('Unable to extract basic info:', e)

    return results

async def extract_videos_from_webpage(sem, session, page_url: str) -> list[ThumbVideo | None]:
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
                return await extract_all_thumb_bl_info(soup)
            except Exception as e:
                print(f"Unable to extract videos: {e}")
                return []
