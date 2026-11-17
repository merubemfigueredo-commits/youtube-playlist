"""Public YouTube playlist downloads, isolated per session and per video."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit
from zipfile import ZipFile, ZIP_STORED

MAX_LIST_ITEMS = 200
MAX_BATCH_VIDEOS = 20
MAX_BATCH_MB = 300
MAX_VIDEO_MB = 120
MAX_VIDEO_SECONDS = 3600
LIST_TIMEOUT = 60
VIDEO_TIMEOUT = 240
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")


class AppError(ValueError):
    """A user-safe Portuguese error."""


def normalize_playlist_url(url: str) -> str:
    """Only accept YouTube links containing a playlist; never arbitrary hosts."""
    if not isinstance(url, str) or not url.strip() or len(url) > 2048:
        raise AppError("Cole um link de playlist do YouTube.")
    try:
        parsed = urlsplit(url.strip())
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {
                "youtube.com", "www.youtube.com", "m.youtube.com",
                "music.youtube.com", "youtu.be",
            }
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise AppError("Use um link HTTPS de playlist do domínio youtube.com.")
        playlist_ids = parse_qs(parsed.query).get("list", [])
        if len(playlist_ids) != 1 or not re.fullmatch(
            r"[A-Za-z0-9_-]{10,128}", playlist_ids[0]
        ):
            raise AppError("O link deve conter um identificador de playlist válido (list=...).")
        return "https://www.youtube.com/playlist?" + urlencode({"list": playlist_ids[0]})
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, AppError):
            raise
        raise AppError("O link da playlist é inválido.") from exc


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif os.name == "nt":
        # Also stop an FFmpeg child if a Windows download times out.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        process.kill()


def _run_worker(payload: dict, folder: Path, timeout: int) -> dict:
    request = folder / "request.json"
    response = folder / "response.json"
    request.write_text(json.dumps(payload), encoding="utf-8")
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("youtube_worker.py")), str(request)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name == "posix",
        )
        process.wait(timeout=timeout)
        if process.returncode != 0 or not response.is_file():
            raise AppError("O processo foi interrompido. Tente menos vídeos por lote.")
        result = json.loads(response.read_text(encoding="utf-8"))
        if result.get("error"):
            raise AppError(result["error"])
        return result
    except subprocess.TimeoutExpired as exc:
        raise AppError(
            f"O YouTube não concluiu a operação em {timeout} segundos. "
            "Tente novamente mais tarde ou escolha um vídeo menor."
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AppError("Não foi possível executar o downloader neste servidor.") from exc
    finally:
        if process is not None and process.poll() is None:
            _terminate(process)
            process.wait()


def load_playlist(url: str) -> dict:
    canonical = normalize_playlist_url(url)
    with TemporaryDirectory(prefix="yt-list-") as temp:
        return _run_worker(
            {"operation": "list", "url": canonical}, Path(temp), LIST_TIMEOUT
        )


def _safe_archive_name(position: int, title: str, video_id: str) -> str:
    title = re.sub(r"[^\w .()-]", "_", title, flags=re.UNICODE).strip(" .")[:90]
    return f"{position:03d} - {title or 'video'} [{video_id}].mp4"


def _report_bytes(rows: list[dict]) -> bytes:
    # Prefix spreadsheet formula triggers in external titles.
    def safe(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text

    text = StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(["posição", "título", "id", "status", "arquivo ou motivo"])
    for row in rows:
        writer.writerow([safe(row[key]) for key in ("position", "title", "id", "status", "detail")])
    return text.getvalue().encode("utf-8-sig")


def download_videos(
    videos: list[dict],
    quality: int = 720,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Download a bounded batch in playlist order and return ZIP bytes.

    Each video uses a separate process. Partial successes are retained and
    explicitly reported. All disk files live inside a temporary directory.
    """
    if quality not in (360, 720, 1080) or type(quality) is not int:
        raise AppError("Escolha uma resolução máxima de 360, 720 ou 1080p.")
    if not videos or len(videos) > MAX_BATCH_VIDEOS:
        raise AppError(f"Selecione de 1 a {MAX_BATCH_VIDEOS} vídeos por lote.")
    seen = set()
    selected = []
    for index, video in enumerate(videos, start=1):
        video_id = str(video.get("id", ""))
        if not VIDEO_ID.fullmatch(video_id) or video_id in seen:
            raise AppError("A seleção contém vídeos inválidos ou repetidos.")
        seen.add(video_id)
        selected.append({
            "id": video_id,
            "title": str(video.get("title") or video_id)[:300],
            "position": int(video.get("position") or index),
        })
    selected.sort(key=lambda item: item["position"])
    failures, files, rows = [], [], []
    total_bytes = 0
    with TemporaryDirectory(prefix="yt-download-") as temp:
        root = Path(temp)
        for number, video in enumerate(selected, start=1):
            if on_progress:
                on_progress(number - 1, len(selected), f"Baixando: {video['title']}")
            folder = root / video["id"]
            folder.mkdir()
            try:
                remaining = MAX_BATCH_MB * 1024 * 1024 - total_bytes
                if remaining <= 0:
                    raise AppError("O lote atingiu o limite de tamanho. Crie outro lote.")
                result = _run_worker({
                    "operation": "download", "id": video["id"], "quality": quality,
                    "max_bytes": min(MAX_VIDEO_MB * 1024 * 1024, remaining),
                }, folder, VIDEO_TIMEOUT)
                media = folder / "video.mp4"
                if not media.is_file() or media.stat().st_size < 1:
                    raise AppError("O YouTube não forneceu um arquivo MP4 completo.")
                size = media.stat().st_size
                if size > remaining or size > MAX_VIDEO_MB * 1024 * 1024:
                    raise AppError("O arquivo excede o limite de tamanho deste lote.")
                name = _safe_archive_name(video["position"], video["title"], video["id"])
                total_bytes += size
                files.append({
                    **video, "filename": name, "bytes": size,
                    "resolution": result.get("resolution") or "Não informada",
                })
                rows.append({**video, "status": "baixado", "detail": name})
            except AppError as exc:
                reason = str(exc)
                failures.append({"title": video["title"], "reason": reason})
                rows.append({**video, "status": "falhou", "detail": reason})
                # Free partial files before the next attempt.
                shutil.rmtree(folder, ignore_errors=True)
            if on_progress:
                on_progress(number, len(selected), f"Processados {number} de {len(selected)} vídeos")
        zip_bytes = None
        if files:
            output = BytesIO()
            # MP4 is already compressed; avoid unnecessary CPU work.
            with ZipFile(output, "w", ZIP_STORED) as archive:
                for item in files:
                    archive.write(root / item["id"] / "video.mp4", item["filename"])
                archive.writestr("relatorio.csv", _report_bytes(rows))
            zip_bytes = output.getvalue()
    return {
        "zip_bytes": zip_bytes, "success_count": len(files),
        "failures": failures, "files": files,
    }
