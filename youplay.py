"""Biblioteca pessoal de playlists do YouTube - interface Streamlit."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import streamlit as st

from downloader import (
    AppError,
    MAX_BATCH_MB,
    MAX_BATCH_VIDEOS,
    MAX_LIST_ITEMS,
    MAX_VIDEO_MB,
    download_videos,
    load_playlist,
    normalize_playlist_url,
)

APP_DIR = Path(__file__).parent
SOURCE_FILES = [
    "app.py",
    "downloader.py",
    "youtube_worker.py",
    "requirements.txt",
    "README.md",
    "NOTICE.md",
    ".gitignore",
    ".streamlit/config.toml",
]
QUALITIES = [360, 720, 1080]

st.set_page_config(page_title="Baixar playlists do YouTube", layout="wide")

# ---------------------------------------------------------------- estado
DEFAULTS = {
    "playlist": None,
    "loaded_url": None,
    "result": None,
    "result_sig": None,
    "list_error": None,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def _sel_key(vid: str) -> str:
    return f"sel_{vid}"


def _clear_selection_widgets() -> None:
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith("sel_"):
            del st.session_state[k]


def reset_all(clear_url: bool = True) -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    _clear_selection_widgets()
    st.session_state["authorized"] = False
    if clear_url:
        st.session_state["url_input"] = ""


def on_url_change() -> None:
    reset_all(clear_url=False)


def fmt_duration(sec) -> str:
    if not sec:
        return "—"
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def build_source_zip() -> tuple[bytes, list[str]]:
    buf = io.BytesIO()
    missing = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in SOURCE_FILES:
            p = APP_DIR / name
            if p.is_file():
                zf.write(p, arcname=name)
            else:
                missing.append(name)
    return buf.getvalue(), missing


# ---------------------------------------------------------------- cabeçalho
st.title("Baixar playlists do YouTube")
st.caption(
    "Biblioteca pessoal para criadores e espectadores salvarem playlists públicas "
    "próprias ou que tenham autorização para baixar. Você escolhe exatamente quais vídeos."
)

with st.sidebar:
    st.header("Sessão")
    if st.button("Limpar tudo", key="btn_clear", use_container_width=True):
        reset_all()
        st.rerun()
    st.divider()
    st.subheader("Limites")
    st.markdown(
        f"- Até **{MAX_LIST_ITEMS}** vídeos listados por playlist\n"
        f"- Até **{MAX_BATCH_VIDEOS}** vídeos por download\n"
        f"- Até **{MAX_BATCH_MB} MB** por lote\n"
        f"- Até **{MAX_VIDEO_MB} MB** por vídeo"
    )
    st.divider()
    """st.subheader("Código-fonte")
    src_bytes, src_missing = build_source_zip()
    st.download_button(
        "Baixar código-fonte (ZIP)",
        data=src_bytes,
        file_name="youtube-playlist-fonte.zip",
        mime="application/zip",
        key="btn_source",
        use_container_width=True,
    ) """
    if src_missing:
        st.caption("Arquivos ausentes no pacote: " + ", ".join(src_missing))

st.warning(
    "O YouTube pode recusar pedidos vindos de servidores em nuvem (pedido de login, "
    "erros 403 ou 429). Este app não garante que os downloads funcionem. Se for "
    "bloqueado, execute-o localmente no seu computador (veja a ajuda abaixo). "
    "Não há suporte a login, cookies, playlists privadas ou contorno de restrições."
)

# ---------------------------------------------------------------- 1. URL
st.subheader("1. Playlist")
st.text_input(
    "URL da playlist do YouTube",
    key="url_input",
    placeholder="https://www.youtube.com/playlist?list=...",
    on_change=on_url_change,
)
load_clicked = st.button("Carregar lista", type="primary")

if load_clicked:
    raw = (st.session_state.get("url_input") or "").strip()
    reset_all(clear_url=False)
    if not raw:
        st.session_state["list_error"] = "Informe a URL de uma playlist."
    else:
        try:
            url = normalize_playlist_url(raw)
            with st.spinner("Carregando a lista de vídeos..."):
                pl = load_playlist(url)
            pl["videos"] = sorted(pl.get("videos") or [], key=lambda v: v.get("position") or 0)
            st.session_state["playlist"] = pl
            st.session_state["loaded_url"] = raw
        except AppError as e:
            st.session_state["list_error"] = str(e)
        except Exception:
            st.session_state["list_error"] = (
                "Não foi possível carregar a playlist por um erro inesperado. Tente novamente."
            )

if st.session_state["list_error"]:
    st.error(st.session_state["list_error"])

pl = st.session_state["playlist"]

# ---------------------------------------------------------------- 2. seleção
if pl:
    videos = pl.get("videos") or []
    st.divider()
    st.subheader("2. Escolha os vídeos")
    c1, c2, c3 = st.columns(3)
    c1.metric("Playlist", pl.get("title") or "Sem título")
    c2.metric("Canal", pl.get("channel") or "—")
    c3.metric("Vídeos listados", len(videos))
    if pl.get("truncated"):
        st.warning(
            f"A playlist tem mais de {MAX_LIST_ITEMS} itens; apenas os primeiros "
            f"{MAX_LIST_ITEMS} foram listados."
        )

    if not videos:
        st.info("Nenhum vídeo disponível foi encontrado nesta playlist.")
    else:
        b1, b2, b3 = st.columns(3)
        can_all = len(videos) <= MAX_BATCH_VIDEOS
        if b1.button(
            "Selecionar todos" if can_all else f"Selecionar os primeiros {MAX_BATCH_VIDEOS}",
            key="btn_sel_all",
            use_container_width=True,
        ):
            for i, v in enumerate(videos):
                st.session_state[_sel_key(v["id"])] = i < MAX_BATCH_VIDEOS
        if b2.button("Limpar seleção", key="btn_sel_none", use_container_width=True):
            for v in videos:
                st.session_state[_sel_key(v["id"])] = False
        b3.caption(f"Máximo de {MAX_BATCH_VIDEOS} vídeos por download.")

        with st.container(height=420):
            for v in videos:
                label = f"{v.get('position', '')}. {v.get('title') or 'Sem título'}  ({fmt_duration(v.get('duration'))})"
                st.checkbox(label, key=_sel_key(v["id"]))

        selected = [v for v in videos if st.session_state.get(_sel_key(v["id"]))]
        n_sel = len(selected)
        over = n_sel > MAX_BATCH_VIDEOS
        if over:
            st.error(
                f"{n_sel} vídeos selecionados. O limite é {MAX_BATCH_VIDEOS} por download; "
                "desmarque alguns."
            )
        else:
            st.write(f"**{n_sel}** de {len(videos)} vídeos selecionados.")

        # ------------------------------------------------------------ 3. download
        st.divider()
        st.subheader("3. Baixar")
        quality = st.radio(
            "Resolução máxima",
            QUALITIES,
            index=1,
            format_func=lambda q: f"Até {q}p",
            horizontal=True,
            key="quality",
            help="É um teto, não uma garantia: se o vídeo não tiver essa resolução, "
            "será usada a melhor disponível abaixo dela.",
        )
        authorized = st.checkbox(
            "Confirmo que os vídeos são meus ou que tenho autorização para baixá-los.",
            key="authorized",
        )

        sig = (tuple(v["id"] for v in selected), quality)
        if st.session_state["result_sig"] is not None and st.session_state["result_sig"] != sig:
            st.session_state["result"] = None
            st.session_state["result_sig"] = None

        disabled = (not authorized) or n_sel == 0 or over
        if st.button("Baixar vídeos selecionados", type="primary", disabled=disabled, key="btn_download"):
            if not authorized or n_sel == 0 or over:
                st.error("Selecione até o limite de vídeos e confirme a autorização.")
            else:
                bar = st.progress(0.0, text="Preparando...")

                def on_progress(done: int, total: int, message: str) -> None:
                    frac = (done / total) if total else 0.0
                    bar.progress(min(max(frac, 0.0), 1.0), text=f"{done}/{total} — {message}")

                try:
                    res = download_videos(selected, quality=quality, on_progress=on_progress)
                    st.session_state["result"] = res
                except AppError as e:
                    st.session_state["result"] = {"error": str(e)}
                except Exception:
                    st.session_state["result"] = {
                        "error": "O download falhou por um erro inesperado. Nenhum arquivo foi gerado."
                    }
                st.session_state["result_sig"] = sig
                bar.empty()

        res = st.session_state["result"]
        if res:
            if res.get("error"):
                st.error(res["error"])
            else:
                ok = int(res.get("success_count") or 0)
                fails = res.get("failures") or []
                zb = res.get("zip_bytes")
                if ok and zb and not fails:
                    st.success(f"{ok} vídeo(s) baixado(s) com sucesso.")
                elif ok and zb:
                    st.warning(f"Sucesso parcial: {ok} vídeo(s) baixado(s), {len(fails)} falharam.")
                else:
                    st.error("Nenhum vídeo foi baixado.")
                if fails:
                    with st.expander(f"Falhas ({len(fails)})", expanded=True):
                        for f in fails:
                            st.markdown(f"- **{f.get('title') or 'Sem título'}**: {f.get('reason') or 'motivo desconhecido'}")
                if ok and zb:
                    st.download_button(
                        "Salvar ZIP",
                        data=zb,
                        file_name="playlist-videos.zip",
                        mime="application/zip",
                        key="btn_save_zip",
                    )
                    st.caption("O ZIP inclui um relatório do download.")

# ---------------------------------------------------------------- ajuda
st.divider()
with st.expander("Ajuda: instalação e execução local"):
    st.markdown(
        """
**Requisitos:** Python 3.12. O FFmpeg é fornecido automaticamente pela dependência
`imageio-ffmpeg`. Para alguns desafios JavaScript do YouTube, o `yt-dlp` pode precisar
de **Node.js 22+** ou **Deno** instalado localmente (detalhes no README).

**Passos:**
1. Baixe o código-fonte pelo botão na barra lateral e descompacte.
2. Instale as dependências: `pip install -r requirements.txt`
3. Execute: `streamlit run app.py`
4. Abra o endereço mostrado no terminal.

**Se o download falhar:** mensagens de login, erros 403 ou 429 normalmente indicam que o
YouTube bloqueou o acesso do servidor. Executar no seu computador pode ajudar,
mas não garante acesso. Este app
não usa login nem cookies e não acessa playlists privadas.
"""
    )
