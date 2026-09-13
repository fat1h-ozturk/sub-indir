import logging
from typing import List, Optional

from sub_indir.core.models import SubtitleCandidate, VideoInfo
from sub_indir.providers.base import BaseProvider

logger = logging.getLogger(__name__)

try:
    import subliminal
    from babelfish import Language
    SUBLIMINAL_AVAILABLE = True
except ImportError:
    SUBLIMINAL_AVAILABLE = False


class SubliminalProvider(BaseProvider):
    """Integrates Subliminal's multi-provider pool (OpenSubtitles, Podnapisi, etc.)
    with Turkish-only filtering and moviehash synchronization."""

    name = "subliminal"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    @property
    def is_available(self) -> bool:
        return SUBLIMINAL_AVAILABLE

    def search(self, video: VideoInfo) -> List[SubtitleCandidate]:
        if not self.is_available:
            return []

        candidates: List[SubtitleCandidate] = []
        try:
            # Construct subliminal video object
            video_input = str(video.path) if video.path else video.filename
            v = subliminal.Video.fromname(video_input)

            # Inject calculated hash and filesize if available
            if video.file_hash and video.file_size:
                v.hashes["opensubtitles"] = video.file_hash
                v.size = video.file_size

            # Inject known metadata if available
            if video.screen_size and not getattr(v, "resolution", None):
                v.resolution = video.screen_size
            if video.release_group and not getattr(v, "release_group", None):
                v.release_group = video.release_group

            # Query subliminal provider pool specifically for Turkish (Language('tur'))
            # Use free providers that do not require an API key to download
            free_providers = ["opensubtitles", "podnapisi"]
            subtitles_dict = subliminal.list_subtitles(
                [v],
                {Language("tur")},
                providers=free_providers
            )
            video_subs = subtitles_dict.get(v, [])

            for s in video_subs:
                matched_by = getattr(s, "matched_by", "")
                hash_matched = matched_by == "hash"

                # Extract release name
                rel_info = (
                    getattr(s, "movie_release_name", None)
                    or getattr(s, "release", None)
                    or getattr(s, "filename", "")
                    or ""
                ).strip()

                # Clean leading release artifacts
                if rel_info.startswith("."):
                    rel_info = rel_info[1:]

                # Extract translator or hearing-impaired notice
                is_hi = getattr(s, "hearing_impaired", False)
                translator = "[SDH]" if is_hi else getattr(s, "uploader", "")

                fps_val = str(getattr(s, "fps", "") or "")

                sub_id = str(getattr(s, "subtitle_id", id(s)))
                sub_provider = getattr(s, "provider_name", "subliminal")
                cand_title = (
                    getattr(s, "series_title", None)
                    or getattr(s, "movie_name", None)
                    or getattr(s, "movie_title", None)
                    or video.title
                )
                cand_year = getattr(s, "movie_year", None)

                candidates.append(
                    SubtitleCandidate(
                        provider=self.name,
                        id=sub_id,
                        title=str(cand_title),
                        lang="tr",
                        season=getattr(s, "series_season", None) or video.season,
                        episode=getattr(s, "series_episode", None) or video.episode,
                        release_info=rel_info,
                        translator=translator,
                        fps=fps_val,
                        downloads=int(getattr(s, "download_count", 0) or 0),
                        detail_url=getattr(s, "page_link", "") or "",
                        hash_matched=hash_matched,
                        extra_data={
                            "subliminal_sub": s,
                            "sub_provider": sub_provider,
                            "matched_by": matched_by,
                            "year": cand_year,
                        },
                    )
                )
        except Exception as e:
            logger.debug(f"Subliminal search error: {e}")

        return candidates

    def download(self, candidate: SubtitleCandidate) -> bytes:
        if not self.is_available:
            raise RuntimeError("Subliminal kütüphanesi sistemde yüklü değil.")

        sub = candidate.extra_data.get("subliminal_sub")
        if not sub:
            raise ValueError("Candidate does not contain a valid Subliminal subtitle object")

        try:
            subliminal.download_subtitles([sub])
            if not sub.content:
                raise RuntimeError("Subliminal altyazı içeriğini indiremedi (boş yanıt).")
            return sub.content
        except Exception as e:
            raise RuntimeError(f"Subliminal indirme hatası: {e}")
