import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from sub_indir.core.models import SubtitleCandidate, VideoInfo
from sub_indir.providers.base import BaseProvider


BASE_URL = "https://turkcealtyazi.org"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}


class TurkceAltyaziProvider(BaseProvider):
    """Subtitle provider for TurkceAltyazi.org."""

    name = "turkcealtyazi"

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    def _get_client(self, referer: Optional[str] = None) -> httpx.Client:
        headers = dict(DEFAULT_HEADERS)
        if referer:
            headers["Referer"] = referer
        return httpx.Client(headers=headers, follow_redirects=True, timeout=self.timeout)

    def search(self, video: VideoInfo) -> List[SubtitleCandidate]:
        candidates: List[SubtitleCandidate] = []
        with self._get_client() as client:
            movie_urls = []

            # 1. Search via IMDb ID first if available (exact match!)
            if video.imdb_id:
                try:
                    res_imdb = client.get(
                        f"{BASE_URL}/find.php",
                        params={"cat": "sub", "find": video.imdb_id}
                    )
                    res_imdb.encoding = "utf-8"
                    if "/mov/" in str(res_imdb.url):
                        movie_urls.append(str(res_imdb.url))
                    else:
                        movie_urls.extend(self._find_matching_movie_urls(res_imdb.text, video))
                except Exception:
                    pass

            # 2. If no movie page found via IMDb, search by title
            if not movie_urls:
                query = video.title.strip()
                try:
                    res = client.get(
                        f"{BASE_URL}/find.php",
                        params={"cat": "sub", "find": query}
                    )
                    res.encoding = "utf-8"
                    if "/mov/" in str(res.url):
                        movie_urls = [str(res.url)]
                    else:
                        movie_urls = self._find_matching_movie_urls(res.text, video)
                except Exception:
                    return []

            # 2. Extract subtitles from matched movie/series pages
            for movie_url in movie_urls[:3]:  # Top 3 matching titles
                try:
                    sub_res = client.get(movie_url)
                    sub_res.encoding = "utf-8"
                    page_candidates = self._parse_subtitles_from_page(sub_res.text, video)
                    candidates.extend(page_candidates)
                except Exception:
                    continue

        return candidates

    def _find_matching_movie_urls(self, html: str, video: VideoInfo) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        left = soup.select_one(".sub-container.nleft")
        if not left:
            left = soup

        matches = []
        for a in left.find_all("a", href=lambda h: h and "/mov/" in h):
            title = a.get_text(strip=True)
            if not title:
                continue
            href = a["href"]
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            
            parent = a.find_parent("div")
            parent_text = parent.get_text(" ", strip=True) if parent else ""
            
            # Check type (Tv Dizisi vs Film)
            is_series = "Tv Dizisi" in parent_text or "dizi" in href.lower()
            
            # Simple matching score for search results
            score = 0
            clean_q = re.sub(r"[^a-zA-Z0-9]", "", video.title.lower())
            clean_t = re.sub(r"[^a-zA-Z0-9]", "", title.lower())
            if clean_q == clean_t:
                score += 50
            elif clean_q in clean_t:
                score += 30

            if video.is_tv and is_series:
                score += 40
            elif not video.is_tv and not is_series:
                score += 30

            if video.year and str(video.year) in parent_text:
                score += 20

            matches.append((score, full_url))

        # Sort descending by score
        matches.sort(key=lambda x: x[0], reverse=True)
        # Deduplicate URLs
        seen = set()
        unique_urls = []
        for _, url in matches:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        return unique_urls

    def _parse_subtitles_from_page(self, html: str, video: VideoInfo) -> List[SubtitleCandidate]:
        soup = BeautifulSoup(html, "html.parser")
        wrapper = soup.find(class_="altyazi-list-wrapper")
        if not wrapper:
            return []

        candidates: List[SubtitleCandidate] = []
        rows = wrapper.find_all(class_=lambda c: c and ("altsonsez" in c or "row-class" in c))

        for row in rows:
            sub_a = row.find("a", href=lambda h: h and "/sub/" in h)
            if not sub_a:
                continue

            sub_href = sub_a["href"]
            detail_url = sub_href if sub_href.startswith("http") else f"{BASE_URL}{sub_href}"
            sub_id = sub_a.get("id", "")
            title = sub_a.get_text(strip=True)

            # Language check
            lang_el = row.find(class_="aldil")
            flag_class = " ".join(lang_el.find("span").get("class", [])) if lang_el and lang_el.find("span") else ""
            if "flagtr" in flag_class:
                lang = "tr"
            elif "flagen" in flag_class:
                lang = "en"
            else:
                lang = "tr" if "türkçe" in flag_class.lower() else "other"

            # Parse Season / Episode or CD
            season = None
            episode = None
            cd_el = row.find(class_="alcd")
            if cd_el:
                cd_text = cd_el.get_text(" ", strip=True)
                # Try multiple patterns for season/episode detection
                tv_patterns = [
                    r"[sS]\s*(\d+).*?[eE]\s*(\d+)",                   # S 02 | E 10
                    r"(\d+)\.\s*[Ss]ezon.*?(\d+)\.\s*[Bb][öo]l",      # 1. Sezon 2. Bölüm
                    r"[Ss]ezon\s*(\d+).*?[Bb][öo]l[üu]m\s*(\d+)",     # Sezon 1 Bölüm 2
                ]
                for pat in tv_patterns:
                    tv_match = re.search(pat, cd_text, re.IGNORECASE)
                    if tv_match:
                        season = int(tv_match.group(1))
                        episode = int(tv_match.group(2))
                        break

                # If no season/episode found yet, check for season pack (e.g. "S 05 Paket", "5. Sezon")
                if season is None and video.is_tv:
                    season_pack_patterns = [
                        r"[sS]\s*(\d+)\s*(?:[Pp]aket)?",
                        r"(\d+)\.\s*[Ss]ezon",
                        r"[Ss]ezon\s*(\d+)",
                    ]
                    for pat in season_pack_patterns:
                        sp_match = re.search(pat, cd_text, re.IGNORECASE)
                        if sp_match:
                            season = int(sp_match.group(1))
                            break

            # Translator
            trans_el = row.find(class_="alcevirmen")
            translator = trans_el.get_text(strip=True) if trans_el else ""

            # FPS
            fps_el = row.find(class_="alfps")
            fps = fps_el.get_text(strip=True) if fps_el else ""

            # Downloads
            dl_el = row.find(class_="alindirme")
            dl_text = dl_el.get_text(strip=True).replace(",", "").replace(".", "") if dl_el else "0"
            downloads = int(dl_text) if dl_text.isdigit() else 0

            # Release info (ripdiv)
            rip_el = row.find(class_="ripdiv")
            release_info = rip_el.get_text(" ", strip=True) if rip_el else ""

            candidates.append(
                SubtitleCandidate(
                    provider=self.name,
                    id=sub_id or detail_url,
                    title=title,
                    lang=lang,
                    season=season,
                    episode=episode,
                    release_info=release_info,
                    translator=translator,
                    fps=fps,
                    downloads=downloads,
                    detail_url=detail_url,
                )
            )

        return candidates

    def download(self, candidate: SubtitleCandidate) -> bytes:
        """Fetches the subtitle download form and posts to /ind."""
        with self._get_client(referer=candidate.detail_url) as client:
            res = client.get(candidate.detail_url)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            form = soup.find("form", action=lambda a: a and "/ind" in a)
            if not form:
                raise ValueError(f"Download form not found on {candidate.detail_url}")

            post_data = {}
            for inp in form.find_all("input"):
                name = inp.get("name")
                if name:
                    post_data[name] = inp.get("value", "")

            # Submit download request
            download_url = f"{BASE_URL}/ind"
            dl_res = client.post(download_url, data=post_data)
            if dl_res.status_code != 200 or not dl_res.content:
                raise RuntimeError(f"Download failed with HTTP {dl_res.status_code}")

            return dl_res.content
