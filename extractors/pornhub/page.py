from bs4 import BeautifulSoup, Tag
from . import DOMAIN, get_text_wrapper
from uuid import uuid4
from ..converters import convert_views, convert_duration
import aiohttp
from ..models import Thumbnail, ThumbVideo, Metadata, VideoLinks, ExternalLink
from http.cookies import SimpleCookie

async def extract_all_thumb_videos(webpage: BeautifulSoup | Tag) -> list[ThumbVideo | None]:
    results = []
    for li in webpage.select('li.videoblock'):
        # Because some videos are not valid
        video, metadata, links = None, None, []
        
        # Extract Metadata
        try:
            metadata = Metadata(
                views = convert_views(get_text_wrapper(lambda: li.select_one('span.views var').get_text(strip=True), 0)),
                duration = convert_duration(get_text_wrapper(lambda: li.select_one('var.duration').get_text(strip=True), 0)),
                upload_date=get_text_wrapper(lambda: li.select_one('var.added').get_text(strip=True), 'A Long Time Ago...'),
                extras={
                    "rating": get_text_wrapper(lambda: li.select_one('div.value').get_text(strip=True), 0)
                }
            )
        except Exception as e:
            print('Unable to extract metadata:', e)
            metadata = Metadata()
        
        # Extract Links
        try:
            videolink = VideoLinks(title="Uploader(s)", links=[])
            for a in li.select('div.usernameWrap a'):
                try:
                    videolink.links.append(ExternalLink(name=get_text_wrapper(lambda: a.get_text(strip=True), 'Unknown Name'), url='https://' + DOMAIN + (a.attrs.get('href') or '/')))
                except:
                    pass
            links.append(videolink)
        except:
            pass

        # Make the video
        try:
            video = ThumbVideo(
                id = li.attrs.get('data-video-vkey') or li.attrs.get('id') or uuid4().hex,
                title = get_text_wrapper(lambda: li.select_one('span.title a').get_text(strip=True), 'No Title'),
                url = "https://" + DOMAIN + li.select_one('span.title a').attrs.get('href', '/'),
                thumbnail = Thumbnail(url=li.select_one('img').attrs.get('src')),
                metadata = metadata,
                links = links
            )
            results.append(video)
        except Exception as e:
            print('Unable to extract video!')

    return results

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
                return await extract_all_thumb_videos(soup)
            except Exception as e:
                print(f'Unable to get videos from page "{page_link}": {e}')
                return []