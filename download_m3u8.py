import aiofiles
import aiohttp
import asyncio
import os
import json, time
from uuid import uuid4
from tqdm.asyncio import tqdm
from fake_useragent import UserAgent

total = 0

def save_data(d, fp):
    with open(fp, 'w', errors='ignore', encoding='utf-8') as file:
        json.dump(d, file, indent=4, ensure_ascii=False)

async def concat_segments(file_lists, save_path, save_name):
    os.makedirs(save_path, exist_ok=True)

    # Save final concatenated file
    filepath = os.path.join(save_path, save_name)

    # Create a temporary file for the list of segments
    temp_concate_file = os.path.join(save_path, f'temp_concate_file_{uuid4()}.txt')
    with open(temp_concate_file, 'w', errors='ignore') as file:
        file.write('\n'.join([f'file \'{os.path.abspath(f)}\'' for f in file_lists if os.path.exists(f)]))

    # Command for concatenation using ffmpeg
    command = [
        'ffmpeg', '-f', 'concat', '-safe', '0', '-i', temp_concate_file,
        '-hide_banner', '-fflags', '+genpts', '-movflags', '+faststart', '-c', 'copy', filepath
    ]

    # Run the ffmpeg command asynchronously
    process = await asyncio.create_subprocess_exec(
        *command,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

    # Monitor process output for progress
    while True:
        line = await process.stderr.readline()
        if not line:
            break

        line = line.decode('utf-8', errors='ignore')
        if 'frame=' in line or 'size=' in line or 'time=' in line:
            print(line.strip(), end='\r')  # Display progress in place

    # Wait for the process to finish
    _, stderr = await process.communicate()
    print()

    # Handle process exit
    if process.returncode != 0:
        print(f'Unable to concatenate segments: {stderr.decode()}')
    else:
        print(f'Concatenation successful!\nFile saved at: {filepath}')

    # Clean up the temporary file
    try:
        os.remove(temp_concate_file)
        for file in file_lists:
            if not os.path.exists(file):
                continue
            else:
                try:
                    os.remove(file)
                except:
                    pass
    except OSError as e:
        print(f"Warning: Unable to delete temp file: {e}")

async def download_segment(sem, session: aiohttp.ClientSession, url, name, path, top_level_bar: tqdm, **kwargs):
    async with sem:
        global total
        try:
            async with session.get(url, **kwargs) as r:
                r.raise_for_status()
                file_path = os.path.join(path, name)
                async with aiofiles.open(file_path, 'wb') as file:
                    async for chunk in r.content.iter_chunked(1024 * 1024 * 10):  # 10 MB chunks
                        await file.write(chunk)
                        total += len(chunk)
                        top_level_bar.set_postfix_str(f'Downloaded: {total / (1024**2):.2f}MB', refresh=True)
                top_level_bar.update(1)
                return (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        except Exception as e:
            print(f'Unable to download "{name}": {e}')
            return 0

async def download(session, index_url, path):
    url_list = []
    name_list = []
    seg_path = os.path.join(path, "segments")
    os.makedirs(seg_path, exist_ok=True)

    async with session.get(index_url) as r:
        r.raise_for_status()
        data = await r.text()

    count = 1
    for line in data.splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        url = line if line.startswith('http') else f"{index_url.rsplit('/', 1)[0]}/{line}"
        url_list.append(url)
        name_list.append(f'segment-{count}.ts')
        count += 1

    print(f"Found {len(url_list)} segments")

    bar_format = "[{n}/{total}] {desc}: |{bar}| {percentage:3.0f}% ({rate_fmt}{postfix})"
    sem = asyncio.Semaphore(4)
    start = time.perf_counter()
    with tqdm(total=len(url_list), desc='Downloading', unit='seg', position=0, colour='blue', bar_format=bar_format) as bar:
        tasks = [asyncio.create_task(download_segment(sem, session, url, name, seg_path, bar)) for name, url in zip(name_list, url_list)]
        sizes = await asyncio.gather(*tasks)
    end = time.perf_counter()
    total_size = sum(sizes)

    files = [k for k in name_list if os.path.exists(os.path.join(seg_path, k))]

    # Save segment_info.txt for cancation
    segment_info = os.path.join(path, f'{uuid4()}_segement_info.txt')
    if input('Segements downloaded!\nConcate them?: ').lower().strip() in ['no', 'n']:
        with open(segment_info, 'w', errors='ignore', encoding='utf-8') as file:
            file.write('\n'.join([f'file \'{os.path.abspath(f)}\'' for f in files]))
    else:
        await concat_segments(files, os.path.expanduser('~/Videos/Movies/'), f'{uuid4()}.mp4')

    print(f'Total downloaded size: {total_size / (1024 ** 2):.2f} MB [{end - start:.2f}s]')
    print(f'File list saved at "{os.path.abspath(segment_info)}"')

async def main():
    async with aiohttp.ClientSession(headers={'User-Agent': UserAgent().random}) as session:
        while True:
            index_url = input('Enter "index.m3u8" URL (or "exit" to quit): ')
            if index_url.lower() == "exit":
                break
            await download(session, index_url, os.path.expanduser("~/Downloads/Playlist/hls"))

if __name__ == "__main__":
    asyncio.run(main())
