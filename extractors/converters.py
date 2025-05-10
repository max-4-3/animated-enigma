import re
from . import VIEWS_MAP
from functools import lru_cache

@lru_cache(maxsize=512)
def convert_views(views_string: str) -> int:
    # Find and searches the abbervative
    if isinstance(views_string, (int, float)):
        return int(views_string)

    abb = re.search('[A-Za-z]', views_string)
    if not abb:
        return int(0.0)
    
    abb = abb.group(0)
    # Convert the string into all number string
    views_string = float(re.sub(r'[A-Za-z \-]', '', views_string) or 0.0)
    return int(views_string * VIEWS_MAP.get(abb.upper(), 1)) # Do a dict lookup and return the approprite value

# Precompile regex once
_duration_units_regex = re.compile(r'(\d+(?:\.\d+)?)(h|m|s)', flags=re.IGNORECASE)

@lru_cache(maxsize=512)
def convert_duration(duration_string: str) -> int:
    """
    Converts various duration formats to total seconds.
    Optimized for repeated calls with LRU caching.
    
    Supported formats:
    - "SS"
    - "MM:SS"
    - "HH:MM:SS"
    - "HH:MM:SS:FF" (frames ignored)
    - "0:10.899"
    - "2h 3m 4s"
    - "90s"
    - "1.5m"
    """

    if isinstance(duration_string, (int, float)):
        return int(duration_string)

    duration_string = duration_string.strip().lower()

    if not duration_string:
        return 0

    # Match formats like "2h 3m 4s"
    matches = _duration_units_regex.findall(duration_string)
    if matches:
        return int(sum(
            float(value) * {'h': 3600, 'm': 60, 's': 1}[unit]
            for value, unit in matches
        ))

    # Handle colon-separated formats: [SS], [MM:SS], [HH:MM:SS], [HH:MM:SS:FF]
    parts = duration_string.split(":")
    try:
        parts = tuple(map(float, parts))
    except ValueError:
        return 0  # Malformed input

    length = len(parts)
    if length == 1:
        return int(parts[0])
    elif length == 2:
        return int(parts[0] * 60 + parts[1])
    elif length == 3:
        return int(parts[0] * 3600 + parts[1] * 60 + parts[2])
    elif length == 4:
        return int(parts[0] * 3600 + parts[1] * 60 + parts[2])  # Ignoring frames
    else:
        return 0
