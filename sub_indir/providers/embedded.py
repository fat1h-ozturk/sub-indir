import logging
import shutil
import subprocess
from pathlib import Path
from typing import List

from sub_indir.core.models import SubtitleCandidate, VideoInfo
from sub_indir.providers.base import BaseProvider

logger = logging.getLogger(__name__)

# Supported text subtitle formats that ffmpeg can cleanly transcode to standard SRT
TEXT_FORMATS = {"subrip", "utf-8", "ass", "ssa", "webvtt", "mov_text", "timed text", "text"}
# Bitmap/image subtitle formats that ffmpeg cannot transcode to text without OCR
IMAGE_FORMATS = {"pgs", "vobsub", "hdmv_pgs_subtitle", "dvd_subtitle"}


class EmbeddedSubtitleProvider(BaseProvider):
    """Detects and extracts embedded Turkish subtitle tracks from video files using ffmpeg."""

    name = "embedded"

    @property
    def is_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def search(self, video: VideoInfo) -> List[SubtitleCandidate]:
        if not self.is_available:
            return []
        if not video.path or not video.path.exists():
            return []

        candidates: List[SubtitleCandidate] = []
        try:
            from pymediainfo import MediaInfo
            media_info = MediaInfo.parse(str(video.path))

            text_stream_idx = 0
            for track in media_info.tracks:
                if track.track_type != "Text":
                    continue

                lang = (track.language or "").lower()
                title = (track.title or "").strip()
                title_lower = title.lower()
                fmt = (track.format or "SRT").strip()
                fmt_lower = fmt.lower()

                # Determine stream index for ffmpeg (-map 0:s:<idx>)
                current_stream_idx = text_stream_idx
                if track.stream_identifier is not None:
                    try:
                        current_stream_idx = int(track.stream_identifier)
                    except (ValueError, TypeError):
                        pass
                text_stream_idx += 1

                # Check if Turkish language
                is_tr = (
                    lang in ["tr", "tur", "turkish"]
                    or "türkçe" in title_lower
                    or "turkce" in title_lower
                    or "turkish" in title_lower
                )
                if not is_tr:
                    continue

                # Check if bitmap/image subtitle (cannot be cleanly extracted to srt without OCR)
                if any(img_fmt in fmt_lower for img_fmt in IMAGE_FORMATS):
                    logger.debug(f"Skipping bitmap embedded subtitle format: {fmt}")
                    continue

                # Construct descriptive release info
                desc_parts = [f"Dahili Akış #{current_stream_idx}", fmt]
                if title:
                    desc_parts.append(title)
                if getattr(track, "forced", "No") == "Yes":
                    desc_parts.append("[Forced]")
                rel_info = " - ".join(desc_parts)

                cand_id = f"embedded_{current_stream_idx}"
                candidates.append(
                    SubtitleCandidate(
                        provider=self.name,
                        id=cand_id,
                        title=f"[Gömülü / Dahili] {video.display_name}",
                        lang="tr",
                        season=video.season,
                        episode=video.episode,
                        release_info=rel_info,
                        translator="Dahili / Resmi Akış",
                        fps=str(video.fps or ""),
                        downloads=0,
                        detail_url="",
                        score=200.0,
                        hash_matched=True,
                        extra_data={
                            "stream_index": current_stream_idx,
                            "video_path": str(video.path),
                            "format": fmt,
                            "title": title,
                        },
                    )
                )
        except Exception as e:
            logger.debug(f"EmbeddedSubtitleProvider search error: {e}")

        return candidates

    def download(self, candidate: SubtitleCandidate) -> bytes:
        if not self.is_available:
            raise RuntimeError("ffmpeg sistemde bulunamadı. Gömülü altyazı çıkarılamıyor.")

        stream_idx = candidate.extra_data.get("stream_index", 0)
        video_path = candidate.extra_data.get("video_path")
        if not video_path or not Path(video_path).exists():
            raise FileNotFoundError(f"Video dosyası bulunamadı: {video_path}")

        cmd = [
            "ffmpeg",
            "-y",
            "-v", "error",
            "-i", str(video_path),
            "-map", f"0:s:{stream_idx}",
            "-c:s", "srt",
            "-f", "srt",
            "-"
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            err_msg = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"FFmpeg altyazı çıkarma hatası: {err_msg}")

        if not result.stdout:
            raise RuntimeError("FFmpeg altyazı içeriğini boş döndürdü.")

        return result.stdout
