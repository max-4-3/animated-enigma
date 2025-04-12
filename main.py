import asyncio, os
from uuid import uuid4
from colorama import Fore
from aiohttp import ClientSession

from tools.utils import clear, read_until, save_data, is_user_quit
from tools.downloader import download_video
from config import *

async def okxxx_handler():

    from okxxx import is_valid_link, is_page_link, is_video_link, make_session
    from okxxx.extractors.page import extract_videos_from_webpage
    from okxxx.extractors.video import extract_video_info

    async def download_videos(sem, session: ClientSession, videos: list, root_download_path: str):
        os.makedirs(root_download_path, exist_ok=True)
        download_dir = root_download_path
        print(f'Downloading "{Fore.LIGHTRED_EX}{videos.__len__()}{Fore.RESET}" videos in "{Fore.LIGHTCYAN_EX}{os.path.abspath(download_dir)}{Fore.RESET}"')

        new_videos = []
        total_size = 0
        total_time = 0
        for idx, video in enumerate(videos, start=1):

            clear()

            print(f'{idx}. Extracting details for "{Fore.LIGHTBLUE_EX}{video['url'].split('/')[-1] or video['url'].split('/')[-2]}{Fore.RESET}" \n[{len(videos) - idx} remaning, total: {len(videos)}]')
            try:
                full_info = await extract_video_info(sem, session, video['url'])
                new_videos.append(full_info)

                print(f'Downloading "{full_info['title']}"...')
                download_url = list(full_info['media'].values())[-1]['url']
                download_size, download_time = await download_video(sem, session, full_info['title'], download_url, '.mp4', download_dir)
                print(f'Completed Download in {download_time}s [{download_size / (1024**2):.2f}MB]')

                total_size += download_size
                total_time += download_time
            except KeyboardInterrupt:
                if input('Quit Downloading?: ').lower().strip() in ['yes', 'y', '']:
                    break

            except Exception as e:
                print(f'Got an error: {e}')
            finally:
                await asyncio.sleep(1)

        return new_videos

    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                ui = input(f'{Fore.LIGHTYELLOW_EX}Enter link ["list" for multiple links]{Fore.RESET}: ').strip()
                
                if ui.lower().strip() == "list":
                    urls = [{'url': url} for url in read_until('Enter link', validator=is_video_link)]
                elif ui.lower().strip() == "exit":
                    return
                elif is_page_link(ui):
                    urls = await extract_videos_from_webpage(QUERY_SEM, session, ui.strip())
                elif is_video_link:
                    urls = [{'url': ui}]
                elif not is_valid_link(ui):
                    raise ValueError(f'Invalid Url! [{ ui = }]')

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, os.path.join(DOWNLOAD_PATH, 'okxxx'))
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def pornhub_handler():
    from pornhub import is_valid_link, is_page_link, is_video_link, make_session
    from okxxx.extractors.page import extract_videos_from_webpage
    from okxxx.extractors.video import extract_video_info

    async def download_videos(sem, pornhub_session: ClientSession, download_session: ClientSession, videos: list, root_download_path: str):
        os.makedirs(root_download_path, exist_ok=True)
        download_dir = root_download_path
        print(f'Downloading "{Fore.LIGHTRED_EX}{videos.__len__()}{Fore.RESET}" videos in "{Fore.LIGHTCYAN_EX}{os.path.abspath(download_dir)}{Fore.RESET}"')

        async def get_index_url(a):
            async with session.get(a) as m3u8_r:
                m3u8_r.raise_for_status()
                raw = await m3u8_r.text()

                base_url = a.rsplit('/', 1)[0] + '/'
                return base_url + [l for l in raw.splitlines() if l and not l.startswith('#')][0]

        new_videos = []
        total_size = 0
        total_time = 0
        for idx, video in enumerate(videos, start=1):

            clear()

            print(f'{idx}. Extracting details for "{Fore.LIGHTBLUE_EX}{video['url'].split('/')[-1]}{Fore.RESET}" \n[{len(videos) - idx} remaning, total: {len(videos)}]')
            try:
                full_info = await extract_video_info(sem, pornhub_session, video['url'].replace('https://www.pornhub.org', ''))
                new_videos.append(full_info)

                print(f'Downloading "{full_info['title']}" [{full_info['duration']}s]...')
                download_url = await get_index_url(max(full_info['resolution'].items(), key=lambda x: x[0])[1]['url'].replace('https://www.pornhub.org', ''))
                download_size, download_time = await download_video(sem, download_session, full_info['title'], download_url, '.mp4', download_dir)
                print(f'Completed Download in {download_time}s [{download_size / (1024**2):.2f}MB]')

                total_size += download_size
                total_time += download_time
            except KeyboardInterrupt:
                if input('Quit Downloading?: ').lower().strip() in ['yes', 'y', '']:
                    break
            except Exception as e:
                print(f'Unable to complete download: \n{"-"*10}\n{e}\n{"-"*10}')
                input('Press enter to move on...')
            finally:
                await asyncio.sleep(1 if idx % 10 != 0 else 3)

        return new_videos

    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                ui = input(f'{Fore.LIGHTYELLOW_EX}Enter link ["list" for multiple links]{Fore.RESET}: ').strip()
                
                if ui.lower().strip() == "list":
                    urls = [{'url': url} for url in read_until('Enter link', validator=is_video_link)]
                elif ui.lower().strip() == "exit":
                    return
                elif is_page_link(ui):
                    urls = await extract_videos_from_webpage(QUERY_SEM, session, ui.strip())
                elif is_video_link:
                    urls = [{'url': ui}]
                elif not is_valid_link(ui):
                    raise ValueError(f'Invalid Url! [{ ui = }]')

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, os.path.join(DOWNLOAD_PATH, 'pornhub'))
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def xnxx_handler():
    from xnxx import is_valid_link, is_page_link, is_video_link, make_session
    from xnxx.extractors.video import extract_video_info
    
    async def download_videos(sem, session: ClientSession, videos: list, root_download_path: str):
        os.makedirs(root_download_path, exist_ok=True)
        download_dir = root_download_path
        print(f'Downloading "{Fore.LIGHTRED_EX}{videos.__len__()}{Fore.RESET}" videos in "{Fore.LIGHTCYAN_EX}{os.path.abspath(download_dir)}{Fore.RESET}"')

        new_videos = []
        total_size = 0
        total_time = 0
        for idx, video in enumerate(videos, start=1):

            clear()

            print(f'{idx}. Extracting details for "{Fore.LIGHTBLUE_EX}{video['url'].split('/')[-1] or video['url'].split('/')[-2]}{Fore.RESET}" \n[{len(videos) - idx} remaning, total: {len(videos)}]')
            try:
                full_info = await extract_video_info(sem, session, video['url'])
                new_videos.append(full_info)

                print(f'Downloading "{full_info['title']}"...')
                download_url = list(full_info['media'].values())[0]['url']
                download_size, download_time = await download_video(sem, session, full_info['title'], download_url, '.mp4', download_dir)
                print(f'Completed Download in {download_time}s [{download_size / (1024**2):.2f}MB]')

                total_size += download_size
                total_time += download_time
            except KeyboardInterrupt:
                if input('Quit Downloading?: ').lower().strip() in ['yes', 'y', '']:
                    break

            except Exception as e:
                print(f'Got an error: {e}')
            finally:
                await asyncio.sleep(1)

        return new_videos

    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                ui = input(f'{Fore.LIGHTYELLOW_EX}Enter link ["list" for multiple links]{Fore.RESET}: ').strip()
                
                if ui.lower().strip() == "list":
                    urls = [{'url': url} for url in read_until('Enter link', validator=is_video_link)]
                elif ui.lower().strip() == "exit":
                    return
                elif is_video_link(ui):
                    urls = [{'url': ui}]
                elif is_page_link(ui):
                    urls = []
                    # urls = await extract_videos_from_webpage(QUERY_SEM, session, ui.strip())
                elif not is_valid_link(ui):
                    raise ValueError(f'Invalid Url! [{ ui = }]')

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, os.path.join(DOWNLOAD_PATH, 'xnxx'))
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def main():

    available_domains = {
        'xnxx': xnxx_handler,
        'pornhub': pornhub_handler,
        'okxxx': okxxx_handler
    }

    while True:
        userinput = input('Enter Domain: ')

        if userinput.lower().strip() == 'exit':
            return

        handler = available_domains.get(userinput.lower().strip())
        if not handler:
            raise NotImplementedError(f'Downloader for \"{userinput}\" is not implemented!')

        await handler()

if __name__ == "__main__":
    asyncio.run(main())
