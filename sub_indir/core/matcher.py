import math
import re
from typing import List

from sub_indir.core.models import SubtitleCandidate, VideoInfo


# Normalized source matching map — covers guessit output variations
# and common release group naming conventions
SOURCE_MAP = {
    "WEB":  ["WEB", "WEBRIP", "WEB-DL", "WEBDL", "NETRIP", "NF", "AMZN", "ATVP", "DSNP", "HMAX", "PCOK", "STAN"],
    "BLU":  ["BLURAY", "BLU-RAY", "BRRIP", "BDRIP", "BDREMUX", "REMUX"],
    "HDTV": ["HDTV", "PDTV", "SDTV", "AHDTV"],
    "DVD":  ["DVDRIP", "DVDSCR", "DVD", "DVD-R"],
}


def _normalize_source(source_str: str) -> str:
    """Maps various source names to a canonical key."""
    s = source_str.upper().replace(" ", "").replace("-", "").replace("_", "")
    for canonical, variants in SOURCE_MAP.items():
        for v in variants:
            if v.replace("-", "").replace(" ", "") in s or s in v.replace("-", "").replace(" ", ""):
                return canonical
    return s


def calculate_match_score(candidate: SubtitleCandidate, video: VideoInfo) -> float:
    score = 0.0

    # 1. Language: Turkish priority
    if candidate.is_turkish:
        score += 30.0

    # 2. TV Show Season / Episode Check
    if video.is_tv:
        if video.season is not None and candidate.season is not None:
            if video.season == candidate.season:
                score += 20.0
            else:
                score -= 100.0  # Wrong season

        if video.episode is not None and candidate.episode is not None:
            if video.episode == candidate.episode:
                score += 30.0
            else:
                score -= 100.0  # Wrong episode

        # Season pack bonus: covers the whole season, extractor will pick the right episode
        if video.season is not None and candidate.season == video.season and candidate.episode is None:
            score += 15.0
    else:
        # If video is movie, but candidate has season/episode
        if candidate.season is not None or candidate.episode is not None:
            score -= 50.0

        # Movie Year Matching
        if video.year:
            text_to_check = f"{candidate.title} {candidate.release_info}"
            if str(video.year) in text_to_check:
                score += 10.0
            else:
                # If candidate explicitly mentions a different 4-digit year (e.g. 1989 vs 2022)
                cand_years = re.findall(r"\b(19\d\d|20\d\d)\b", text_to_check)
                if cand_years and str(video.year) not in cand_years:
                    score -= 30.0  # Different release year (remake / prequel / unrelated)

    # 3. Release Group Matching (Crucial for subtitle synchronization!)
    rel_info = (candidate.release_info or "").upper()
    if video.release_group:
        grp = video.release_group.upper()
        # Word boundary search for release group (e.g. \bFLUX\b)
        if re.search(rf"\b{re.escape(grp)}\b", rel_info):
            score += 40.0
        elif grp in rel_info:
            score += 25.0

    # 4. Source Matching — expanded with SOURCE_MAP for BRRip, BDRip, DVDRip, etc.
    if video.source:
        video_source_key = _normalize_source(video.source)
        # Check if any variant from the same source family exists in release info
        matched = False
        if video_source_key in SOURCE_MAP:
            for variant in SOURCE_MAP[video_source_key]:
                if variant in rel_info or variant.replace("-", "") in rel_info:
                    score += 15.0
                    matched = True
                    break
        if not matched:
            # Direct substring check as fallback
            src_upper = video.source.upper().replace(" ", "").replace("-", "")
            if src_upper in rel_info:
                score += 15.0

    # 5. Resolution Matching (1080p, 720p, 2160p)
    if video.screen_size:
        size = video.screen_size.upper()
        if size in rel_info:
            score += 10.0

    # 6. Video Codec Matching (x264, x265, HEVC, H.264, H.265)
    if video.video_codec:
        codec = video.video_codec.upper().replace(".", "")
        codec_variants = {codec}
        # Map common codec aliases
        if codec in ("H264", "H 264", "AVC"):
            codec_variants.update(["H264", "X264", "AVC"])
        elif codec in ("H265", "H 265", "HEVC"):
            codec_variants.update(["H265", "X265", "HEVC"])
        rel_clean = rel_info.replace(".", "").replace("-", "")
        if any(cv in rel_clean for cv in codec_variants):
            score += 5.0

    # 7. FPS Matching — critical for subtitle synchronization
    if candidate.fps:
        try:
            cand_fps = float(candidate.fps)
            # Common FPS values for reference: 23.976, 24.0, 25.0, 29.97, 30.0
            # Check if video screen_size or source hints at FPS
            # Also check release info for FPS hints
            video_fps_hint = None
            for fps_val in ["23.976", "24.000", "25.000", "29.970", "30.000"]:
                if fps_val in rel_info:
                    video_fps_hint = float(fps_val)
                    break

            if video_fps_hint and abs(cand_fps - video_fps_hint) < 0.01:
                score += 10.0
            elif cand_fps > 0:
                # Small bonus for having FPS info at all (quality indicator)
                score += 2.0
        except (ValueError, TypeError):
            pass

    # 8. Popularity / Download Count Bonus (log scale, max +10)
    if candidate.downloads > 0:
        download_bonus = min(10.0, math.log10(candidate.downloads + 1) * 2.0)
        score += download_bonus

    return round(score, 1)


def rank_candidates(candidates: List[SubtitleCandidate], video: VideoInfo) -> List[SubtitleCandidate]:
    """Calculates scores for all candidates and sorts them from best to worst."""
    for c in candidates:
        c.score = calculate_match_score(c, video)

    # Sort descending by score, then by downloads
    return sorted(candidates, key=lambda c: (c.score, c.downloads), reverse=True)
