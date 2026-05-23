from pathlib import Path

def sanitize_filename(name: str):

    invalid = '<>:"/\\|?*'

    for c in invalid:
        name = name.replace(c, "_")

    return name.strip()


def ensure_dir(path):

    Path(path).mkdir(
        parents=True,
        exist_ok=True
    )