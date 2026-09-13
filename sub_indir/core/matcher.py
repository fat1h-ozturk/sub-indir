import math
import re
from typing import List

from sub_indir.core.models import SubtitleCandidate, VideoInfo


# Normalized source matching map — covers guessit output variations
# and common release group naming conventions
SOURCE_MAP = {
    "WEB":  ["WEB", "WEBRIP", "WEB-DL", "WEBDL", "NETRIP", "NF", "AMZN", "ATVP", "DSNP", "HMAX", "PCOK", "STAN"],
    "BLU":  ["BLURAY", "BLU-RAY", "BRRIP", "BDRIP", "BDREMUX", "REMUX"],
    "HDTV": ["HDTV", "PDTV", "SDTV", "AHDTV", "DVB"],
    "DVD":  ["DVDRIP", "DVDSCR", "DVD", "DVD-R"],
}

# Known P2P re-encoder groups that re-encode from scene BluRay or WEB-DL masters
REENCODER_GROUPS = {
    "JOY", "PSA", "PAHE", "QXR", "SILENCE", "UTR", "TIGOLE", "MEGUSTA",
    "RMTEAM", "RARBG", "YTS", "SHAANIG", "MINX", "AFG", "GGEZ", "ION10",
    "ELITE", "FENIX", "CAKES", "GLHF", "XEN0N", "RUBIK", "SUCCESSFULCRAB"
}

