import aiohttp, json, re
from exctractors.converters import convert_views

def get_resolutions(flash_var: dict) -> dict:
    res = {}
    for media in flash_var['mediaDefinitions']:
        if media.get('remote') is not None:
            continue
        res[int(media['quality'])] = {
            'format': media['format'],
            'url': media['videoUrl']
        }
    return dict(sorted(res.items(), key=lambda x: x[0], reverse=True))

async def extract_video(sem, session: aiohttp.ClientSession, video_link: str, include_var: bool = False, **kwargs):
    async with sem:
        async with session.get(video_link, **kwargs) as r:
            try:
                r.raise_for_status()
                page = await r.text()

                flash_var_match = re.search(r"""var (flashvars_\d*) = (?P<dict>{.*});\n""", page)
                if not flash_var_match:
                    raise ValueError('Unable to find flash vars')
                flash_var = json.loads(flash_var_match.group('dict'))

                title_match = re.search(r"<title(?P<name>.*)</title>", page)
                if not title_match:
                    title = "No title"
                else:
                    title = title_match.group('name')

                views_match = re.search(r"""<div\sclass=['"]views["']>[^<]*?<span\s?class=['"]count["']>(?P<views>[^<]*)</span>\s?Views\s?</div>""", page)
                if not views_match:
                    views = 0
                else:
                    views = convert_views(views_match.group('views'))
                
                data = {
                    'id': flash_var.get('playbackTracking').get('video_id'),
                    'title': flash_var['video_title'] or title,
                    'thumbnail': flash_var.get('image_url'),
                    'duration': flash_var['video_duration'],
                    'next_vid': flash_var.get('nextVideo'),
                    'resolution': get_resolutions(flash_var),
                    'flash_var': flash_var if include_var else {},
                    'timestamp': flash_var.get('playbackTracking').get('video_timestamp'),
                    'views': views
                }
                data['url'] = flash_var['link_url']

                return data
            except Exception as e:
                print(f'Unable to ectract video from "{video_link}": {e}')
                raise e
