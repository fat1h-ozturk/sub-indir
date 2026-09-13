import os
import sys
from pathlib import Path
from typing import Optional, List

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from InquirerPy import inquirer

from sub_indir import __version__
from sub_indir.core.parser import parse_video, is_video_file, VIDEO_EXTENSIONS
from sub_indir.core.models import VideoInfo, SubtitleCandidate
from sub_indir.core.downloader import SubtitleManager


# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="sub-indir",
    help="Yalnızca Türkçe altyazıya odaklı, akıllı altyazı indirme CLI aracı.",
    add_completion=False,
)
console = Console(safe_box=True)


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]sub-indir[/bold cyan] versiyon [green]{__version__}[/green]")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None, "-v", "--version", callback=version_callback, is_eager=True, help="Sürüm bilgisini gösterir."
    ),
):
    """Yalnızca Türkçe altyazıya odaklı akıllı CLI aracı."""
    pass


def format_candidate_label(c: SubtitleCandidate) -> str:
    episode_info = ""
    if c.season is not None and c.episode is not None:
        episode_info = f"S{c.season:02d}E{c.episode:02d} | "

    translator = f"Çeviri: {c.translator}" if c.translator else ""
    fps = f"{c.fps} FPS" if c.fps else ""
    downloads = f"{c.downloads:,} indirme" if c.downloads else ""
    rip = f"[{c.release_info[:40]}...]" if len(c.release_info) > 40 else f"[{c.release_info}]"

    prov_tag = "[TurkceAltyazi]" if c.provider == "turkcealtyazi" else "[OpenSubtitles]"
    sync_badge = " [bold green]★ HASH[/bold green]" if c.hash_matched else ""

    meta_parts = [p for p in [prov_tag, episode_info, translator, fps, downloads] if p]
    meta_str = " | ".join(meta_parts)
    return f"({c.score:.0f}p{sync_badge}) {meta_str} {rip}"


