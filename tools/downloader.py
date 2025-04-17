import aiohttp, asyncio, argparse, os, sys, aiofiles, time, shutil, logging, re, random
from colorama import Fore
from uuid import uuid4
from tqdm import tqdm
from datetime import datetime
from typing import Any

try:
    from .consts import LOG_FORMAT, LOG_PATH, DATE_FORMAT
    from .utils import sanitize_filename
except:
    def sanitize_filename(a): return a
    LOG_PATH = os.path.join(os.getcwd(), "logs")
    LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [PID:%(process)d] [%(threadName)s] [%(funcName)s@%(filename)s:%(lineno)d] - %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up loggers for different tasks
def setup_task_loggers():
    os.makedirs(LOG_PATH, exist_ok=True)
    
    now = datetime.now()
    date_suffix = f"{now.month:02d}-{now.day:02d}-{now.year:02d}"
    
    # Main logger (keep your existing one)
    main_logger = logging.getLogger(__name__)
    main_handler = logging.FileHandler(
        os.path.join(LOG_PATH, os.path.split(__file__)[1] + f"-{date_suffix}.log")
    )
    main_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    main_logger.addHandler(main_handler)
    main_logger.setLevel(logging.DEBUG)
    
    # Logger for gathering segments
    gather_logger = logging.getLogger("gathering_segments")
    gather_handler = logging.FileHandler(
        os.path.join(LOG_PATH, f"gathering-segments-{date_suffix}.log")
    )
    gather_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    gather_logger.addHandler(gather_handler)
    gather_logger.setLevel(logging.DEBUG)
    
    # Logger for downloading segments
    download_logger = logging.getLogger("downloading_segments")
    download_handler = logging.FileHandler(
        os.path.join(LOG_PATH, f"downloading-segments-{date_suffix}.log")
    )
    download_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    download_logger.addHandler(download_handler)
    download_logger.setLevel(logging.DEBUG)
    
    # Logger for concatenating segments
    concat_logger = logging.getLogger("concatenating_segments")
    concat_handler = logging.FileHandler(
        os.path.join(LOG_PATH, f"concatenating-segments-{date_suffix}.log")
    )
    concat_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    concat_logger.addHandler(concat_handler)
    concat_logger.setLevel(logging.DEBUG)
    
    return main_logger, gather_logger, download_logger, concat_logger

# Initialize loggers at module level
Log, GatherLog, DownloadLog, ConcatLog = setup_task_loggers()

# Then in your functions, use the appropriate logger:
async def download_segment(sem, session: aiohttp.ClientSession, segment_url: str, download_dir: str, pbar: tqdm, retry_limit: int = 5, fixed_backoff: int | float = 2.0):
    async with sem:
        try:
            DownloadLog.debug(f'GET: { segment_url = }; { download_dir = }')        
            segment_name = segment_url.split('/')[-1].split('?')[0] or segment_url.split("/")[-1]
            download_path = os.path.join(download_dir, segment_name)

            is_succesfull = False
            for i in range(1, retry_limit + 1):
                try:
                    async with session.get(segment_url) as r:
                        r.raise_for_status()
                        DownloadLog.info(f'GET: { segment_url = } [{ r.status = }]')

                        DownloadLog.debug(f'{ download_path = }; { segment_name = }')
                        with tqdm(total=int(r.headers.get('content-length', 0)), unit='B', unit_scale=True, desc=f'\t|-> Downloading "{segment_name}"'.expandtabs(4), leave=False, position=1) as segment_pbar:
                            async with aiofiles.open(download_path, 'wb') as file:
                                while chunk := await r.content.read(1024 * 1024 * 40):
                                    await file.write(chunk)
                                    segment_pbar.update(len(chunk))

                        DownloadLog.info(f'File Saved at { download_path = } under { segment_name = } [ {os.path.getsize(download_path) if os.path.exists(download_path) else 0} ]')
                        await asyncio.sleep(0.1)
                        pbar.update(1)

                        is_succesfull = True
                        return download_path
                except Exception as e:
                    retry_after = fixed_backoff * i + random.random()
                    status = getattr(r, "status", "N/A")
                    DownloadLog.error(f'[Failed] GET: { segment_url = } [{status}] [exception = {e}] [{ retry_after = }; { retry_limit - i =  }]')
                    await asyncio.sleep(retry_after)

            if not is_succesfull:
                raise aiohttp.ServerConnectionError(f'Unable to Retrive Data from {segment_url}!')

        except Exception as e:
            print(f'Unable to download segement "{Fore.RED}{segment_name}{Fore.RESET}"!')
            DownloadLog.error(f'[Download Segement Error] { e = }; { segment_name = }; { download_path = }; { segment_url = }')
            return ''

