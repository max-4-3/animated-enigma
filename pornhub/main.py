from exctractors.video import extract_video
from exctractors.page import extract_videos_from_webpage
from fake_useragent import UserAgent
from tqdm.asyncio import tqdm
from uuid import uuid4
from datetime import datetime
from colorama import Fore

import os, asyncio, aiohttp, json, aiofiles, shutil, time, ssl

IP_ADDR = '66.254.114.41'
DOMAIN = 'www.pornhub.org'
DOWNLOAD_DIR, DATA_DIR, QUERY_SEM, DOWNLOAD_SEM = None, None, None, None

def load_data(fp=os.path.join(os.path.split(os.path.split(__file__)[0])[0], 'config.json')):
    if not os.path.exists(fp):
        return
    global DOWNLOAD_DIR, DATA_DIR, QUERY_SEM, DOWNLOAD_SEM

    with open(fp, 'r', errors='ignore', encoding='utf-8') as file:
        data = json.load(file)
        DOWNLOAD_DIR = data.get('download_dir', None)
        if not DOWNLOAD_DIR:
            raise ValueError(f'Please Set Download PATH in "{fp}"')

        DOWNLOAD_DIR = DOWNLOAD_DIR if not DOWNLOAD_DIR.startswith('~') else os.path.expanduser(DOWNLOAD_DIR)
        DOWNLOAD_DIR = os.path.join(DOWNLOAD_DIR, os.path.split(os.path.split(__file__)[0])[1])
        DATA_DIR = os.path.join(DOWNLOAD_DIR, 'data')
        QUERY_SEM = asyncio.Semaphore(data.get('query_sem_limit', 2))
        DOWNLOAD_SEM = asyncio.Semaphore(data.get('download_sem_limit', 4))

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

def save_data(d, fp):
    with open(fp, 'w') as file:
        try:
            json.dump(d, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f'Unable to save data to file "{fp}": {e}')

def clear():
    os.system('cls' if os.name.lower() in ['windows', 'nt'] else 'clear')

async def download_segment(sem, session: aiohttp.ClientSession, segment_url: str, segment_name: str, download_dir: str, pbar: tqdm):
    async with sem:
        try:
            async with session.get(segment_url) as r:
                r.raise_for_status()
                download_path = os.path.join(download_dir, segment_name)

                with tqdm(total=int(r.headers.get('content-length', 0)), unit='B', unit_scale=True, desc=f'--> Downloading "{segment_name}"'.expandtabs(4), leave=False, position=1) as segment_pbar:
                    async with aiofiles.open(download_path, 'wb') as file:
                        while chunk := await r.content.read(1024 * 1024 * 10):
                            await file.write(chunk)
                            segment_pbar.update(len(chunk))

                await asyncio.sleep(0.1)
                pbar.update(1)

                return download_path
        except Exception as e:
            print(f'Unable to download segement from: \n{Fore.LIGHTYELLOW_EX}{segment_url}{Fore.RESET}\n{Fore.LIGHTRED_EX}Error{Fore.RESET}: {e}')
            return ''

