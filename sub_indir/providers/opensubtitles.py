import os
from typing import List, Optional
import httpx

from sub_indir.core.models import SubtitleCandidate, VideoInfo
from sub_indir.providers.base import BaseProvider


API_BASE_URL = "https://api.opensubtitles.com/api/v1"
DEFAULT_USER_AGENT = "sub-indir v0.1.0"


class OpenSubtitlesProvider(BaseProvider):
    """Subtitle provider for OpenSubtitles.com REST API v3."""

    name = "opensubtitles"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.api_key = api_key or os.environ.get("OPENSUBTITLES_API_KEY")
        self.timeout = timeout

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Api-Key"] = self.api_key
        return headers

    def search(self, video: VideoInfo) -> List[SubtitleCandidate]:
        if not self.is_available:
            return []

        candidates: List[SubtitleCandidate] = []
        params = {
            "languages": "tr",
        }

        # If moviehash is calculated, use it for exact match
        if video.file_hash:
            params["moviehash"] = video.file_hash
        else:
            params["query"] = video.title
            if video.year and not video.is_tv:
                params["year"] = str(video.year)
            if video.is_tv:
                if video.season:
                    params["season_number"] = str(video.season)
                if video.episode:
                    params["episode_number"] = str(video.episode)

        try:
            with httpx.Client(headers=self._get_headers(), timeout=self.timeout) as client:
                res = client.get(f"{API_BASE_URL}/subtitles", params=params)
                if res.status_code != 200:
                    return []

                data = res.json().get("data", [])
                for item in data:
                    attrs = item.get("attributes", {})
                    files = attrs.get("files", [])
                    file_id = files[0].get("file_id") if files else None
                    if not file_id:
                        continue

                    feature = attrs.get("feature_details", {})
                    release = attrs.get("release", "") or attrs.get("comments", "")
                    uploader = attrs.get("uploader", {}).get("name", "")

                    season = feature.get("season_number") if video.is_tv else None
                    episode = feature.get("episode_number") if video.is_tv else None

                    candidates.append(
                        SubtitleCandidate(
                            provider=self.name,
                            id=str(item.get("id")),
                            title=feature.get("movie_name", video.title),
                            lang="tr",
                            season=season,
                            episode=episode,
                            release_info=release,
                            translator=uploader,
                            fps=str(attrs.get("fps", "")),
                            downloads=int(attrs.get("download_count", 0)),
                            detail_url=attrs.get("url", ""),
                            extra_data={"file_id": file_id},
                        )
                    )
        except Exception:
            pass

        return candidates

    def download(self, candidate: SubtitleCandidate) -> bytes:
        if not self.is_available:
            raise RuntimeError("OpenSubtitles API key is required to download from OpenSubtitles.")

        file_id = candidate.extra_data.get("file_id")
        if not file_id:
            raise ValueError("No file_id found for OpenSubtitles candidate")

        with httpx.Client(headers=self._get_headers(), timeout=self.timeout) as client:
            # 1. Request download link
            dl_res = client.post(f"{API_BASE_URL}/download", json={"file_id": file_id})
            if dl_res.status_code != 200:
                raise RuntimeError(f"Failed to get download URL: HTTP {dl_res.status_code}")

            dl_url = dl_res.json().get("link")
            if not dl_url:
                raise RuntimeError("No download link in response")

            # 2. Download actual file
            file_res = client.get(dl_url)
            if file_res.status_code != 200:
                raise RuntimeError(f"Failed to download subtitle file: HTTP {file_res.status_code}")

            return file_res.content
