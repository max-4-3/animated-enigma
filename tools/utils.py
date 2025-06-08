import os, json, asyncio, re, time
from rich import print
from pydantic import BaseModel
import pyperclip
from typing import Callable
from threading import Thread, Event, Lock


class ClipboardMonitor:
    def __init__(
        self,
        string_validation: Callable[[str], bool],
        prefix: str = "",
        poll_interval: float = 0.1,
    ):
        self.string_validation = string_validation
        self.prefix = prefix.strip()
        self.poll_interval = poll_interval
        self.collected = set()
        self._stop_event = Event()
        self._lock = Lock()
        self._thread = Thread(target=self._monitor, daemon=True)

    def __enter__(self):
        print(
            f"[bold green]{self.prefix} 📋 Clipboard monitoring started. Press [red]Ctrl+C[/red] to stop.[/bold green]"
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def stop(self):
        self._stop_event.set()
        self._thread.join()
        print(
            f"\n[bold green]🛑 Monitoring stopped. {len(self.collected)} unique item(s) collected.[/bold green]"
        )

    def get_collected(self) -> list[str]:
        with self._lock:
            return list(self.collected)

    def _monitor(self):
        last_clip = ""
        while not self._stop_event.is_set():
            try:
                current = pyperclip.paste().strip()
                if current and current != last_clip:
                    last_clip = current
                    if self.string_validation(current):
                        with self._lock:
                            if current not in self.collected:
                                self.collected.add(current)
                                print(f"[cyan]➕ Added:[/cyan] [bold]{current}[/bold]")
                            else:
                                print(f"[yellow]⚠️ Duplicate (ignored):[/yellow]")
                    else:
                        print(f"[dim]❌ Skipped (did not pass validation):[/dim]")
                time.sleep(self.poll_interval)
            except Exception as e:
                print(f"[red]⚠️ Clipboard error: {e}[/red]")


def load_data(
    fp=os.path.join(os.path.split(os.path.split(__file__)[0])[0], "config.json")
):
    if not os.path.exists(fp):
        return "", "", asyncio.Semaphore(1), asyncio.Semaphore(2)

    with open(fp, "r", errors="ignore", encoding="utf-8") as file:
        data = json.load(file)
        DOWNLOAD_DIR = data.get("download_dir", None)
        if not DOWNLOAD_DIR:
            raise ValueError(f'Please Set Download PATH in "{fp}"')

        DOWNLOAD_DIR = (
            DOWNLOAD_DIR
            if not DOWNLOAD_DIR.startswith("~")
            else os.path.expanduser(DOWNLOAD_DIR)
        )
        DOWNLOAD_DIR = os.path.join(
            DOWNLOAD_DIR, os.path.split(os.path.split(__file__)[0])[1]
        )
        DATA_DIR = os.path.join(DOWNLOAD_DIR, "data")
        QUERY_SEM = asyncio.Semaphore(data.get("query_sem_limit", 2))
        DOWNLOAD_SEM = asyncio.Semaphore(data.get("download_sem_limit", 4))

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(DATA_DIR, exist_ok=True)

        return DOWNLOAD_DIR, DATA_DIR, QUERY_SEM, DOWNLOAD_SEM


def save_data(d, fp):
    with open(fp, "w", errors="ignore", encoding="utf-8") as file:
        data = None
        if isinstance(d, BaseModel):
            data = d.model_dump(mode="json")
        elif isinstance(d, list):
            data = []
            for obj in d:
                if isinstance(obj, BaseModel):
                    data.append(obj.model_dump(mode="json"))
                else:
                    data.append(obj)
        else:
            data = d
        try:
            json.dump(data, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f'Unable to save data to file "{fp}": {e}')


def clear():
    os.system("cls" if os.name.lower() in ["windows", "nt"] else "clear")


def read_until(
    starting_prompt: str,
    stop: str = "stop",
    url: bool = True,
    case_sensitive: bool = False,
    clear_screen: bool = True,
    exit_on_error: bool = True,
    validator: callable = lambda x: True,
    allow_duplicates: bool = False,
    reverse: bool = True,
) -> list[str]:
    """Read user input until stop command is entered.

    Args:
        starting_prompt: The prompt to display for each input
        stop: The command that stops the input collection
        url: If True, validates input starts with 'http'
        case_sensitive: If False, stop command comparison is case-insensitive
        clear_screen: If True, clears screen between inputs

    Returns:
        List of collected valid inputs
    """
    data = []
    stop_test = stop if case_sensitive else stop.lower()

    while True:
        try:
            if clear_screen:
                os.system("cls" if os.name == "nt" else "clear")

            print(f"[{len(data)}] {starting_prompt}\n" f'Type "{stop}" to stop: ')
            user_input = input().strip()

            # Check for stop command
            test_input = user_input if case_sensitive else user_input.lower()
            if test_input == stop_test:
                break

            # Validate input
            if not user_input:
                continue

            if not validator(user_input):
                print(
                    f"Invalid input [{user_input}] does not meet requirements\nPress Enter to continue..."
                )
                input("")
                continue

            if url and not user_input.startswith(("http://", "https://")):
                print(
                    f"Invalid URL - must start with http:// or https://\nPress Enter to continue..."
                )
                input("")
                continue

            if not allow_duplicates and user_input in data:
                print(f'Duplicates Not Wanted: "{user_input}" [already exists]')
                input("")
                continue

            data.append(user_input)
        except:
            if exit_on_error:
                break
            continue
    return data[::-1] if reverse else data


def format_elapsed_time(seconds: float) -> str:
    millis = int((seconds % 1) * 1000)
    total_seconds = int(seconds)

    days, total_seconds = divmod(total_seconds, 86400)
    hours, total_seconds = divmod(total_seconds, 3600)
    minutes, total_seconds = divmod(total_seconds, 60)
    secs = total_seconds

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")
    if millis or not parts:
        parts.append(f"{millis}ms")

    return " ".join(parts)


def format_bytes_readable(size: int) -> str:
    units = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB", 5: "PB"}

    if size < 1024:
        return f"{size} B"

    power = 0
    while size >= 1024 and power < len(units) - 1:
        size /= 1024
        power += 1

    return f"{size:.2f} {units[power]}"


def sanitize_filename(filename):
    """
    Sanitizes a filename for Windows by replacing restricted characters.
    """
    # Define restricted characters and their replacements
    restricted_chars = {
        "<": "_lt_",  # less than
        ">": "_gt_",  # greater than
        ":": "_",  # colon
        '"': "_",  # double quote
        "/": "_",  # forward slash
        "\\": "_",  # backslash
        "|": "_",  # vertical bar
        "?": "_",  # question mark
        "*": "_",  # asterisk
    }

    # Replace restricted characters
    for char, replacement in restricted_chars.items():
        filename = filename.replace(char, replacement)

    # Remove any trailing dots or spaces, which are not allowed in Windows filenames
    filename = filename.strip().rstrip(".")

    # Remove any control characters (ASCII 0-31)
    filename = re.sub(r"[\x00-\x1f]", "", filename)

    return filename


def is_user_quit() -> bool:
    print("Do you want to quit?: ")
    return input("").lower().strip() in ("yes", "y")

