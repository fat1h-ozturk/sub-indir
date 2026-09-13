from pathlib import Path
import struct
from typing import Optional, Union, Dict, Any
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


def extract_media_info(filepath: Path) -> Dict[str, Any]:
    """Extracts actual video stream FPS, resolution, codec, and duration using pymediainfo if available."""
    info: Dict[str, Any] = {}
    try:
        from pymediainfo import MediaInfo
        media_info = MediaInfo.parse(str(filepath))
        for track in media_info.tracks:
            if track.track_type == "Video":
                if track.frame_rate:
                    try:
                        info["fps"] = round(float(track.frame_rate), 3)
                    except (ValueError, TypeError):
                        pass
                if track.height:
                    try:
                        h = int(track.height)
                        if h >= 2000:
                            info["screen_size"] = "2160p"
                        elif h >= 1000:
                            info["screen_size"] = "1080p"
                        elif h >= 700:
                            info["screen_size"] = "720p"
                        elif h >= 480:
                            info["screen_size"] = "480p"
                    except (ValueError, TypeError):
                        pass
                if track.format:
                    fmt = str(track.format).upper()
                    if "HEVC" in fmt or "H.265" in fmt:
                        info["video_codec"] = "H.265"
                    elif "AVC" in fmt or "H.264" in fmt:
                        info["video_codec"] = "H.264"
                    elif "AV1" in fmt:
                        info["video_codec"] = "AV1"
                if track.duration:
                    try:
                        info["duration"] = round(float(track.duration) / 1000.0, 1)
                    except (ValueError, TypeError):
                        pass
                break
    except Exception:
        pass
    return info


def resolve_imdb_id(
    title: str,
    year: Optional[int] = None,
    is_tv: bool = False,
    timeout: float = 3.0
) -> Optional[str]:
    """Resolves IMDb ID (e.g. tt0137523) using IMDb suggestion API with timeout protection."""
    clean = (title or "").lower().strip()
    if not clean:
        return None

    from urllib.parse import quote
    import httpx

    encoded = quote(clean)
    first_char = clean[0] if clean[0].isalnum() else "a"
    url = f"https://v3.sg.media-imdb.com/suggestion/{first_char}/{encoded}.json"

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("d", [])
                for item in items:
                    item_id = item.get("id", "")
                    if not item_id.startswith("tt"):
                        continue
                    item_year = item.get("y")
                    item_q = item.get("q", "").lower()
                    is_item_tv = "tv" in item_q or "series" in item_q

                    if year and item_year and abs(item_year - year) <= 1:
                        return item_id
                    if is_tv and is_item_tv:
                        return item_id
                    if not is_tv and not is_item_tv and item_q in ("feature", "movie"):
                        return item_id

                # Fallback to first valid tt item
                if items and items[0].get("id", "").startswith("tt"):
                    return items[0]["id"]
    except Exception:
        pass
    return None


def parse_video(file_path_or_name: Union[str, Path]) -> VideoInfo:
    """Parses video metadata from filename, parent directories, and video stream properties."""
    path = Path(file_path_or_name) if isinstance(file_path_or_name, str) else file_path_or_name
    filename = path.name

    # 1. Parse filename with guessit
    guess = dict(guessit(filename))

    # 2. Check parent folder name if available (vital for folders like "The Walking Dead Season 3 (1080p x265 Joy)")
    if path.parent and path.parent != Path(".") and path.parent.name:
        try:
            parent_guess = dict(guessit(path.parent.name))
            for key in ["release_group", "screen_size", "video_codec", "source", "season", "year"]:
                if not guess.get(key) and parent_guess.get(key):
                    guess[key] = parent_guess[key]
        except Exception:
            pass

    title = guess.get("title", path.stem)
    year = guess.get("year")
    season = guess.get("season")
    episode = guess.get("episode")
    release_group = guess.get("release_group")
    source = guess.get("source")
    screen_size = guess.get("screen_size")
    video_codec = guess.get("video_codec")

    # guessit returns lists for multi-episode files (e.g. Show.S01E01-E02.mkv)
    # Safely extract first element to prevent TypeError on int()
    if isinstance(season, list):
        season = season[0]
    if isinstance(episode, list):
        episode = episode[0]
    if isinstance(year, list):
        year = year[0]

    # TV vs Movie check
    is_tv = bool(season is not None or episode is not None or guess.get("type") == "episode")

    file_hash = None
    file_size = None
    real_path = None
    fps = None
    duration = None

    if path.exists() and path.is_file():
        real_path = path.resolve()
        file_hash, file_size = compute_moviehash(real_path)

        # 3. Extract actual stream properties (FPS, resolution, codec, duration) from the container
        media_info = extract_media_info(real_path)
        if media_info:
            fps = media_info.get("fps")
            duration = media_info.get("duration")
            if not screen_size and media_info.get("screen_size"):
                screen_size = media_info["screen_size"]
            if not video_codec and media_info.get("video_codec"):
                video_codec = media_info["video_codec"]

    # 4. Resolve IMDb ID
    imdb_id = resolve_imdb_id(
        title=str(title),
        year=int(year) if year else None,
        is_tv=is_tv
    )

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
        fps=fps,
        duration=duration,
        is_tv=is_tv,
        file_hash=file_hash,
        file_size=file_size,
        imdb_id=imdb_id,
    )
