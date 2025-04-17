import os, json, asyncio, re
from rich import print

def load_data(fp=os.path.join(os.path.split(os.path.split(__file__)[0])[0], 'config.json')):
    if not os.path.exists(fp):
        return "", "", asyncio.Semaphore(1), asyncio.Semaphore(2) 
    
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

        return DOWNLOAD_DIR, DATA_DIR, QUERY_SEM, DOWNLOAD_SEM

def save_data(d, fp):
    with open(fp, 'w', errors='ignore', encoding='utf-8') as file:
        try:
            json.dump(d, file, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f'Unable to save data to file "{fp}": {e}')

def clear():
    os.system('cls' if os.name.lower() in ['windows', 'nt'] else 'clear')

def read_until(
    starting_prompt: str,
    stop: str = "stop",
    url: bool = True,
    case_sensitive: bool = False,
    clear_screen: bool = True,
    exit_on_error: bool = True,
    validator: callable = lambda x: True,
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
                os.system('cls' if os.name == 'nt' else 'clear')
            
            user_input = input(
                f"[{len(data)}] {starting_prompt}\n"
                f"Type \"{stop}\" to stop: "
            ).strip()
            
            # Check for stop command
            test_input = user_input if case_sensitive else user_input.lower()
            if test_input == stop_test:
                return data
                
            # Validate input
            if (not user_input):
                continue
            
            if not validator(user_input):
                print(f"Invalid input [{user_input}] does not meet requirements")
                input("Press Enter to continue...\n")
                continue

            if url and not user_input.startswith(('http://', 'https://')):
                print(f"Invalid URL - must start with http:// or https://")
                input("Press Enter to continue...")
                continue
                
            data.append(user_input)
        except:
            if exit_on_error:
                return data
            continue

def sanitize_filename(filename):
    """
    Sanitizes a filename for Windows by replacing restricted characters.
    """
    # Define restricted characters and their replacements
    restricted_chars = {
        '<': '_lt_',  # less than
        '>': '_gt_',  # greater than
        ':': '_',     # colon
        '"': '_',     # double quote
        '/': '_',     # forward slash
        '\\': '_',    # backslash
        '|': '_',     # vertical bar
        '?': '_',     # question mark
        '*': '_',     # asterisk
    }

    # Replace restricted characters
    for char, replacement in restricted_chars.items():
        filename = filename.replace(char, replacement)

    # Remove any trailing dots or spaces, which are not allowed in Windows filenames
    filename = filename.strip().rstrip('.')

    # Remove any control characters (ASCII 0-31)
    filename = re.sub(r'[\x00-\x1f]', '', filename)

    return filename

def is_user_quit() -> bool:
    return input('Do you want to quit?: ').lower().strip() in ('yes', 'y')