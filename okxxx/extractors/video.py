from bs4 import BeautifulSoup, NavigableString
import re
from http.cookies import SimpleCookie
from .converters import convert_duration_to_seconds, convert_upload_date_to_timestamp

async def extract_video_info(sem, session, video_url: str, recommendation: bool = True, **kwargs):
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
            video_info_div = soup.find('div', class_='video-info')

            # Extract Socials
            social_element = video_info_div.find('div', class_='social-holder')
            socials = []
            if social_element:
                for a_s in social_element.find_all('a'):
                    social = {
                        'name': a_s.find('span').text.strip(),
                        'link': a_s.attrs.get('href')
                    }
                    socials.append(social)

            # Extract Video Links (Ensure we skip the "social-holder video-link" by using the exact match or navigating structure)
            video_links = []
            # Use a CSS selector to precisely target the second video-link div
            video_link_elements = video_info_div.select('div.video-link:not(.social-holder)')
            if video_link_elements:
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
                    video_link = {
                        'title': words,
                        'links': []
                    }
                    for a in video_link_element.find_all('a'):
                        href = a.attrs.get('href', '')
                        url = href if href.startswith(('http://', 'https://')) else f"https://okxxx2.com{href}"
                        video_link['links'].append(
                            {
                                'title': a.text.strip() if a.text else 'no title provided!',
                                'url': url
                            }
                        )
                    video_links.append(video_link)

            # Extract video tage
            tags_element = video_info_div.find('ul', class_='video-tags')
            tags = []
            for idx, li in enumerate(tags_element.find_all('li'), start=1):
                if idx == 1:
                    # this element is just 'Tags:'
                    continue
                a = li.find('a')
                tags.append(
                    {
                        'title': a.text.strip() if a.text else a.attrs.get('href', '').split('/')[-1].replace('-', ' ').title(),
                        'url': f"https://okxxx2.com{a.attrs.get('href', '')}"
                    }
                )

            # Extract recommendations
            related_videos_data = {}
            if recommendation:
                related_videos_element = soup.find('div', class_='related-videos')
                related_videos = []
                for thumb_video in related_videos_element.select('div[class^="item thumb-bl thumb-bl-video"]'):

                    # Extract info from thumbnail
                    a_thumb_video = thumb_video.find('a')
                    img_thumb_video = thumb_video.find('img')
                    related_video = {
                        'title': a_thumb_video.attrs.get('title'),
                        'url': f"https://okxxx2.com{a_thumb_video.attrs.get('href')}",
                        'preview': a_thumb_video.attrs.get('data-preview-custom'),
                        'thumbnail': 'https:' + img_thumb_video.attrs.get('data-original')
                    }

                    # Extract info from thumbnail-info
                    thumb_info = thumb_video.find('div', class_='thumb-bl-info')
                    thumb_meta_div = thumb_info.find('ul', class_='video-meta')
                    related_video['meta'] = {
                        'contents': [
                            {
                                'title': d.attrs.get('title'),
                                'url': f"https://okxxx2.com{d.attrs.get('href', '')}",
                                'verified': bool(d.find('svg').attrs.get('icon icon-verified'))
                            } for d in thumb_info.find_all('a') if d
                        ],
                        'duration': convert_duration_to_seconds(thumb_meta_div.find('i', class_='fa fa-clock-o').parent.find('span').text),
                        'views': thumb_meta_div.find('i', class_='fa fa-eye').parent.find('span').text,
                        'upload_date': thumb_meta_div.find('i', class_='fa fa-calendar-o').parent.find('span').text
                    }

                    related_videos.append(related_video)

                related_videos_data['factor'] = [k.text for k in related_videos_element.find('h2', class_='title-rel').find_all('a') if k]
                related_videos_data['videos'] = related_videos

            # Extract video's meta
            meta_div = video_info_div.find('div', class_='block-des')
            meta = {
                'description': meta_div.find('div', class_='desc').text.strip() if meta_div.find('div', class_='desc').text else 'No Description',
                'views': int(meta_div.find('i', class_='fa fa-eye').parent.find('span').text.replace(' ', '')),
                'duration': convert_duration_to_seconds(meta_div.find('i', class_='fa fa-clock-o').parent.find('span').text.replace(' ', '')),  # Example: MM:SS (optional: HH:MM:SS)
                'upload_date': convert_upload_date_to_timestamp(meta_div.find('i', class_='fa fa-calendar-o').parent.find('span').text.replace(' ', ''))  # Example: DD.MM.YYYY (01.01.2025)
            }

            # Extract media info
            main_media_url = [k.attrs.get('src') for k in soup.find('video').find_all('source') if k.attrs.get('label', '') == "Auto"][0]
            raw_media = await session.get(main_media_url)
            raw_media.raise_for_status()

            raw_media = await raw_media.text()
            media_info = {}
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
                        framerate = int(float(part.split("=")[1]))
                    elif part.startswith("RESOLUTION"):
                        resolution = part.split("=")[1].strip()
                url = raw_media.splitlines(keepends=False)[idx + 1]

                media_info[resolution] = {
                    "idx": count,
                    "resolution": resolution,
                    "framerate": framerate,
                    "url": url
                }
                count += 1


            video_meta = {
                'title': title,
                'meta': meta,
                'tags': tags,
                'links': video_links,
                'socials': socials,
                'url': soup.find('meta', {'property': "og:url"}).attrs.get('content'),
                "media": media_info,
                'recommendation': related_videos_data
            }
            return video_meta

        except Exception as e:
            print(f"Unable to extract info from '{video_url}': {e}")
            return {}
    