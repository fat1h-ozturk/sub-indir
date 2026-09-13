from pathlib import Path
from typing import Union
import charset_normalizer


TURKISH_UNIQUE_CHARS = {"ı", "İ", "ş", "Ş", "ğ", "Ğ"}
TURKISH_ALL_CHARS = {"ı", "İ", "ş", "Ş", "ğ", "Ğ", "ç", "Ç", "ö", "Ö", "ü", "Ü"}


def _fix_mojibake(text: str) -> str:
    """Fixes common UTF-8 double-encoding artifacts (e.g. Ã§ -> ç, Ä± -> ı)."""
    # Quick check if common UTF-8 multi-byte sequences were decoded as latin-1/cp1252
    mojibake_markers = ["Ã§", "Ã¶", "Ã¼", "Ä±", "ÅŸ", "ÄŸ", "Ã‡", "Ã–", "Ãœ", "Ä°", "Åž", "Äž"]
    if any(marker in text for marker in mojibake_markers):
        for enc in ["latin1", "cp1252", "windows-1254"]:
            try:
                fixed = text.encode(enc).decode("utf-8")
                # If fixed text has more Turkish chars and fewer weird symbols, accept it
                if any(c in fixed for c in TURKISH_ALL_CHARS):
                    return fixed
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

        # Direct dictionary fallback if full re-encoding fails (e.g. text contains non-Latin1 symbols)
        mojibake_map = {
            "Ã§": "ç", "Ã¶": "ö", "Ã¼": "ü", "Ä±": "ı", "ÅŸ": "ş", "ÄŸ": "ğ",
            "Ã‡": "Ç", "Ã–": "Ö", "Ãœ": "Ü", "Ä°": "İ", "Åž": "Ş", "Äž": "Ğ",
        }
        for bad, good in mojibake_map.items():
            text = text.replace(bad, good)
    return text


def normalize_to_utf8(content: Union[bytes, str]) -> str:
    """
    Intelligently converts Turkish subtitle content to clean, standard UTF-8.
    Accurately handles Windows-1254, ISO-8859-9, and UTF-8 with BOM / mojibake.
    """
    if isinstance(content, str):
        return _fix_mojibake(content)

    if not content:
        return ""

    # 1. Check for UTF-8 with BOM (0xEF, 0xBB, 0xBF)
    if content.startswith(b"\xef\xbb\xbf"):
        try:
            return _fix_mojibake(content[3:].decode("utf-8"))
        except UnicodeDecodeError:
            pass

    # 2. Check if valid direct UTF-8
    try:
        decoded_utf8 = content.decode("utf-8")
        # Check if it has Turkish characters or needs mojibake fix
        return _fix_mojibake(decoded_utf8)
    except UnicodeDecodeError:
        pass

    # 3. Dedicated Turkish Encodings: Windows-1254 & ISO-8859-9
    # The vast majority of legacy Turkish subtitles are encoded in Windows-1254.
    for turkish_enc in ["windows-1254", "iso-8859-9"]:
        try:
            decoded_tr = content.decode(turkish_enc)
            # Verify that Turkish characters are present
            if any(c in decoded_tr for c in TURKISH_ALL_CHARS):
                return decoded_tr
        except UnicodeDecodeError:
            continue

    # 4. Fallback to charset-normalizer
    try:
        result = charset_normalizer.from_bytes(content).best()
        if result and result.encoding:
            enc = result.encoding.lower()
            # If charset-normalizer detected another European encoding (mac_latin2, cp1252, etc.),
            # prefer windows-1254 for Turkish subtitles.
            if enc in ["mac_latin2", "iso8859_2", "cp1250", "cp1252", "latin1"]:
                try:
                    return content.decode("windows-1254")
                except UnicodeDecodeError:
                    pass
            return str(result)
    except Exception:
        pass

    # 5. Last resort fallback
    try:
        return content.decode("windows-1254", errors="replace")
    except Exception:
        return content.decode("utf-8", errors="replace")


def save_subtitle_file(text: str, output_path: Path) -> Path:
    """Saves subtitle content as clean UTF-8 with standard line endings."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Ensure standard line endings (\n)
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    output_path.write_text(normalized_text, encoding="utf-8")
    return output_path
