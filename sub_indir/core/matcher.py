import math
import re
from typing import List

from sub_indir.core.models import SubtitleCandidate, VideoInfo


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
    else:
        # If video is movie, but candidate has season/episode
        if candidate.season is not None or candidate.episode is not None:
            score -= 50.0

    # 3. Release Group Matching (Crucial for subtitle synchronization!)
    rel_info = (candidate.release_info or "").upper()
    if video.release_group:
        grp = video.release_group.upper()
        # Word boundary search for release group (e.g. \bFLUX\b)
        if re.search(rf"\b{re.escape(grp)}\b", rel_info):
            score += 40.0
        elif grp in rel_info:
            score += 25.0

    # 4. Source Matching (BluRay, WEBRip, WEB-DL, HDTV)
    if video.source:
        src = video.source.upper()
        if "WEB" in src and ("WEB" in rel_info or "NETRIP" in rel_info):
            score += 15.0
        elif "BLU" in src and "BLU" in rel_info:
            score += 15.0
        elif "HDTV" in src and "HDTV" in rel_info:
            score += 15.0

    # 5. Resolution Matching (1080p, 720p, 2160p)
    if video.screen_size:
        size = video.screen_size.upper()
        if size in rel_info:
            score += 10.0

    # 6. Popularity / Download Count Bonus (log scale, max +10)
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