async def download_video(sem: asyncio.Semaphore, session: aiohttp.ClientSession, video_title: str, video_url: str, video_ext: str, download_dir: str, cleanup: bool = True, re_encode: bool = False, download_sem_limit: int = 4, make_subfolder: bool = True, subfoler_name: str = "videos"):
    async with sem:
        video_title = sanitize_filename(video_title)
        download_sem = asyncio.Semaphore(download_sem_limit)
        random_name = str(uuid4())
        start = time.perf_counter()

        if make_subfolder:
            download_dir = os.path.join(download_dir, 'videos' if subfoler_name is None else subfoler_name)

        # File Setup
        temp_dir = os.path.join(download_dir, 'temp_' + random_name)
        segement_infofile = os.path.join(download_dir, f'{random_name}_seginfo.txt')
        output_file_temp = os.path.join(download_dir, random_name + '_' + video_title + video_ext)
        Log.debug(f'[File Setup] { temp_dir = }; { segement_infofile = }; { output_file_temp = }')

        os.makedirs(temp_dir, exist_ok=True)
        m3u8_urls = []
        
        try:
            GatherLog.info(f'Parsing index for video: {video_title} [ { video_url = } ]')
            async with session.get(video_url) as m3u8_r:
                GatherLog.debug(f'GET: {video_url} [{ m3u8_r.status = }; { m3u8_r.headers['content-type'] = }]')
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
                        GatherLog.debug(f'Skipping line {i}: Empty or comment')
                        continue
                    
                    # Handle segment link construction
                    if line.startswith(('http://', 'https://')):
                        segment_full_link = line
                    else:
                        segment_full_link = f"{base_url}/{line.lstrip('/')}"
                    
                    segment_name = segment_full_link.split('/')[-1].split('?')[0] or segment_full_link.split("/")[-1]
                    
                    GatherLog.debug(f'Adding segment {i}: {segment_name} from {segment_full_link}')
                    m3u8_urls.append((segment_name, segment_full_link))

                GatherLog.info(f'{len(m3u8_urls)} segments url found for video: {video_title}')

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
                file.write('\n'.join([f'file \'{a.replace("\\", "/")}\'' for a in filenames if a]))

            # Concate (e.g. combine) all segments
            command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', os.path.abspath(segement_infofile), '-c', 'copy', '-y', '-hide_banner', '-loglevel', 'debug', '-fflags', '+genpts', os.path.abspath(output_file_temp)]
            ConcatLog.info(f'Concating segments for video: {video_title} [{ command = }]')
            proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)

            # Progress bar
            total_files = len([file for file in open(segement_infofile, 'r').read().splitlines() if file.startswith('file')])
            line_match_pattern = re.compile(r'\[concat\s+?@\s+?(\w)+\]\s+?file:(\d+)\s+?stream:\d+?\s+?pts:\d+\s+?')

            with tqdm(total=total_files, desc='Concatenating', unit='file', unit_divisor=10, unit_scale=False) as concate_bar:
                while True:
                    line = await proccess.stderr.readline()
                    if not line:
                        break

                    line_match = line_match_pattern.match(line.decode(errors='ignore'))
                    if line_match:
                        try:
                            file_no = int(line_match.group(2)) - concate_bar.n
                            ConcatLog.debug(f'[Concat] Concatenated {file_no} file [raw = {line.decode(errors='ignore').replace('\n', '\\n')}]')
                            concate_bar.update(file_no + 1)
                        except Exception as e:
                            ConcatLog.error(f'Unable to gather file no from "{line.decode(errors='ignore').replace('\n', '\\n')}": {e}')
                            concate_bar.update(1)

            await proccess.wait()

            if proccess.returncode != 0:
                ConcatLog.error(f'Error occurred during concat for video {video_title}: \n{(await proccess.stderr.read()).decode(errors='ignore')[:-200]}\n')
                raise OSError('Unable to Concate file!')
            else:
                ConcatLog.info(f'Concat successful for video: {video_title}')

            # Re-encode for smoother playback if 're_encode'
            output_file = os.path.join(download_dir, video_title + video_ext)
            if re_encode:
                command = ['ffmpeg', '-i', output_file_temp, '-hide_banner', '-c:v', 'libx264', '-vf', '"format=yuv420p"', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k', output_file]
                ConcatLog.info(f'Re-encoding video: {video_title} [ { command = } ]')
                proccess = await asyncio.create_subprocess_exec(*command, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
                _, stderr = await proccess.communicate()

                if proccess.returncode != 0:
                    ConcatLog.error(f'Error occurred during re-encoding for video {video_title}: {stderr.decode()}')
                else:
                    ConcatLog.info(f'Re-encoding successful for video: {video_title}')
            else:
                if not os.path.exists(output_file):
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

def parse_arguments() -> list[str | Any | None]:
    if len(sys.argv) == 1:  # No Arguments Given
        raise ValueError(
            'Insufficient Arguments!\n'
            'Args: <url> [video_name(def = untitled_video)] [video_ext(def = mp4)] '
            '[download_dir(def = cwd)] [sub_dir(def = None; None = no dir will be made)]\n'
            '<> = Required; [] = Optional'
        )

    # Check if any -- or - options were used
    if any(arg.startswith('-') for arg in sys.argv[1:]):
        parser = argparse.ArgumentParser(description="Video downloader arguments")
        parser.add_argument("url", help="Video URL")
        parser.add_argument("-t", "--video-title", default="untitled_video", help="Title of the video")
        parser.add_argument("-e", "--ext", default="mp4", help="Video extension")
        parser.add_argument("-d", "--download-dir", default=os.getcwd(), help="Download directory")
        parser.add_argument("-s", "--subfolder-name", default=None, help="Optional subfolder name")

        args = parser.parse_args()
        return [args.url, args.video_title, args.ext, args.download_dir, args.subfolder_name]
    
    # Fallback: classic positional argument mode
    def try_to_get(index: int, default = None):
        try:
            value = sys.argv[index]
            return value if value.strip() else default
        except IndexError:
            return default
    
    return [
        try_to_get(1),
        try_to_get(2, "untitled_video"),
        try_to_get(3, "mp4"),
        try_to_get(4, os.getcwd()),
        try_to_get(5, None)
    ]

async def main():
    async with aiohttp.ClientSession() as session:
        sem = asyncio.Semaphore(18)
        args = parse_arguments()

        if any(arg in ["", " ", None] for arg in args[:-1]):
            raise ValueError(f'Some values are None: {args}')

        print(f"video_url: {args[0]}, video_title: {args[1]}, video_ext: {args[2]}, download_dir: {args[3]}, make_subfolder: {args[4] is not None}, sub_foldername: {args[4]}")
        await download_video(
            sem = sem,
            session = session,
            video_url = args[0],
            video_title = args[1],
            video_ext = args[2],
            download_dir = args[3],
            make_subfolder = args[4] is not None,
            subfoler_name = args[4]
        )

if __name__ == "__main__":
    asyncio.run(main())
