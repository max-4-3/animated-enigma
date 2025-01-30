from extractors.video import extract_video_info
from extractors.page import extract_videos_from_webpage
from fake_useragent import UserAgent
from tqdm.asyncio import tqdm
from uuid import uuid4
from datetime import datetime
from colorama import Fore

import os, asyncio, aiohttp, json, aiofiles, shutil, time

DOWNLOAD_DIR = os.path.expanduser('~/Videos/Downloaders/okxxx/')
DATA_DIR = os.path.expanduser('~/Videos/Downloaders/okxxx/data')
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def save_data(d, fp):
    with open(fp, 'w') as file:
        try:
            json.dump(d, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f'Unable to save data to file "{fp}": {e}')

def clear():
    os.system('cls' if os.name.lower() in ['windows', 'nt'] else 'clear')

# async def download_video(sem, video_title, video_url, video_ext, download_dir):
#     async with sem:
#         os.makedirs(download_dir, exist_ok=True)

#         print(f"Downloading \"{video_title}\" in \"{download_dir}\"")
#         fullpath = os.path.join(download_dir, video_title + video_ext)
#         # Construct the ffmpeg command
#         log_level = '-loglevel'
#         command = [
#             "ffmpeg",
#             "-i", video_url,
#             "-hide_banner", '-y',
#             # log_level, 'info',
#             fullpath
#         ]

#         # Run the command asynchronously
#         try:
#             process = await asyncio.create_subprocess_exec(
#                 *command,
#                 stdout=asyncio.subprocess.PIPE,
#                 stderr=asyncio.subprocess.PIPE
#             )

#             with tqdm(desc='Frame Proccessed', unit='') as pbar:
#                 while True:
#                     line = await process.stderr.readline() or await process.stdout.readline()
#                     if not line:
#                         break
#                     line = line.decode()
                    
#                     if 'frame=' in line:
#                         frame = int(line.split('frame=')[1].split('fps=')[0].strip())
#                         pbar.update(frame - pbar.n)
                    
#                     pbar.refresh()

#             stdout, stderr = await process.communicate()

#             if process.returncode == 0:
#                 print(f"Download complete: {fullpath}")
#             else:
#                 print(f"Error occurred: \n{stderr.decode().strip() or stdout.decode().strip()}")
#             return os.path.getsize(fullpath) if os.path.exists(fullpath) else 0
#         except Exception as e:
#             print(f"Exception during download: {e}")
#             return 0

async def download_segment(sem, session: aiohttp.ClientSession, segment_url: str, download_dir: str, pbar: tqdm):
    async with sem:
        try:
            async with session.get(segment_url) as r:
                r.raise_for_status()
                segment_name = segment_url.split('/')[-1].split('?')[0]
                download_path = os.path.join(download_dir, segment_name)

                with tqdm(total=int(r.headers.get('content-length', 0)), unit='B', unit_scale=True, desc=f'\t|-> Downloading "{segment_name}"'.expandtabs(4), leave=False, position=1) as segment_pbar:
                    async with aiofiles.open(download_path, 'wb') as file:
                        while chunk := await r.content.read(1024 * 40):
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
        
        print(f'Parsing index...')
        async with session.get(video_url) as m3u8_r:
            m3u8_r.raise_for_status()
            raw = await m3u8_r.text()

            data = ''
            for line in raw.splitlines():
                if line.startswith('#'):
                    data += line
                else:
                    break
            
            base_url = video_url.rsplit('/', 1)[0]
            m3u8_urls = [((base_url if not l.startswith('https') else '') + l, l.split('/')[-1].split('?')[0]) for l in raw.splitlines() if l and not l.startswith('#')]
            print(f'{Fore.LIGHTRED_EX}{m3u8_urls.__len__()}{Fore.RESET} segements url found!')

        # Download all segments
        with tqdm(total=len(m3u8_urls), position=0, desc='Segment progress', unit='seg', colour='green') as pbar:
            tasks = []
            filenames = []
            for link, name in m3u8_urls:
                tasks.append(asyncio.create_task(download_segment(sem, session, link, temp_dir, pbar)))
                filenames.append(os.path.join(temp_dir, name))
            
            await asyncio.gather(*tasks)
    
        # Create the segmentInfo.txt file with correct formating
        segement_infofile = os.path.join(download_dir, f'{random_name}_seginfo.txt')
        with open(segement_infofile, 'w') as file:
            file.write('\n'.join([f'file \'{a.replace("\\", "/")}\'' for a in filenames if a])) # file 'c:\abs\path\segment.ts'
        
        # Concate (e.g. combine) all segments ( with abspath being compulsory )
        print(f'Concating segments...')
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

async def download_videos(sem, session: aiohttp.ClientSession, data: dict, root_download_path: str):
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
        full_info = await extract_video_info(sem, session, video['url'])
        new_videos.append(full_info)

        print(f'Downloading "{full_info['title']}"...')
        download_url = list(full_info['media'].values())[-1]['url']
        download_size, download_time = await download_video(sem, session, full_info['title'], download_url, '.mp4', download_dir)
        print(f'Completed Download in {download_time}s [{download_size / (1024**2):.2f}MB]')

        total_size += download_size
        total_time += download_time
        await asyncio.sleep(1)

    data['videos'] = new_videos
    data['total_download_size'] = total_size
    data['total_download_time'] = total_time
    return data

async def main():
    headers = {
        'User-Agent': UserAgent().random 
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        sem = asyncio.Semaphore(1)
        while True:
            clear()
            temp = os.path.join(f'{uuid4()}__initial.json')
            link = input(f'{Fore.LIGHTYELLOW_EX}Enter link{Fore.RESET}: ').strip()
            if 'video' in link:
                data = {'videos': [{'url': link}]}
            else:
                data = await extract_videos_from_webpage(sem, session, link)
            save_data(data, temp)
            
            download_dir = os.path.join(DOWNLOAD_DIR, datetime.now().strftime('%Y_%m_%d'))
            new_data = await download_videos(asyncio.Semaphore(2), session, data, download_dir)

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
