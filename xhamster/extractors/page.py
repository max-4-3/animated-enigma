import json, re
from rich import print

async def extract_videos_from_webpage(sem, session, url, **kwargs):
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
            
                return initial_props.get("layoutPage", {}).get("videoListProps", {}).get("videoThumbProps", [])
            except Exception as e:
                print('Scrapping Error:', e)
                return []
            