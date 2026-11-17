"""Network/media worker. Only canonical YouTube URLs enter yt-dlp."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from downloader import (
    AppError, MAX_LIST_ITEMS, MAX_VIDEO_SECONDS, VIDEO_ID, normalize_playlist_url,
)


class QuietLogger:
    def debug(self, message):
        pass

    def warning(self, message):
        pass

    def error(self, message):
        pass


def friendly_error(error: Exception) -> str:
    message = str(error).lower()
    if any(part in message for part in (
        "sign in", "confirm you're not a bot", "bot", "429", "403",
        "po token", "challenge", "javascript runtime",
    )):
        return (
            "O YouTube bloqueou o acesso ou exigiu uma verificação. Isso é comum "
            "em servidores de nuvem. Tente mais tarde ou execute no seu computador "
            "com o yt-dlp atualizado e Node.js/Deno instalado. O app não contorna bloqueios."
        )
    if any(part in message for part in ("private", "members-only", "login", "age", "premium")):
        return "Conteúdo privado, restrito ou que exige login não é suportado."
    if any(part in message for part in ("unavailable", "not exist", "removed", "not found")):
        return "O vídeo ou a playlist está indisponível, foi removido ou não é público."
    if any(part in message for part in ("format", "ffmpeg")):
        return (
            "Não há um MP4 compatível na resolução solicitada ou o FFmpeg não "
            "está disponível. Tente outra resolução e confira o README."
        )
    if any(part in message for part in ("timed out", "network", "connection", "resolve")):
        return "Falha de conexão com o YouTube. Confira a internet e tente mais tarde."
    return "Não foi possível acessar o conteúdo. Confira o link e se ele é público e está disponível."


def _options() -> dict:
    runtimes = {}
    for runtime in ("deno", "node"):
        executable = shutil.which(runtime)
        if executable:
            runtimes[runtime] = {"path": executable}
    return {
        "quiet": True, "no_warnings": True, "logger": QuietLogger(),
        "socket_timeout": 15, "retries": 1, "fragment_retries": 1,
        "extractor_retries": 1, "cachedir": False,
        # Use only locally installed JS solvers, never a remote execution service.
        "js_runtimes": runtimes, "remote_components": set(),
    }


def list_playlist(payload: dict) -> dict:
    import yt_dlp

    url = normalize_playlist_url(payload["url"])
    options = {
        **_options(), "extract_flat": "in_playlist", "skip_download": True,
        "playlistend": MAX_LIST_ITEMS + 1, "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise AppError("Não foi possível consultar esta playlist pública.")
        entries = list(info.get("entries") or [])
        videos, seen = [], set()
        for index, item in enumerate(entries[:MAX_LIST_ITEMS], start=1):
            if not item:
                continue
            video_id = str(item.get("id") or "")
            if not VIDEO_ID.fullmatch(video_id) or video_id in seen:
                continue
            if item.get("availability") in {"private", "premium_only", "subscriber_only", "needs_auth"}:
                continue
            title = str(item.get("title") or "")
            if title in ("[Private video]", "[Deleted video]"):
                continue
            seen.add(video_id)
            duration = item.get("duration")
            videos.append({
                "id": video_id, "title": title or video_id, "position": index,
                "duration": int(duration) if isinstance(duration, (int, float)) else None,
            })
        if not videos:
            raise AppError("Não foram encontrados vídeos públicos acessíveis nesta playlist.")
        return {
            "id": str(info.get("id") or ""),
            "title": str(info.get("title") or "Playlist"),
            "channel": str(info.get("channel") or info.get("uploader") or "Canal não informado"),
            "url": url, "videos": videos,
            "truncated": len(entries) > MAX_LIST_ITEMS,
        }


def download_video(payload: dict, folder: Path) -> dict:
    import imageio_ffmpeg
    import yt_dlp

    video_id = str(payload.get("id") or "")
    if not VIDEO_ID.fullmatch(video_id):
        raise AppError("O identificador do vídeo é inválido.")
    quality = payload.get("quality")
    if quality not in (360, 720, 1080):
        raise AppError("A resolução solicitada é inválida.")
    max_bytes = int(payload["max_bytes"])
    # FFmpeg has a wheel-bundled executable on supported desktop/Linux platforms.
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    progress_bytes = {}

    def progress(event):
        if event.get("status") in ("downloading", "finished"):
            filename = event.get("filename") or "stream"
            progress_bytes[filename] = event.get("downloaded_bytes") or 0
            if sum(progress_bytes.values()) > max_bytes:
                raise AppError("O vídeo excede o limite de tamanho. Tente uma resolução menor.")

    def allowed(info, *, incomplete=False):
        if info.get("is_live") or info.get("live_status") in ("is_live", "is_upcoming"):
            return "Transmissões ao vivo ou agendadas não são suportadas."
        duration = info.get("duration")
        if duration and duration > MAX_VIDEO_SECONDS:
            return "Vídeos com mais de 60 minutos não são aceitos nesta versão."
        if info.get("has_drm"):
            return "Conteúdo protegido por DRM não é suportado."
        return None

    bound = f"[height<={quality}]"
    options = {
        **_options(), "noplaylist": True, "ignoreerrors": False,
        "format": (
            f"bestvideo[ext=mp4][vcodec^=avc1]{bound}+bestaudio[ext=m4a]/"
            f"best[ext=mp4]{bound}"
        ),
        "outtmpl": str(folder / "video.%(ext)s"),
        "merge_output_format": "mp4", "ffmpeg_location": ffmpeg,
        "max_filesize": max_bytes, "progress_hooks": [progress],
        "match_filter": allowed, "overwrites": True,
        "concurrent_fragment_downloads": 1,
        "writethumbnail": False, "writeinfojson": False,
        "writesubtitles": False, "writeautomaticsub": False,
        "hls_prefer_native": True, "fixup": "never",
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
    media = folder / "video.mp4"
    if not info or not media.is_file():
        raise AppError(
            "O vídeo não foi baixado. Ele pode exceder 60 minutos, ser uma "
            "transmissão ao vivo ou ultrapassar o limite de tamanho."
        )
    if media.stat().st_size > max_bytes:
        media.unlink()
        raise AppError("O vídeo excede o tamanho disponível no lote. Tente uma resolução menor.")
    return {"resolution": info.get("resolution") or f"até {quality}p"}


def main() -> None:
    request = Path(sys.argv[1])
    response = request.with_name("response.json")
    try:
        payload = json.loads(request.read_text(encoding="utf-8"))
        if payload["operation"] == "list":
            result = list_playlist(payload)
        elif payload["operation"] == "download":
            result = download_video(payload, request.parent)
        else:
            raise AppError("Operação inválida.")
    except AppError as exc:
        result = {"error": str(exc)}
    except Exception as exc:
        result = {"error": friendly_error(exc)}
    response.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
