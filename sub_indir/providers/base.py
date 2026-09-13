from abc import ABC, abstractmethod
from typing import List

from sub_indir.core.models import SubtitleCandidate, VideoInfo


class BaseProvider(ABC):
    """Abstract base class for subtitle providers."""

    name: str = "base"

    @abstractmethod
    def search(self, video: VideoInfo) -> List[SubtitleCandidate]:
        """Searches for subtitles matching the given video information."""
        pass

    @abstractmethod
    def download(self, candidate: SubtitleCandidate) -> bytes:
        """Downloads the subtitle file or archive for the given candidate and returns raw bytes."""
        pass
