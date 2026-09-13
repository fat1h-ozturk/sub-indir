from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from sub_indir.core.models import SubtitleCandidate, VideoInfo
from sub_indir.core.parser import parse_video
from sub_indir.core.matcher import rank_candidates
from sub_indir.core.extractor import extract_subtitles_from_bytes, pick_best_subtitle
from sub_indir.core.encoding import normalize_to_utf8, save_subtitle_file
from sub_indir.providers.base import BaseProvider
from sub_indir.providers.turkcealtyazi import TurkceAltyaziProvider
from sub_indir.providers.opensubtitles import OpenSubtitlesProvider


@dataclass
class DownloadResult:
    video: VideoInfo
    subtitle_path: Optional[Path]
    candidate: Optional[SubtitleCandidate]
    success: bool
    message: str


class SubtitleManager:
    """Manages subtitle searching, ranking, downloading, and post-processing."""

    def __init__(
        self,
        providers: Optional[List[BaseProvider]] = None,
        opensubtitles_key: Optional[str] = None
    ):
        if providers is not None:
            self.providers = providers
        else:
            self.providers = [
                TurkceAltyaziProvider(),
                OpenSubtitlesProvider(api_key=opensubtitles_key)
            ]

    def find_subtitles(self, video: VideoInfo) -> List[SubtitleCandidate]:
        """Searches all registered providers and ranks the results."""
        all_candidates: List[SubtitleCandidate] = []
        for p in self.providers:
            try:
                subs = p.search(video)
                all_candidates.extend(subs)
            except Exception:
                continue

        return rank_candidates(all_candidates, video)

    def download_and_save(
        self,
        candidate: SubtitleCandidate,
        video: VideoInfo,
        target_path: Optional[Path] = None,
        add_language_suffix: bool = True
    ) -> DownloadResult:
        """Downloads, unpacks, converts to UTF-8 and saves the subtitle."""
        provider = next((p for p in self.providers if p.name == candidate.provider), None)
        if not provider:
            return DownloadResult(
                video=video,
                subtitle_path=None,
                candidate=candidate,
                success=False,
                message=f"Sağlayıcı bulunamadı: {candidate.provider}"
            )

        try:
            raw_bytes = provider.download(candidate)
        except Exception as e:
            return DownloadResult(
                video=video,
                subtitle_path=None,
                candidate=candidate,
                success=False,
                message=f"İndirme hatası: {e}"
            )

        extracted = extract_subtitles_from_bytes(raw_bytes)
        if not extracted:
            return DownloadResult(
                video=video,
                subtitle_path=None,
                candidate=candidate,
                success=False,
                message="İndirilen arşiv içinde geçerli altyazı dosyası bulunamadı."
            )

        best_match = pick_best_subtitle(extracted, video)
        if not best_match:
            return DownloadResult(
                video=video,
                subtitle_path=None,
                candidate=candidate,
                success=False,
                message="Eşleşen altyazı seçilemedi."
            )

        sub_filename, sub_bytes = best_match
        utf8_text = normalize_to_utf8(sub_bytes)

        # Determine original subtitle extension (preserve .ass/.vtt instead of forcing .srt)
        sub_ext = Path(sub_filename).suffix.lower() if sub_filename else ".srt"
        if sub_ext not in {".srt", ".ass", ".ssa", ".vtt", ".sub"}:
            sub_ext = ".srt"

        # Determine target file path
        if target_path:
            out_path = Path(target_path)
        elif video.path:
            lang_suffix = f".tr{sub_ext}" if add_language_suffix else sub_ext
            out_path = video.path.with_suffix(lang_suffix)
        else:
            lang_suffix = f".tr{sub_ext}" if add_language_suffix else sub_ext
            # Sanitize filename for Windows (remove : ? * < > | " chars)
            safe_name = "".join(c if c not in ':?*<>|"' else '_' for c in video.filename)
            out_path = Path.cwd() / f"{safe_name}{lang_suffix}"

        save_subtitle_file(utf8_text, out_path)

        return DownloadResult(
            video=video,
            subtitle_path=out_path,
            candidate=candidate,
            success=True,
            message="Altyazı başarıyla indirildi ve UTF-8 olarak kaydedildi."
        )
