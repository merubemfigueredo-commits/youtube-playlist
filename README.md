
# Playlists do YouTube — Python e Streamlit

Aplicativo independente para consultar uma playlist pública, selecionar vídeos
autorizados e baixar um ZIP com os arquivos MP4, numerados na ordem da playlist.
O ZIP inclui `relatorio.csv` com os resultados, inclusive falhas.

**Importante:** este projeto não garante acesso ao YouTube. A plataforma pode
exigir verificação, bloquear endereços de servidores ou mudar suas interfaces.
Nesses casos o aplicativo mostra a falha, sem contornar a restrição.
Para uso pessoal, executar no seu próprio computador costuma ser mais adequado
do que usar um servidor de nuvem, mas também não garante acesso.

## Recursos

- Consulta dos primeiros 200 itens de uma playlist pública.
- Seleção de até 20 vídeos por lote; playlists maiores podem ser baixadas em lotes.
- MP4 com áudio e resolução máxima de 360p, 720p ou 1080p, conforme disponível.
- Download do ZIP e relatório dos vídeos concluídos ou que falharam.
- Progresso por vídeo, tratamento de sucesso parcial e ação para limpar a sessão.
- Download do código-fonte pela interface.
- Não exige chave de API nem conta Google; não aceita cookies ou login.

## Instalar e executar

1. Instale **Python 3.12**.
2. Instale **Node.js 22 ou superior** (https://nodejs.org/) ou uma versão atual
   do Deno (https://deno.com/). O yt-dlp pode precisar desse runtime para os
   desafios JavaScript normais do player. Reinicie o terminal após instalar.
   O aplicativo detecta `node`/`deno` no PATH automaticamente e utiliza o
   pacote local `yt-dlp-ejs`, incluído por `yt-dlp[default]`.
3. Extraia o código e abra um terminal na pasta que contém `app.py`:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Abra o endereço mostrado pelo Streamlit, normalmente `http://localhost:8501`.
No Windows, se necessário use `py -3.12` em vez de `python`.

A interface é inteiramente Python/Streamlit. Node.js/Deno **não servem a
interface**: são auxiliares opcionais de execução do player utilizados pelo
yt-dlp. Não é preciso instalar pacotes npm.

O FFmpeg é fornecido pelo pacote `imageio-ffmpeg` nas plataformas com wheels
compatíveis. Não é preciso instalar Calibre, React ou banco de dados.
Se o binário não estiver disponível para seu sistema, instale FFmpeg e defina
a variável `IMAGEIO_FFMPEG_EXE` com o caminho do executável.

## Como usar

1. Cole uma URL HTTPS de playlist que contenha `list=...`.
2. Clique em **Carregar playlist**.
3. Selecione até 20 vídeos ou use a ação para selecionar um lote.
4. Escolha a resolução máxima. Uma opção de 1080p não melhora um vídeo de 360p.
5. Confirme que possui autorização para os downloads.
6. Inicie o download e aguarde o progresso.
7. Baixe o ZIP. Se algum vídeo falhar, a interface informa qual e por quê.

Alterar o link limpa a consulta anterior. Alterar seleção ou qualidade invalida
o ZIP anterior. A aplicação não mistura resultados entre sessões.
Vídeos indisponíveis ou repetidos podem ser omitidos da consulta.

## Limites desta versão

- Primeiros **200 itens** consultados de cada playlist.
- Até **20 vídeos** por lote.
- Até **120 MB por vídeo** e **300 MB de mídia por lote**.
- Até **60 minutos de duração** por vídeo; transmissões ao vivo são rejeitadas.
- Até **60 segundos** para consultar e **240 segundos por vídeo**.
- Somente MP4 compatível, preferindo H.264 + M4A; se não houver formato
  compatível na resolução máxima escolhida, o vídeo falha explicitamente.

O limite é de mídia: o ZIP contém ainda um pequeno relatório e cabeçalhos.
Arquivos parciais de um vídeo são removidos em caso de falha. Durante a
junção de áudio e vídeo, o uso temporário de disco pode superar o tamanho final.
O ZIP é preparado na memória: hospedagens pequenas podem ficar sem recursos
mesmo com esses limites. Use lotes menores nesses ambientes.

## Criar seu repositório no GitHub

1. Crie um repositório, por exemplo `youtube-playlist-streamlit`.
2. Extraia o ZIP do código.
3. Envie **os arquivos**, não apenas o ZIP, por **Add file → Upload files**.
4. Deixe `app.py`, `downloader.py`, `youtube_worker.py` e `requirements.txt`
   na raiz.
5. Inclua também `README.md`, `NOTICE.md`, `.gitignore` e
   `.streamlit/config.toml`. Se seu seletor ocultar a pasta `.streamlit`,
   crie o arquivo pelo editor do GitHub.
6. Salve com **Commit changes**.

Alternativa usando Git:

```bash
git init
git add .
git commit -m "Adiciona downloader de playlists em Streamlit"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/youtube-playlist-streamlit.git
git push -u origin main
```

## Hospedagem e Streamlit Community Cloud

É possível hospedar uma interface Streamlit, mas **o funcionamento dos downloads
do YouTube em nuvem não é garantido**. O YouTube pode bloquear o IP do servidor
ou limitar as requisições. Verifique também os limites e termos da hospedagem.

No Streamlit Community Cloud:

1. Acesse https://share.streamlit.io/ e conecte o repositório GitHub.
2. Crie um app, escolha a branch e informe `app.py`.
3. Selecione Python 3.12 nas configurações avançadas e publique.
4. Se o ambiente não tiver Node.js/Deno compatível no PATH, configure um runtime
   suportado no ambiente de hospedagem. Sem ele alguns vídeos podem não funcionar.
   O `requirements.txt` instala pacotes Python, **não instala Node.js/Deno**.

Não coloque cookies, senhas ou tokens no repositório. Este app não precisa deles.
Se a hospedagem bloquear o acesso, use o código localmente; não há uma configuração
que garanta acesso ou dispense as verificações impostas pelo YouTube.

## Quando algo falhar

- **Verificação de bot, 403 ou 429:** aguarde ou tente executar localmente.
- **Privado, assinatura, restrição etária ou DRM:** não são suportados.
- **Formato indisponível:** escolha outra resolução. Alguns vídeos não oferecem
  um MP4 compatível.
- **Timeout ou tamanho:** faça lotes menores ou escolha resolução menor.
- **FFmpeg:** confira se a instalação do `imageio-ffmpeg` terminou corretamente.
- **Mudanças no YouTube:** atualize o yt-dlp:

```bash
python -m pip install --upgrade "yt-dlp[default]"
```

Depois atualize a versão no `requirements.txt` do seu repositório para manter
a instalação reproduzível. Não compartilhe seu ZIP de mídia se não tiver esse direito.

## Estrutura

```text
app.py                   Interface Streamlit
downloader.py            URLs, subprocessos, limites, lote e empacotamento ZIP
youtube_worker.py        Consulta e download via yt-dlp e FFmpeg
requirements.txt         Dependências
.streamlit/config.toml   Configuração Streamlit
.gitignore               Exclusão de mídia e dados locais do Git
NOTICE.md                Uso responsável, privacidade e licenças
README.md                Este guia
```

Leia `NOTICE.md` antes de usar ou redistribuir. O projeto não remove DRM,
não autentica contas e não contorna bloqueios do YouTube.
