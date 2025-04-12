import aiohttp, asyncio, os, aiofiles, time, shutil, logging
from colorama import Fore
from uuid import uuid4
from tqdm import tqdm
from .consts import LOG_PATH, LOG_FORMAT, DATE_FORMAT


logging.basicConfig(
    filename=os.path.join(LOG_PATH, '.' + os.path.split(__file__)[1] + '.log'),
    filemode='a',
    level=logging.DEBUG,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT
)

Log = logging.getLogger(__name__)

async def download_segment(sem, session: aiohttp.ClientSession, segment_url: str, download_dir: str, pbar: tqdm):
    async with sem:
        try:
            Log.debug(f'GET: { segment_url = }; { download_dir = }')        
            segment_name = segment_url.split('/')[-1].split('?')[0] or segment_url.split("/")[-1]
            download_path = os.path.join(download_dir, segment_name)

            async with session.get(segment_url) as r:
                r.raise_for_status()
                Log.info(f'GET: { segment_url = } [{ r.status = }]')

                Log.debug(f'{ download_path = }; { segment_name = }')
                with tqdm(total=int(r.headers.get('content-length', 0)), unit='B', unit_scale=True, desc=f'\t|-> Downloading "{segment_name}"'.expandtabs(4), leave=False, position=1) as segment_pbar:
                    async with aiofiles.open(download_path, 'wb') as file:
                        while chunk := await r.content.read(1024 * 1024 * 40):
                            await file.write(chunk)
                            segment_pbar.update(len(chunk))

                Log.info(f'File Saved at { download_path = } under { segment_name = } [ {os.path.getsize(download_path) if os.path.exists(download_path) else 0} ]')
                await asyncio.sleep(0.1)
                pbar.update(1)

                return download_path
        except Exception as e:
            print(f'Unable to download segement "{Fore.RED}{segment_name}{Fore.RESET}"!')
            Log.error(f'[Download Segement Error] { e = }; { segment_name = }; { download_path = }; { segment_url = }')
            return ''

async def download_video(sem: asyncio.Semaphore, session: aiohttp.ClientSession, video_title: str, video_url: str, video_ext: str, download_dir: str, cleanup: bool = True, re_encode: bool = False, download_sem_limit: int = 4):
    async with sem:
        download_sem = asyncio.Semaphore(download_sem_limit)
        random_name = str(uuid4())
        start = time.perf_counter()

        download_dir = os.path.join(download_dir, 'videos')
        
        # File Setup
        temp_dir = os.path.join(download_dir, 'temp_' + random_name)
        segement_infofile = os.path.join(download_dir, f'{random_name}_seginfo.txt')
        output_file_temp = os.path.join(download_dir, random_name + '_' + video_title + video_ext)
        Log.debug(f'[File Setup] { temp_dir = }; { segement_infofile = }; { output_file_temp = }')

        os.makedirs(temp_dir, exist_ok=True)
        m3u8_urls = []
        
        try:
            Log.info(f'Parsing index for video: {video_title} [ { video_url = } ]')
            async with session.get(video_url) as m3u8_r:
                Log.debug(f'GET: {video_url} [{ m3u8_r.status = }; { m3u8_r.headers['content-type'] = }]')
                m3u8_r.raise_for_status()
                raw = await m3u8_r.text()

                data = ''
                for line in raw.splitlines():
                    if line.startswith('#'):
                        data += ('\n' if line[0] != '\n' else '') + line

                # Remove trailing slash if present
                base_url = video_url.rsplit('/', 1)[0].rstrip('/')
                m3u8_urls = []

                for i, line in enumerate(raw.splitlines(), start=1):
                    if not line or line.startswith('#'):
                        # Only log skipped lines if debugging
                        Log.debug(f'Skipping line {i}: Empty or comment')
                        continue
                    
                    # Handle segment link construction
                    if line.startswith(('http://', 'https://')):
                        segment_full_link = line
                    else:
                        segment_full_link = f"{base_url}/{line.lstrip('/')}"
                    
                    segment_name = segment_full_link.split('/')[-1].split('?')[0] or segment_full_link.split("/")[-1]
                    
                    Log.debug(f'Adding segment {i}: {segment_name} from {segment_full_link}')
                    m3u8_urls.append((segment_name, segment_full_link))

                Log.info(f'{len(m3u8_urls)} segments url found for video: {video_title}')

            # Download all segments
            with tqdm(total=len(m3u8_urls), position=0, desc='Segment progress', unit='seg', colour='green') as pbar:
                tasks = []
                filenames = []
                for name, link in m3u8_urls:
                    tasks.append(asyncio.create_task(download_segment(download_sem, session, link, temp_dir, pbar)))
                    filenames.append(os.path.join(temp_dir, name))

                await asyncio.gather(*tasks)

            # Create the segmentInfo.txt file with correct formating
            with open(segement_infofile, 'w') as file:
                file.write('\n'.join([f'file \'{a.replace("\\", "/")}\'' for a in filenames if a])) # file 'c:\abs\path\segment.ts'

            # Concate (e.g. combine) all segments ( with abspath being compulsory )
            command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', os.path.abspath(segement_infofile), '-c', 'copy', '-y', '-hide_banner', '-loglevel', 'error', '-fflags', '+genpts', os.path.abspath(output_file_temp)]
            Log.info(f'Concating segments for video: {video_title} [{ command = }]')
            proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            _, stderr = await proccess.communicate()

            if proccess.returncode != 0:
                Log.error(f'Error occurred during concat for video {video_title}: {stderr.decode()}')
                raise OSError('Unable to Concate file!')
            else:
                Log.info(f'Concat successful for video: {video_title}')

            # Re-encode for smoother playback if 're_encode'
            output_file = os.path.join(download_dir, video_title + video_ext)
            if re_encode:
                command = ['ffmpeg', '-i', output_file_temp, '-hide_banner', '-c:v', 'libx264', '-vf', '"format=yuv420p"', '-preset', 'fast', '-c:a', 'aac', '-b:a', '192k', output_file]
                Log.info(f'Re-encoding video: {video_title} [ { command = } ]')
                proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
                _, stderr = await proccess.communicate()

                if proccess.returncode != 0:
                    Log.error(f'Error occurred during re-encoding for video {video_title}: {stderr.decode()}')
                else:
                    Log.info(f'Re-encoding successful for video: {video_title}')
            else:
                os.rename(output_file_temp, output_file)

        except Exception as e:
            Log.error(f'Error processing video {video_title}: {str(e)}')
            raise
        finally:
            # Cleanup the temp files if 'cleanup'
            if cleanup and os.path.exists(os.path.join(download_dir, video_title + video_ext)):
                Log.info(f'Cleaning temp files for video: {video_title}')
                try:
                    shutil.rmtree(temp_dir, True)
                    os.remove(segement_infofile)
                    if os.path.exists(output_file_temp):
                        os.remove(output_file_temp)
                    Log.info(f'Cleanup successful for video: {video_title}')
                except Exception as e:
                    Log.error(f'Error occurred during cleanup for video {video_title}: {e}')
            else:
                Log.info(f'Skipping cleaning temp files for video: {video_title}')

        end = time.perf_counter()
        duration = round(end - start, 2)
        file_size = os.path.getsize(output_file) if os.path.exists(output_file) else 0
        Log.info(f'Completed processing video: {video_title} | Size: {file_size} bytes | Took: {duration} seconds')
        return file_size, duration