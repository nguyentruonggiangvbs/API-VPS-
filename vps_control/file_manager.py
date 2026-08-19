from pathlib import Path
import shutil

BASE_PATH = Path('/opt')


def safe_path(path: str):
    target = Path(path).resolve()
    if not str(target).startswith(str(BASE_PATH)):
        raise PermissionError('Path not allowed')
    return target


def list_files(path='/opt'):
    target = safe_path(path)
    return [
        {
            'name': item.name,
            'type': 'folder' if item.is_dir() else 'file',
            'size': item.stat().st_size if item.is_file() else 0
        }
        for item in target.iterdir()
    ]


def delete_file(path):
    target = safe_path(path)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return True
