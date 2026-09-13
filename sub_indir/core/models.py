from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class VideoInfo:
    filename: str
    title: str
    path: Optional[Path] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    release_group: Optional[str] = None
    source: Optional[str] = None
    screen_size: Optional[str] = None
    video_codec: Optional[str] = None
    is_tv: bool = False
    file_hash: Optional[str] = None
    file_size: Optional[int] = None

    @property
    def display_name(self) -> str:
        if self.is_tv and self.season is not None and self.episode is not None:
            return f"{self.title} S{self.season:02d}E{self.episode:02d}"
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


@dataclass
class SubtitleCandidate:
    provider: str
    id: str
    title: str
    lang: str = "tr"
    season: Optional[int] = None
    episode: Optional[int] = None
    release_info: str = ""
    translator: str = ""
    fps: str = ""
    downloads: int = 0
    detail_url: str = ""
    score: float = 0.0
    extra_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_turkish(self) -> bool:
        return self.lang.lower() in ["tr", "turkish", "türkçe"]
