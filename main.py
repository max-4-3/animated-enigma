import asyncio, os, re, time, threading
from rich import print
from uuid import uuid4
from aiohttp import ClientSession
from datetime import datetime
from typing import Callable, List

from extractors.models import ThumbVideo, Video, Media, MediaItem
from tools.utils import clear, read_until, format_bytes_readable, save_data, is_user_quit, sanitize_filename, format_elapsed_time, ClipboardMonitor
from tools.downloader import download_video, download_video_with_ffmpeg, add_thumbnail
from config import *

async def user_input_proccesser(page_parser: Callable, page_link_validator: Callable, video_link_validator: Callable, print_first: str = None, prefix: str = "") -> List[ThumbVideo]:
    print(print_first if print_first else f"{prefix} Enter link [\"list\" for multiple links]:", end="")
    userinput = input("").lower().strip()

    if not userinput:
        raise ValueError('Enter a value!')
    
    if userinput in ['exit', 'stop']:
        raise StopIteration

    if userinput == "list":
        return [ThumbVideo(url = url) for url in read_until(f"{prefix} Enter Only Video Links:", validator=video_link_validator)]

    elif video_link_validator(userinput):
        return [ThumbVideo( url = userinput)]

    elif page_link_validator(userinput):
        return await page_parser(userinput)
    
    else:
        raise Exception('Invalid Input Passed: {}'.format(userinput))

def get_highest_media_dict(media_dict: Media) -> MediaItem | None:
    try:
        highest_key = max(
            [(index, int(re.sub(r'\D', '', str(item.resolution).strip()))) for index, item in enumerate(media_dict.items)],
            key=lambda x: x[1]
        )[0]
        return media_dict.items[highest_key]
    except Exception:
        return None

