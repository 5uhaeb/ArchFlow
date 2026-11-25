"""Bounded, cached UTF-8 reads for workspace analysis."""
import os
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

MAX_BYTES = int(os.environ.get('ARCHFLOW_MAX_FILE_BYTES', '1048576'))
MAX_ENTRIES = int(os.environ.get('ARCHFLOW_MAX_ENTRIES', '2000'))

@lru_cache(maxsize=4096)
def cached_text(path: str, mtime: int, size: int) -> str:
    if size > MAX_BYTES: raise HTTPException(413, 'File exceeds the workspace text size limit.')
    try:
        data = Path(path).read_bytes()
        if b'\0' in data: raise UnicodeError('binary content')
        return data.decode('utf-8')
    except UnicodeError as exc: raise HTTPException(415, 'Binary or non-UTF-8 file cannot be edited.') from exc
    except OSError as exc: raise HTTPException(403, 'File cannot be read.') from exc

def text(path: Path) -> str:
    try: stat = path.stat()
    except OSError as exc: raise HTTPException(403, 'File cannot be accessed.') from exc
    return cached_text(str(path), stat.st_mtime_ns, stat.st_size)
