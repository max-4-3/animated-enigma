def convert_views(views_str: str) -> int:
    maps = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000
    }
    views_str.replace(',', '')
    views_str = views_str.lower()

    if 'k' in views_str:
        return int(float(views_str.replace('k', ''))) * maps['k']
    elif 'm' in views_str:
        return int(float(views_str.replace('m', ''))) * maps['b']
    elif 'b' in views_str:
        return int(float(views_str.replace('b', ''))) * maps['b']
    else:
        return 0 if not views_str.isdigit() else int(views_str)
def convert_views(views_str: str) -> int:
    maps = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000
    }
    views_str.replace(',', '')
    views_str = views_str.lower()

    if 'k' in views_str:
        return int(float(views_str.replace('k', ''))) * maps['k']
    elif 'm' in views_str:
        return int(float(views_str.replace('m', ''))) * maps['b']
    elif 'b' in views_str:
        return int(float(views_str.replace('b', ''))) * maps['b']
    else:
        return 0 if not views_str.isdigit() else int(views_str)