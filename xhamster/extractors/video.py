import asyncio, aiohttp, re, json
from rich import print

async def extract_video_info(sem: asyncio.Semaphore, session: aiohttp.ClientSession, url: str, recommendations: bool = True, **kwargs) -> dict:
    async with sem:
        async with session.get(url, **kwargs) as response:
            response.raise_for_status()
            try:
                webpage = await response.text()
                initial_data_pattern = re.compile(r'window\.initials\s*=\s*(\{.*?\});', re.DOTALL)
                
                initial_prop_found = initial_data_pattern.search(webpage)
                if not initial_prop_found:
                    raise ValueError('Unable to find initial data!')
                
                initial_props = json.loads(initial_prop_found.group(1))
                video_data = {}
                
                video_model = initial_props.get("videoModel", {})
                video_entity = initial_props.get("videoEntity", {})
                xplayer_settings = initial_props.get("xplayerSettings", {})
                
                media_info = {}
                media_url = (xplayer_settings.get("sources", {}).get("hls", {}).get("av1") or xplayer_settings.get("sources", {}).get("hls", {}).get("h264") or {}).get("url", None)
                for res in media_url.split("multi=")[1].split("/")[0].split(","):
                    if not res:
                        continue
                    res_part = res.split(":")
                    res = res_part[-2].strip() if len(res_part) > 2 else res_part[-1]
                    media_info[res] = {
                        "index": media_info.get("index", 0) + 1,
                        "resolution": res,
                        "url": media_url.replace("_TPL_", res)
                    }
                
                video_data = {**video_model, **video_entity, **xplayer_settings}
                # del video_data["sources"]
                del video_data["hlsConfig"]
                del video_data["preload"]
                
                video_data["media"] = media_info
                
                video_data["tags"] = initial_props.get("videoTagsComponent", {}).get("tags", [])
                video_data["comments"] = initial_props.get("commentsComponent", {}).get("commentsList", {}).get("items", [])
                
                recom = []
                if recommendations:
                    relatedComponent = initial_props.get("relatedVideosComponent", None)
                    if relatedComponent:
                        recom = relatedComponent.get("videoTabInitialData", {}).get("videoListProps", {}).get("videoThumbProps", [])

                video_data["recommendation"] = recom
                
                return video_data
                
            except Exception as e:
                print('Parsing error:', e)
                return {}