async def download_videos(
    sem,
    session,
    videos: list[ThumbVideo],
    extract_details_func: Callable,
    root_download_path: str,
    *,
    name_suffix: str = "",
    get_media_dict_func: Callable = None,
    pre_meida_url_func: Callable = None,
    max_retries: int = 3,
    download_retries: int = 1,
    backoff_base: float = 2.0,
    download_session: ClientSession = None,
    skip_custom_downloader: bool = False,
    thumbnail_url_extract_func: Callable = None
):
    os.makedirs(root_download_path, exist_ok=True)
    name_suffix = "[ " + re.sub(r'\s{2,}', ' ', re.search(r"[\w+\s]+", name_suffix or os.path.basename(root_download_path)).group(0)).strip() + " ]"

    print(f'[bold green]Downloading {len(videos)} videos to:[/bold green] "[cyan]{os.path.abspath(root_download_path)}[/cyan]"')

    new_videos, videos_failed = [], []
    total_size = total_time = 0

    for idx, video in enumerate(videos, 1):
        clear()

        video_id = video.url.rstrip("/").split("/")[-1]
        print(f'[bold]{idx}/{len(videos)}[/bold] Extracting: [yellow]{video_id}[/yellow]')

        try:
            video_extracted = None
            for attempt in range(1, max_retries + 1):
                try:
                    print(f'[blue]🔍 Attempt {attempt}: Extracting video details...[/blue]')
                    video_extracted: Video = await extract_details_func(sem, session, video.url)
                    if not video_extracted:
                        raise ValueError("No details extracted")
                    break  # Success
                except Exception as e:
                    print(f'[red]⚠ Extract failed: {e}[/red]')
                    if attempt < max_retries:
                        wait = backoff_base ** attempt
                        print(f'[yellow]↻ Retrying extraction in {wait:.2f}s...[/yellow]')
                        await asyncio.sleep(wait)
                    else:
                        print('[red]❌ Max retries reached for extraction. Skipping video.[/red]')
                        video_extracted = None

            if not video_extracted:
                print(f'[red]❌ Extraction failed[/red]')
                videos_failed.append(video)
                continue

            json_path = os.path.join(INITIAL_PATH, sanitize_filename(video_extracted.title)[:80] + name_suffix + '.json')
            save_data(video_extracted, json_path)
            videos_failed.append(video_extracted)

            print(f'[green]✅ Info gathered![/green] Downloading: [italic cyan]{video_extracted.title}[/italic cyan]')

            media = (
                get_media_dict_func(video_extracted) if get_media_dict_func
                else get_highest_media_dict(video_extracted.media)
            )
            if not media:
                print(f'[red]❌ Unable to retrieve media dict[/red]')
                continue

            download_url = media.url
            if not download_url.startswith('http'):
                print(f'[red]❌ Invalid media URL:[/red] [yellow]{download_url}[/yellow]')
                continue

            if pre_meida_url_func:
                print(f'[blue]» Initilizing media url...[/blue]')
                download_url = await pre_meida_url_func(session=session if not isinstance(download_session, ClientSession) else download_session, url = download_url)

            if skip_custom_downloader:
                print(f'[blue]▶ Using ffmpeg...[/blue]')
                size_downloaded, time_taken, output_file = await download_video_with_ffmpeg(
                    sem, video_extracted.title,
                    download_url, '.mp4', root_download_path
                )
            else:
                for attempt in range(1, download_retries + 1):
                    try:
                        print(f'[blue]▶ Attempt {attempt}: Using custom downloader...[/blue]')
                        size_downloaded, time_taken, output_file = await download_video(
                            sem, session if not isinstance(download_session, ClientSession) else download_session, video_extracted.title,
                            download_url, '.mp4', root_download_path, cleanup=True
                        )
                        break  # success
                    except Exception as e:
                        print(f'[red]⚠ Custom download failed: {e}[/red]')
                        if attempt < max_retries:
                            wait = backoff_base ** attempt
                            print(f'[yellow]↻ Retrying in {wait:.2f}s...[/yellow]')
                            await asyncio.sleep(wait)
                        else:
                            print('[blue]↪ Falling back to ffmpeg...[/blue]')
                            for ff_attempt in range(1, max_retries + 1):
                                try:
                                    print(f'[blue]▶ Attempt {ff_attempt}: Using ffmpeg...[/blue]')
                                    size_downloaded, time_taken, output_file = await download_video_with_ffmpeg(
                                        sem, video_extracted.title,
                                        download_url, '.mp4', root_download_path
                                    )
                                    break
                                except Exception as e:
                                    print(f'[red]❌ ffmpeg failed: {e}[/red]')
                                    if ff_attempt < max_retries:
                                        wait = backoff_base ** ff_attempt
                                        print(f'[yellow]↻ Retrying in {wait:.2f}s...[/yellow]')
                                        await asyncio.sleep(wait)
                                    else:
                                        raise Exception("All methods failed")

            if thumbnail_url_extract_func:
                thumbnail_url = thumbnail_url_extract_func(video_extracted)
                if not thumbnail_url:
                    continue
                print(f'[green]▶ Adding Thumbnail...')
                await add_thumbnail(sem, session if not isinstance(download_session, ClientSession) else download_session, thumbnail_url, output_file) 
            
            total_size += size_downloaded
            total_time += time_taken
            videos_failed.pop(-1)
            new_videos.append(video_extracted)

        except KeyboardInterrupt:
            if is_user_quit():
                break
        except Exception as e:
            print(f'[red bold]❌ Unexpected error: {e}[/red bold]')
            print("[dim]Press enter to continue...[/dim]")
            input("")
        finally:
            await asyncio.sleep(0.02 * idx)

    print(f'\n[bold green]✔ Completed:[/bold green] {len(new_videos)} downloaded')
    if videos_failed:
        print(f'[bold red]✘ Failed:[/bold red] {len(videos_failed)} videos')
        fail_file = os.path.join(
            INITIAL_PATH, datetime.now().strftime(r'%d-%m-%Y %H.%M.%S') +
            "-Videos-Failed-" + name_suffix + ".json"
        )
        save_data(videos_failed, fail_file)
        print(f'[yellow]Saved failed video info to:[/yellow] {fail_file}')

    print(f'[bold cyan]⏱ Total time:[/bold cyan] {format_elapsed_time(total_time)}')
    print(f'[bold cyan]💾 Total data:[/bold cyan] {format_bytes_readable(total_size)}')
    return new_videos