# High-profile scene release groups (masters) whose subtitles are compatible with re-encodes
SCENE_MASTERS = {
    "CTRLHD", "DON", "FLUX", "NTB", "KOGI", "AMIABLE", "SPARKS", "ROVERS",
    "SIGMA", "DEMAND", "CAKES", "GLHF", "CASSTUDIO", "CYPHANIX", "BTN",
    "DEFLATE", "TOMMY", "MIXED", "DIMENSION", "LOL", "KILLERS"
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

    # 0. Embedded / Internal Subtitles in Video (guaranteed instant 100% sync!)
    if candidate.provider == "embedded":
        score += 200.0

    # 1. Moviehash Exact Match (guaranteed 100% frame-perfect sync!)
    if candidate.hash_matched:
        score += 150.0

    # 2. Language: Turkish priority
    if candidate.is_turkish:
        score += 30.0

    # 3. Title match & Spin-off / Different show filter
    v_clean = re.sub(r"[^a-zA-Z0-9]", "", video.title.lower())
    c_clean = re.sub(r"[^a-zA-Z0-9]", "", candidate.title.lower())
    if v_clean and c_clean:
        if v_clean == c_clean:
            score += 15.0
        elif (v_clean in c_clean or c_clean in v_clean) and abs(len(c_clean) - len(v_clean)) > 3:
            # Different spin-off or franchise variation (e.g. "Fear the Walking Dead", "Dead City", "World Beyond")
            score -= 100.0

    # Also check release_info for spin-off subtitles attached to franchise names
    rel_clean_upper = re.sub(r"[._-]", " ", (candidate.release_info or "").upper())
    v_upper = video.title.upper()
    if f"{v_upper} " in rel_clean_upper:
        remainder = rel_clean_upper.split(f"{v_upper} ", 1)[1]
        match = re.match(r"^([A-Z]{3,}(?:\s+[A-Z]{3,})*)\s+S\d+", remainder)
        if match and not any(tag in match.group(1) for tag in ["COMPLETE", "SEASON", "SPECIAL", "PART"]):
            score -= 80.0
    if "FEAR " in rel_clean_upper and "FEAR" not in v_upper:
        score -= 80.0

    # 4. TV Show Season / Episode Check
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

    rel_info = (candidate.release_info or "").upper()

    # 4. Baseline Quality Tier Preference (Retail BluRay/WEB vs obsolete CAM/SCR)
    if any(cam in rel_info for cam in ["DVDSCR", "DVD-SCR", "CAMRIP", "HDCAM", "TELESYNC", "WORKPRINT", "SCREENER"]):
        score -= 30.0
    elif re.search(r"\b(CAM|TS|SCR)\b", rel_info):
        score -= 30.0
    elif any(q in rel_info for q in ["BLURAY", "BLU-RAY", "BDRIP", "BRRIP", "WEB-DL", "WEBDL", "WEBRIP"]):
        score += 10.0

    # 5. Release Group Matching (Crucial for subtitle synchronization!)
    if video.release_group:
        grp = video.release_group.upper()
        # Word boundary search for release group (e.g. \bFLUX\b)
        if re.search(rf"\b{re.escape(grp)}\b", rel_info):
            score += 40.0
        elif grp in rel_info:
            score += 25.0

    # 5. HDTV vs WEB/BluRay Incompatibility & Re-Encoder Affinity
    # High-res, x265, and re-encoder rips almost ALWAYS come from WEB-DL or BluRay masters.
    # Broadcast HDTV has commercial breaks and different timing; mixing them causes desync!
    is_web_or_bluray_video = False
    if video.source and any(s in video.source.upper() for s in ["WEB", "BLU", "BD"]):
        is_web_or_bluray_video = True
    elif video.screen_size in ("1080p", "2160p", "4k"):
        is_web_or_bluray_video = True
    elif video.video_codec and any(c in video.video_codec.upper() for c in ["H.265", "HEVC", "X265"]):
        is_web_or_bluray_video = True
    elif video.release_group and video.release_group.upper() in REENCODER_GROUPS:
        is_web_or_bluray_video = True

    candidate_is_hdtv = "HDTV" in rel_info and not any(w in rel_info for w in ["WEB", "BLU", "BDRIP", "BRRIP"])
    candidate_is_web_or_blu = any(w in rel_info for w in ["WEB", "WEBRIP", "WEB-DL", "WEBDL", "BLURAY", "BLU-RAY", "BRRIP", "BDRIP"])

    if is_web_or_bluray_video:
        if candidate_is_hdtv:
            score -= 40.0  # Heavy penalty: HDTV commercials and cut differences desync on WEB/BluRay!
        elif candidate_is_web_or_blu:
            score += 25.0  # Compatible master timing

        # If video is from a P2P re-encoder (Joy, PSA, Pahe, etc.), check if candidate matches scene master
        if video.release_group and video.release_group.upper() in REENCODER_GROUPS:
            if any(m in rel_info for m in SCENE_MASTERS):
                score += 30.0  # Candidate is the exact scene master used for the re-encode!
    elif video.source and "HDTV" in video.source.upper():
        if candidate_is_hdtv:
            score += 30.0
        elif candidate_is_web_or_blu:
            score -= 30.0

    # 6. Source Matching — expanded with SOURCE_MAP
    if video.source:
        video_source_key = _normalize_source(video.source)
        matched = False
        if video_source_key in SOURCE_MAP:
            for variant in SOURCE_MAP[video_source_key]:
                if variant in rel_info or variant.replace("-", "") in rel_info:
                    score += 15.0
                    matched = True
                    break
        if not matched:
            src_upper = video.source.upper().replace(" ", "").replace("-", "")
            if src_upper in rel_info:
                score += 15.0

    # 7. Resolution Matching (1080p, 720p, 2160p)
    if video.screen_size:
        size = video.screen_size.upper()
        if size in rel_info:
            score += 10.0

    # 8. Video Codec Matching (x264, x265, HEVC, H.264, H.265)
    if video.video_codec:
        codec = video.video_codec.upper().replace(".", "")
        codec_variants = {codec}
        if codec in ("H264", "H 264", "AVC"):
            codec_variants.update(["H264", "X264", "AVC"])
        elif codec in ("H265", "H 265", "HEVC"):
            codec_variants.update(["H265", "X265", "HEVC"])
        rel_clean = rel_info.replace(".", "").replace("-", "")
        if any(cv in rel_clean for cv in codec_variants):
            score += 5.0

    # 9. FPS Matching — crucial for preventing drift!
    cand_fps = None
    if candidate.fps:
        try:
            cand_fps = float(candidate.fps)
        except (ValueError, TypeError):
            pass

    # If candidate doesn't have FPS explicitly, check release info
    if cand_fps is None:
        for fps_val in ["23.976", "24.000", "25.000", "29.970", "30.000"]:
            if fps_val in rel_info:
                cand_fps = float(fps_val)
                break

    if cand_fps is not None:
        if video.fps is not None:
            # Video has real detected FPS (from container or metadata)
            if abs(video.fps - cand_fps) < 0.05:
                score += 25.0  # Exact FPS match
            elif abs(video.fps - cand_fps) >= 0.5:
                score -= 40.0  # Frame rate mismatch (e.g. 23.976 vs 25.0 PAL drift)
        else:
            # Small bonus for having verified FPS metadata
            score += 2.0

    # 10. Popularity / Download Count Bonus (capped at +4.0 so it never overrides source compatibility)
    if candidate.downloads > 0:
        download_bonus = min(4.0, math.log10(candidate.downloads + 1) * 0.8)
        score += download_bonus

    return round(score, 1)


def rank_candidates(candidates: List[SubtitleCandidate], video: VideoInfo) -> List[SubtitleCandidate]:
    """Calculates scores for all candidates and sorts them from best to worst."""
    for c in candidates:
        c.score = calculate_match_score(c, video)

    # Sort descending by score, then by downloads
    return sorted(candidates, key=lambda c: (c.score, c.downloads), reverse=True)
