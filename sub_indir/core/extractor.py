import io
import re
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

from sub_indir.core.models import VideoInfo


SUBTITLE_EXTENSIONS = {".srt", ".ass", ".sub", ".vtt"}


def is_archive(data: bytes) -> bool:
    """Checks if byte payload is a zip or rar archive."""
    return data.startswith(b"PK\x03\x04") or data.startswith(b"Rar!\x1a\x07")


def extract_subtitles_from_bytes(data: bytes) -> List[Tuple[str, bytes]]:
    """Extracts all subtitle files from zip archive bytes or returns single file."""
    results: List[Tuple[str, bytes]] = []

    # If it is a ZIP archive
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    # Ignore directory entries and mac metadata
                    if name.endswith("/") or "__MACOSX" in name or name.startswith("."):
                        continue
                    ext = Path(name).suffix.lower()
                    if ext in SUBTITLE_EXTENSIONS:
                        content = zf.read(name)
                        results.append((Path(name).name, content))
        except Exception:
            pass

    # If already a subtitle format or text
    if not results:
        # Check if text looks like an SRT (has timestamp format like 00:00:00,000 --> 00:00:00,000)
        # Or just return as single file
        results.append(("subtitle.srt", data))

    return results


def pick_best_subtitle(
    candidates: List[Tuple[str, bytes]],
    video_info: Optional[VideoInfo] = None
) -> Optional[Tuple[str, bytes]]:
    """Finds the most matching subtitle file from extracted files based on episode/name."""
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    if not video_info:
        # Return the largest file by default (usually the full subtitle)
        return max(candidates, key=lambda item: len(item[1]))

    # For TV episodes, match episode pattern in subtitle internal filename
    if video_info.is_tv and video_info.episode is not None:
        ep = video_info.episode
        # Patterns ordered from most specific to least specific
        # Using negative lookahead (?!\d) to prevent E01 matching in E10
        patterns = [
            rf"[eE](?:pisode)?[ ._-]?{ep:02d}(?!\d)",    # E01, Episode.01, e01
            rf"[eE](?:pisode)?[ ._-]?{ep}(?!\d)",         # E1, Episode.1
            rf"[bB][öo]l[üu]m[ ._-]*{ep}(?!\d)",          # Bölüm 1, bolum.1
        ]
        # Collect ALL matching files first, then filter SDH
        matching = []
        for name, data in candidates:
            for pat in patterns:
                if re.search(pat, name, re.IGNORECASE):
                    matching.append((name, data))
                    break

        if matching:
            # Prefer non-SDH/HI among matched episode files
            non_sdh = [c for c in matching if not re.search(r"(\.hi\.|\.sdh\.|[ ._-]sdh\b|[ ._-]hi\b)", c[0], re.IGNORECASE)]
            if non_sdh:
                return max(non_sdh, key=lambda item: len(item[1]))
            return max(matching, key=lambda item: len(item[1]))

    # Exclude HI / SDH (hearing impaired) if standard is available
    non_sdh = [c for c in candidates if not re.search(r"(\.hi\.|\.sdh\.|[ ._-]sdh\b|[ ._-]hi\b)", c[0], re.IGNORECASE)]
    if non_sdh:
        return max(non_sdh, key=lambda item: len(item[1]))

    return max(candidates, key=lambda item: len(item[1]))