async def okxxx_handler():

    from extractors.okxxx import is_page_link, is_video_link, make_session
    from extractors.okxxx.page import extract_videos_from_webpage
    from extractors.okxxx.video import extract_video_info

    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                urls = await user_input_proccesser(
                    extract_videos_from_webpage,
                    is_page_link,
                    is_video_link,
                    prefix="[OKXXX]"
                )

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, extract_details_func=extract_video_info, root_download_path=os.path.join(DOWNLOAD_PATH, 'okxxx'), thumbnail_url_extract_func=lambda info: info.thumbnail.url)
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def pornhub_handler():
    from extractors.pornhub import is_page_link, is_video_link, make_session
    from extractors.pornhub.page import extract_videos_from_webpage
    from extractors.pornhub.video import extract_video

    async def get_index_url(*_, **kwargs):
        a = kwargs.get('url')
        ses = kwargs.get('session')
        async with ses.get(a) as m3u8_r:
            m3u8_r.raise_for_status()
            raw = await m3u8_r.text()
            first_non_comment_line = [line for line in raw.splitlines() if not line.startswith("#")]

            if len(first_non_comment_line) < 1:
                raise ValueError('Unable to Extracr Index.m3u8!')

            path_url = first_non_comment_line[0]
            index_url = '/'.join(a.split('/')[:-1]).rstrip('/') + "/" + path_url.lstrip('/')
            return index_url

    from fake_useragent import UserAgent
    async with make_session() as session, ClientSession(headers={'User-Agent':UserAgent().random }) as download_session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                urls = await user_input_proccesser(
                    extract_videos_from_webpage,
                    is_page_link,
                    is_video_link,
                    prefix="[PORNHUB]"
                )

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, extract_video, os.path.join(DOWNLOAD_PATH, 'pornhub'), pre_meida_url_func=get_index_url, download_session=download_session, thumbnail_url_extract_func=lambda info: info.thumbnail.url)
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def xnxx_handler():
    from extractors.xnxx import is_page_link, is_video_link, make_session
    from extractors.xnxx.video import extract_video_info
    from extractors.xnxx.page import get_videos_from_webpage
    
    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                urls = await user_input_proccesser(
                    get_videos_from_webpage,
                    is_page_link,
                    is_video_link,
                    prefix="[XNXX]"
                )

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, extract_video_info, os.path.join(DOWNLOAD_PATH, 'xnxx'), thumbnail_url_extract_func=lambda info: info.thumbnail.url)
                    save_data(new_data, temp)
                except Exception as e:
                    print(f'Download Error: {e}')

                if is_user_quit():
                    return
                
            finally:
                if os.path.exists(temp):
                    os.remove(temp)

async def xhamster_handler():
    from extractors.xhamster import is_video_link, is_page_link, is_valid_link, make_session
    from extractors.xhamster.page import extract_videos_from_webpage
    from extractors.xhamster.video import extract_video_info
    
    def get_media_func(full_info):
        return full_info.get('sources', {}).get("hls", {}).get("av1", None) or full_info.get('sources', {}).get("hls", {}).get("h264", None) or {}

    async def get_max_url(**kwargs):
        url = kwargs.get('url')
        max_res = max([int(re.sub(r'\D', '', "".join(res.split(':')[1:]))) for res in url.split('multi=')[1].split('/')[0].split(',') if res])
        return url.replace("_TPL_", f"{max_res}p")

    async with make_session() as session:
        while True:
            clear()
            temp = os.path.join(INITIAL_PATH, f'{uuid4()}__initial.json')
            try:
                print("Enter link [\"list\" for multiple links]: ", end='')
                ui = input('').strip()
                
                if ui.lower().strip() == "list":
                    urls = [{'pageUrl': url} for url in read_until('Enter link', validator=is_video_link)]
                elif ui.lower().strip() == "exit":
                    return
                elif is_video_link(ui):
                    urls = [{'pageUrl': ui}]
                elif is_page_link(ui):
                    urls = await extract_videos_from_webpage(QUERY_SEM, session, ui.strip())
                elif not is_valid_link(ui):
                    raise ValueError(f'Invalid Url! [{ ui = }]')

                try:
                    new_data = await download_videos(QUERY_SEM, session, urls, extract_video_info, os.path.join(DOWNLOAD_PATH, 'xhamster'), get_media_dict_func=get_media_func, url_key="pageUrl", pre_meida_url_func=get_max_url, thumbnail_url_extract_func=lambda info: info.get('thumbBig', None))
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
        'okxxx': okxxx_handler,
        # 'xhamster': xhamster_handler  # Currently Not Fixed this one...
    }

    while True:
        clear()
        print('\n'.join(f"{i}. {name}" for i, name in enumerate(available_domains.keys(), start=1)))
        print('Choose from above: ', end='')
        userinput = input('')

        if userinput.lower().strip() == 'exit':
            return

        key = None
        try:
            key = list(available_domains.keys())[int(userinput.strip().lower()) - 1]
            handler = available_domains.get(key)
            if not handler:
                raise NotImplementedError(f'Downloader for \"{userinput}\" is not implemented!')

            await handler()
        except Exception as e:
            print('Error', e)
        finally:
            print("Press enter to continue...")
            input("")

if __name__ == "__main__":
    asyncio.run(main())
