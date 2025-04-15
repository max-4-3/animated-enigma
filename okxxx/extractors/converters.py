from datetime import datetime

def convert_duration_to_seconds(duration_str):
    """Converts a duration string (12:21) to seconds."""
    time_parts = duration_str.split(':')
    if len(time_parts) == 3:
        hours, minutes, seconds = map(int, time_parts)
        total_seconds = hours * 3600 + minutes * 60 + seconds
    elif len(time_parts) == 2:
        minutes, seconds = map(int, time_parts)
        total_seconds = minutes * 60 + seconds
    else:
        total_seconds = int(time_parts[0]) # Assuming the string is in seconds if no colon is found

    return total_seconds

def convert_upload_date_to_timestamp(upload_date_str):
    """Converts an upload date string(DD.MM.YYYY) to a timestamp."""
    date_format = "%d.%m.%Y" # Example format: DD.MM.YYYY
    upload_date = datetime.strptime(upload_date_str, date_format)
    timestamp = int(upload_date.timestamp())
    return timestamp
from datetime import datetime

def convert_duration_to_seconds(duration_str):
    """Converts a duration string (12:21) to seconds."""
    time_parts = duration_str.split(':')
    if len(time_parts) == 3:
        hours, minutes, seconds = map(int, time_parts)
        total_seconds = hours * 3600 + minutes * 60 + seconds
    elif len(time_parts) == 2:
        minutes, seconds = map(int, time_parts)
        total_seconds = minutes * 60 + seconds
    else:
        total_seconds = int(time_parts[0]) # Assuming the string is in seconds if no colon is found

    return total_seconds

def convert_upload_date_to_timestamp(upload_date_str):
    """Converts an upload date string(DD.MM.YYYY) to a timestamp."""
    date_format = "%d.%m.%Y" # Example format: DD.MM.YYYY
    upload_date = datetime.strptime(upload_date_str, date_format)
    timestamp = int(upload_date.timestamp())
    return timestamp