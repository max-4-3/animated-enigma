import json, re
from rich import print
from http.cookies import SimpleCookie


async def extract_videos_from_webpage(
    sem, session, url, initial_dict: bool = False, **kwargs
):
    async with sem:
        async with session.get(url, **kwargs) as response:
            response.raise_for_status()
            set_cookie_header = response.headers.getall("Set-Cookie", [])
            for cookie_str in set_cookie_header:
                cookie = SimpleCookie()
                cookie.load(cookie_str)
                # Convert to a dict that aiohttp can understand
                cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
                session.cookie_jar.update_cookies(cookies_dict, response.url)

            if response.cookies:
                session.cookie_jar.update_cookies(response.cookies)

            try:
                webpage = await response.text()
                initial_data_pattern = re.compile(
                    r"window\.initials\s*=\s*(\{.*?\});", re.DOTALL
                )

                initial_prop_found = initial_data_pattern.search(webpage)
                if not initial_prop_found:
                    raise ValueError("Unable to find initial data!")

                initial_props = json.loads(initial_prop_found.group(1))
                layoutPage = initial_props.get("layoutPage", {})
                listPropsKey = [
                    key
                    for key in layoutPage.keys()
                    if "videoListProps".lower() in key.lower()
                ]

                if not initial_dict:
                    thums = []
                    for key in listPropsKey:
                        thumbData = layoutPage.get(key)
                        if thumbData and isinstance(thumbData, dict):
                            thumbsItem = thumbData.get("videoThumbProps", [])
                            if thumbsItem and isinstance(thumbsItem, list):
                                thums.extend(thumbsItem)
                    return thums
                else:
                    return initial_props
            except Exception as e:
                print("Scrapping Error:", e)
                return []

