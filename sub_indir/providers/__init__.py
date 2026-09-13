"""Providers module for sub-indir."""
from sub_indir.providers.base import BaseProvider
from sub_indir.providers.embedded import EmbeddedSubtitleProvider
from sub_indir.providers.turkcealtyazi import TurkceAltyaziProvider
from sub_indir.providers.subliminal_provider import SubliminalProvider
from sub_indir.providers.opensubtitles import OpenSubtitlesProvider

__all__ = [
    "BaseProvider",
    "EmbeddedSubtitleProvider",
    "TurkceAltyaziProvider",
    "SubliminalProvider",
    "OpenSubtitlesProvider",
]