async def download_video(sem: asyncio.Semaphore, session: aiohttp.ClientSession, video_title: str, video_url: str, video_ext: str, download_dir: str, cleanup: bool = True, re_encode: bool = False):
    async with sem:
        random_name = str(uuid4())
        start = time.perf_counter()
        temp_dir = os.path.join(download_dir, 'temp_' + random_name)
        os.makedirs(temp_dir, exist_ok=True)
        m3u8_urls = []

        try:
            print(f'Parsing index...')
            # First get request
            async with session.get(video_url) as m3u8_r:
                m3u8_r.raise_for_status()
                raw = await m3u8_r.text()

                base_url = video_url.rsplit('/', 1)[0] + '/'
                new_index_url = base_url + [l for l in raw.splitlines() if l and not l.startswith('#')][0]

            # Second get request to get all parts
            async with session.get(new_index_url) as new_response:
                new_response.raise_for_status()

                raw = await new_response.text()
                m3u8_urls = [((base_url if not l.startswith('https') else '') + l) for l in raw.splitlines() if l and not l.startswith('#')]
                print(f'{Fore.LIGHTRED_EX}{m3u8_urls.__len__()}{Fore.RESET} segements url found!')

            # Download all segments
            with tqdm(total=len(m3u8_urls), position=0, desc='Segment progress', unit='seg', colour='green') as pbar:
                tasks = []
                filenames = []
                for idx, link in enumerate(m3u8_urls, start=1):
                    segment_name = f"seg-{idx}.ts"
                    tasks.append(asyncio.create_task(download_segment(DOWNLOAD_SEM, session, link, segment_name, temp_dir, pbar)))
                    filenames.append(os.path.join(temp_dir, segment_name))

                await asyncio.gather(*tasks)

            # Create the segmentInfo.txt file with correct formating
            segement_infofile = os.path.join(download_dir, f'{random_name}_seginfo.txt')
            with open(segement_infofile, 'w') as file:
                file.write('\n'.join([f'file \'{a.replace("\\", "/")}\'' for a in filenames if a])) # file 'c:\abs\path\segment.ts'

            # Concate (e.g. combine) all segments ( with abspath being compulsory )
            print(f'Concating {len(filenames)} segments...')
            output_file_temp = os.path.join(download_dir, random_name + '_' + video_title + video_ext)
            command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', os.path.abspath(segement_infofile), '-c', 'copy', '-y', '-hide_banner', '-loglevel', 'error', '-fflags', '+genpts', os.path.abspath(output_file_temp)]
            proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            _, stderr = await proccess.communicate()

            if proccess.returncode != 0:
                print(f'{Fore.LIGHTMAGENTA_EX}Error occured: {Fore.RESET}\n{stderr.decode()}')
            else:
                print(f'{Fore.LIGHTGREEN_EX}Concation succesfull!{Fore.RESET}')

            # Re-encode for smoother playback if 're_encode'
            output_file = os.path.join(download_dir, video_title + video_ext)
            if re_encode:
                print('Re-encoding...')
                command = ['ffmpeg', '-i', output_file_temp, '-hide_banner', '-c:v', 'libx264', '-preset', 'fast', '-c:a', 'aac', output_file]
                proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
                _, stderr = await proccess.communicate()

                if proccess.returncode != 0:
                    print(f'{Fore.LIGHTMAGENTA_EX}Error occured: {Fore.RESET}\n{stderr.decode()}')
                else:
                    print(f'{Fore.LIGHTGREEN_EX}Re-encoding succesfull!{Fore.RESET}')
            else:
                os.rename(output_file_temp, output_file)
        finally:
            # Cleanup the temp files if 'cleanup'
            if cleanup:
                print(f'Cleaning temp files...')
                try:
                    shutil.rmtree(temp_dir, True)
                    os.remove(segement_infofile)
                    if os.path.exists(output_file_temp):
                        os.remove(output_file_temp)
                    print(f'{Fore.LIGHTGREEN_EX}Cleanup succesfull{Fore.RESET}!')
                except Exception as e:
                    print(f'{Fore.LIGHTMAGENTA_EX}Error occured during cleanup{Fore.RESET}: {e}')
            else:
                print('Skipping cleaning the temp!')

        end = time.perf_counter()
        return (os.path.getsize(output_file) if os.path.exists(output_file) else 0), round(end - start, 2)

async def download_videos(sem, pornhub_session: aiohttp.ClientSession, download_session: aiohttp.ClientSession, data: dict, root_download_path: str):
    os.makedirs(root_download_path, exist_ok=True)
    videos = data['videos']
    download_dir = root_download_path
    print(f'Downloading "{Fore.LIGHTRED_EX}{videos.__len__()}{Fore.RESET}" videos in "{Fore.LIGHTCYAN_EX}{os.path.abspath(download_dir)}{Fore.RESET}"')

    new_videos = []
    total_size = 0
    total_time = 0
    for idx, video in enumerate(videos, start=1):

        clear()

        print(f'{idx}. Extracting details for "{Fore.LIGHTBLUE_EX}{video['url'].split('/')[-1]}{Fore.RESET}" \n[{len(videos) - idx} remaning, total: {len(videos)}]')
        try:
            full_info = await extract_video(sem, pornhub_session, video['url'].replace('https://www.pornhub.org', ''))
            new_videos.append(full_info)

            print(f'Downloading "{full_info['title']}" [{full_info['duration']}s]...')
            download_url = max(full_info['resolution'].items(), key=lambda x: x[0])[1]['url'].replace('https://www.pornhub.org', '')
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

    data['videos'] = new_videos
    data['total_download_size'] = total_size
    data['total_download_time'] = total_time
    return data

async def main():
    
    load_data()

    async with  as download_session:
        while True:
            clear()
            temp = os.path.join(f'{uuid4()}__initial.json')
            link = input(f'{Fore.LIGHTYELLOW_EX}Enter link{Fore.RESET}: ').strip().replace('https://www.pornhub.org', '')
            link = link if link[0] == '/' else ('/' + link)

            if 'viewkey=' in link:
                data = {'videos': [{'url': link}]}
            else:
                data = await extract_videos_from_webpage(QUERY_SEM, session, link)
            save_data(data, temp)
            
            download_dir = os.path.join(DOWNLOAD_DIR, datetime.now().strftime('%Y_%m_%d'))
            new_data = await download_videos(QUERY_SEM, session, download_session, data, download_dir)

            data_path = os.path.join(DATA_DIR, f'{uuid4()}.json')
            save_data(new_data, data_path)

            if os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass
            
            if input(f'{Fore.LIGHTYELLOW_EX}Do you want to download another video/page?{Fore.RESET}: ').lower().strip() in ['no', 'nope', 'n', '', None]:
                break

if __name__ == "__main__":
    asyncio.run(main())