def process_single_video(
    manager: SubtitleManager,
    video: VideoInfo,
    auto: bool = False,
    force: bool = False,
    no_suffix: bool = False
) -> bool:
    console.print()
    meta_lines = [
        f"[bold white]Başlık:[/bold white] [cyan]{video.title}[/cyan]",
    ]
    if video.is_tv:
        meta_lines.append(
            f"[bold white]Bölüm:[/bold white] [yellow]Sezon {video.season}, Bölüm {video.episode}[/yellow]"
        )
    if video.year:
        meta_lines.append(f"[bold white]Yıl:[/bold white] [magenta]{video.year}[/magenta]")
    if video.release_group:
        meta_lines.append(f"[bold white]Release:[/bold white] [green]{video.release_group}[/green]")
    if video.screen_size:
        meta_lines.append(f"[bold white]Çözünürlük:[/bold white] {video.screen_size}")
    if video.source:
        meta_lines.append(f"[bold white]Kaynak:[/bold white] {video.source}")
    if video.fps:
        meta_lines.append(f"[bold white]FPS (Akış):[/bold white] [blue]{video.fps}[/blue]")

    console.print(
        Panel(
            "\n".join(meta_lines),
            title=f"[bold cyan]> {video.display_name}[/bold cyan]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    # Check if subtitle already exists
    if video.path:
        suffixes_to_check = [".srt", ".ass", ".vtt"] if no_suffix else [".tr.srt", ".tr.ass", ".tr.vtt", ".srt"]
        existing_sub = None
        for sfx in suffixes_to_check:
            cand = video.path.with_suffix(sfx)
            if cand.exists():
                existing_sub = cand
                break
        if existing_sub and not force:
            console.print(
                f"[yellow][i] Altyazi dosyasi zaten mevcut:[/yellow] [dim]{existing_sub.name}[/dim] (Atlandi, tekrar indirmek icin --force kullanin)"
            )
            return True

    with console.status("[bold green]Turkce ve senkronize altyazilar araniyor (TurkceAltyazi + OpenSubtitles)...[/bold green]", spinner="dots"):
        candidates = manager.find_subtitles(video)

    if not candidates:
        console.print("[red][X] Eslesen Turkce altyazi bulunamadi.[/red]")
        return False

    console.print(f"[green][V] Toplam {len(candidates)} adet altyazi bulundu.[/green]")

    selected_candidate: Optional[SubtitleCandidate] = None

    if auto or len(candidates) == 1:
        selected_candidate = candidates[0]
        console.print(f"[cyan][*] En iyi eslesme otomatik secildi:[/cyan] [bold]{selected_candidate.release_info or selected_candidate.title}[/bold] ([yellow]{selected_candidate.score:.0f}p[/yellow])")
    else:
        # Show table of top candidates
        table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Puan", justify="right", style="yellow")
        table.add_column("Sağlayıcı", style="cyan")
        if video.is_tv:
            table.add_column("Bölüm", style="magenta")
        table.add_column("Çevirmen / Tip", style="green")
        table.add_column("FPS", style="blue")
        table.add_column("İndirme", justify="right")
        table.add_column("Uyumlu Sürümler (Rip)", style="white")

        for idx, c in enumerate(candidates[:12], start=1):
            score_display = f"{c.score:.0f} ★" if c.hash_matched else f"{c.score:.0f}"
            prov_display = "TurkceAltyazi" if c.provider == "turkcealtyazi" else "OpenSubtitles"
            row_items = [str(idx), score_display, prov_display]
            if video.is_tv:
                ep_str = f"S{c.season:02d}E{c.episode:02d}" if c.season and c.episode else "-"
                row_items.append(ep_str)
            row_items.extend([
                c.translator or "-",
                c.fps or "-",
                f"{c.downloads:,}" if c.downloads else "-",
                (c.release_info[:45] + "...") if len(c.release_info) > 45 else (c.release_info or "-")
            ])
            table.add_row(*row_items)

        console.print(table)

        # Interactive selector (use indices to avoid InquirerPy's asdict() corrupting SubtitleCandidate)
        choices = [
            {"name": format_candidate_label(c), "value": idx}
            for idx, c in enumerate(candidates[:15])
        ]
        choices.append({"name": "[Vazgeç / İptal et]", "value": None})

        try:
            selected_idx = inquirer.select(
                message="İndirmek istediğiniz altyazıyı seçin:",
                choices=choices,
                default=0
            ).execute()
        except KeyboardInterrupt:
            console.print("\n[yellow]İşlem iptal edildi.[/yellow]")
            return False

        if selected_idx is None:
            console.print("[yellow]İndirme atlandı.[/yellow]")
            return False

        selected_candidate = candidates[selected_idx]

    with console.status("[bold cyan]Altyazi indiriliyor ve UTF-8'e donusturuluyor...[/bold cyan]", spinner="dots"):
        res = manager.download_and_save(
            candidate=selected_candidate,
            video=video,
            add_language_suffix=not no_suffix
        )

    if res.success and res.subtitle_path:
        console.print(f"[bold green][V] Altyazi kaydedildi:[/bold green] [underline white]{res.subtitle_path}[/underline white]")
        return True
    else:
        console.print(f"[bold red][X] Hata:[/bold red] {res.message}")
        return False


@app.command(name="download", help="Video dosyası veya klasör için Türkçe altyazı indirir.")
def download(
    target: str = typer.Argument(".", help="Video dosya yolu, klasör veya arama metni (Varsayılan: bulunulan dizin '.')"),
    auto: bool = typer.Option(False, "-a", "--auto", help="Kullanıcıya sormadan en yüksek puanlı altyazıyı otomatik indirir"),
    force: bool = typer.Option(False, "-f", "--force", help="Altyazı dosyası zaten varsa üzerine yazar"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Klasör belirtildiğinde alt klasörleri de tarar"),
    no_suffix: bool = typer.Option(False, "--no-suffix", help="'.tr.srt' yerine doğrudan '.srt' olarak kaydeder"),
    lang: Optional[str] = typer.Option(None, "-l", "--lang", hidden=True, help="Uyumluluk için opsiyonel dil parametresi"),
    version: Optional[bool] = typer.Option(None, "-v", "--version", callback=version_callback, is_eager=True),
):
    target_path = Path(target)
    manager = SubtitleManager()

    # Case 1: Directory scan
    if target_path.exists() and target_path.is_dir():
        pattern = "**/*" if recursive else "*"
        video_files: List[Path] = [
            f for f in target_path.glob(pattern)
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]

        if not video_files:
            console.print(f"[yellow]Klasörde video dosyası bulunamadı:[/yellow] {target_path}")
            raise typer.Exit()

        console.print(f"[bold cyan]Toplam {len(video_files)} adet video dosyasi bulundu.[/bold cyan]")
        success_count = 0
        try:
            for vfile in video_files:
                v_info = parse_video(vfile)
                ok = process_single_video(manager, v_info, auto=auto, force=force, no_suffix=no_suffix)
                if ok:
                    success_count += 1
        except KeyboardInterrupt:
            console.print("\n[yellow]Toplu indirme iptal edildi.[/yellow]")

        console.print()
        console.print(f"[bold green]Tamamlandi:[/bold green] {success_count}/{len(video_files)} video icin altyazi indirildi.")
        return

    # Case 2: Single existing video file
    if target_path.exists() and target_path.is_file():
        v_info = parse_video(target_path)
        process_single_video(manager, v_info, auto=auto, force=force, no_suffix=no_suffix)
        return

    # Case 3: Title query string (e.g. "Severance S02E01" or "Inception 2010")
    v_info = parse_video(target)
    process_single_video(manager, v_info, auto=auto, force=force, no_suffix=no_suffix)


def main():
    # Allow running directly: "sub-indir ." or "sub-indir -a ." without typing "download"
    if len(sys.argv) == 1:
        sys.argv.insert(1, "download")
    elif len(sys.argv) > 1 and sys.argv[1] not in ("download", "--help", "-h", "--version", "-v"):
        sys.argv.insert(1, "download")
    app()


if __name__ == "__main__":
    main()
