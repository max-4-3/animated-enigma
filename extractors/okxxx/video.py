from bs4 import BeautifulSoup, NavigableString
import re
from http.cookies import SimpleCookie
from ..converters import convert_duration
from .page import extract_all_thumb_bl_info
from ..models import ExternalLink, Metadata, Media, MediaItem, Video, ThumbVideo, Thumbnail, VideoLinks, Recommendations
from . import DOMAIN

async def extract_video_info(sem, session, video_url: str, recommendation: bool = True, **kwargs) -> Video | None:
    """Extract video info from a webpage and returns a dict with info"""
    async with sem:
        webpage = await session.get(video_url, **kwargs)
        set_cookie_header = webpage.headers.getall('Set-Cookie', [])
        for cookie_str in set_cookie_header:
            cookie = SimpleCookie()
            cookie.load(cookie_str)
            # Convert to a dict that aiohttp can understand
            cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
            session.cookie_jar.update_cookies(cookies_dict, webpage.url)
        
        if webpage.cookies:
            session.cookie_jar.update_cookies(webpage.cookies)

        try:
            webpage.raise_for_status()
            soup = BeautifulSoup(await webpage.text(), 'html.parser')

            title = ' '.join(soup.find('title').text.split()[2:-2])
            thumbnail = Thumbnail(url=soup.select_one('meta[property*="og:image"]').attrs.get('content', None))
            video_info_div = soup.find('div', class_='video-info')

            # Extract Socials
            socials = VideoLinks(title="Socials", links=[])
            for a_s in video_info_div.select('div.social-holder a'):
                try:
                    socials.links.append(ExternalLink(
                        name = a_s.select_one('span').get_text(strip=True),
                        url = a_s.attrs.get('href', None)
                    ))
                except:
                    pass

            # Extract Video Links (Ensure we skip the "social-holder video-link" by using the exact match or navigating structure)
            video_links = []
            # Use a CSS selector to precisely target the second video-link div
            video_link_elements = video_info_div.select('div.video-link:not(.social-holder)') or []
            for video_link_element in video_link_elements:

                # Extract non-tag text (NavigableStrings only)
                non_tag_texts = [
                    child.strip() for child in video_link_element.contents
                    if isinstance(child, NavigableString) and child.strip()
                ]

                # Join the non-tag texts into a single string (if there are multiple)
                non_tag_text = ' '.join(non_tag_texts)

                # Use regex to find individual words or phrases
                words = re.findall(r'\b\w+\b', non_tag_text)
                video_link = VideoLinks(
                    title = " ".join(words),
                    links = []
                )
                for a in video_link_element.select('a'):
                    href = a.attrs.get('href', '')
                    url = href if href.startswith(('http://', 'https://')) else f"{DOMAIN}{href}"
                    video_link.links.append(
                        ExternalLink(
                            name = a.get_text(strip=True) or "No Title Provided!",
                            url = url
                        )
                    )
                video_links.append(video_link)

            # Extract video tag
            tags = VideoLinks(
                title="Tags",
                links = []
            )
            for li in video_info_div.select('ul.video-tags li a'):
                tags.links.append(
                    ExternalLink(
                        name = li.get_text(strip=True) or li.attrs.get('href', '').split('/')[-1].replace('-', ' ').title(),
                        url = DOMAIN + (li.attrs.get('href') or "/")
                    )
                )

            # Extract recommendations
            related_videos_data = Recommendations()
            if recommendation:
                related_videos_element = soup.select_one('div.related-videos')
                if related_videos_element:
                    related_videos_data.title = " ".join([k.get_text(strip=True) for k in related_videos_element.select('h2.title-rel a') if k])
                    related_videos_data.contents = await extract_all_thumb_bl_info(related_videos_element)

            # Extract video's meta
            meta_div = video_info_div.select_one('div.block-des')
            metadata = Metadata(
                views=int(meta_div.select_one('i.fa.fa-eye').parent.select_one('span').get_text(strip=True).replace(' ', '')),
                duration=convert_duration(meta_div.find('i', class_='fa fa-clock-o').parent.find('span').text.replace(' ', '')),
                upload_date=meta_div.find('i', class_='fa fa-calendar-o').parent.find('span').text.replace(' ', ''),
                extras={
                    "desc": meta_div.select_one('div.desc').get_text(strip=True) or "No Description"
                }
            )

            # Extract media info
            main_media_url = [k.attrs.get('src') for k in soup.select('video source') if k.attrs.get('label', '') == "Auto"][0]
            raw_media = await session.get(main_media_url)
            raw_media.raise_for_status()

            raw_media = await raw_media.text()
            media = Media(base_url=main_media_url)
            count = 1
            for idx, raw in enumerate(raw_media.splitlines(keepends=False)):
                if (raw is None) or (idx == 0):
                    continue

                resolution = None
                framerate = None
                url = None

                # Ignore non Comments
                if not raw.startswith("#"):
                    continue

                for part in raw.split(","):
                    if part.startswith("FRAME-RATE"):
                        framerate = part.split("=", 1)[1]
                    elif part.startswith("RESOLUTION"):
                        resolution = part.split("=", 1)[1].strip()
                url = raw_media.splitlines(keepends=False)[idx + 1]

                media.items.append(
                    MediaItem(
                        idx = count,
                        url = url,
                        resolution = resolution,
                        framerate=framerate
                    )
                )
                count += 1

            return Video(
                title= title,
                thumbnail= thumbnail,
                url= video_url,
                metadata= metadata,
                recommendations=[related_videos_data],
                media= media,
                links= video_links,
                tags= tags.links
            )

        except Exception as e:
            print(f"Unable to extract info from '{video_url}': {e}")
            return None
    