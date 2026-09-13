from pathlib import Path
import struct
from typing import Optional, Union
from guessit import guessit

from sub_indir.core.models import VideoInfo


VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts", ".m2ts"
}


def is_video_file(file_path: Union[str, Path]) -> bool:
    path = Path(file_path)
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def compute_moviehash(filepath: Path) -> tuple[Optional[str], Optional[int]]:
    """Calculates OpenSubtitles-compatible 64-bit moviehash."""
    try:
        filesize = filepath.stat().st_size
        if filesize < 65536 * 2:
            return None, filesize
        
        longlongformat = "<q"
        bytesize = struct.calcsize(longlongformat)
        hash_val = filesize
        
        with open(filepath, "rb") as f:
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_val = (hash_val + l_value) & 0xFFFFFFFFFFFFFFFF
                
            f.seek(max(0, filesize - 65536), 0)
            for _ in range(65536 // bytesize):
                buffer = f.read(bytesize)
                (l_value,) = struct.unpack(longlongformat, buffer)
                hash_val = (hash_val + l_value) & 0xFFFFFFFFFFFFFFFF
                
        return f"{hash_val:016x}", filesize
    except Exception:
        return None, None


def parse_video(file_path_or_name: Union[str, Path]) -> VideoInfo:
    """Parses video metadata from filename or Path using guessit."""
    path = Path(file_path_or_name) if isinstance(file_path_or_name, str) else file_path_or_name
    filename = path.name
    
    guess = guessit(filename)
    
    title = guess.get("title", path.stem)
    year = guess.get("year")
    season = guess.get("season")
    episode = guess.get("episode")
    release_group = guess.get("release_group")
    source = guess.get("source")
    screen_size = guess.get("screen_size")
    video_codec = guess.get("video_codec")
    
    # TV vs Movie check
    is_tv = bool(season is not None or episode is not None or guess.get("type") == "episode")
    
    file_hash = None
    file_size = None
    real_path = None
    
    if path.exists() and path.is_file():
        real_path = path.resolve()
        file_hash, file_size = compute_moviehash(real_path)

    return VideoInfo(
        filename=filename,
        path=real_path,
        title=str(title),
        year=int(year) if year else None,
        season=int(season) if season else None,
        episode=int(episode) if episode else None,
        release_group=str(release_group) if release_group else None,
        source=str(source) if source else None,
        screen_size=str(screen_size) if screen_size else None,
        video_codec=str(video_codec) if video_codec else None,
        is_tv=is_tv,
        file_hash=file_hash,
        file_size=file_size,
    )
