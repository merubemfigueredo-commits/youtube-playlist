# Uso responsável e privacidade

Baixe somente vídeos de sua autoria, em domínio público ou cujo titular tenha
autorizado o download. Respeite os termos do YouTube e as leis aplicáveis.
Este projeto não é afiliado ao YouTube ou Google.

O aplicativo não remove DRM, não usa cookies de contas, não acessa playlists
privadas e não contorna restrições de idade, assinatura, região ou verificações.
Uma URL acessível publicamente não significa que você tem direito de baixar
ou redistribuir o vídeo. A confirmação na interface não concede esses direitos.

## Dados

O servidor que hospeda o aplicativo se comunica diretamente com o YouTube e os
servidores de mídia dele. O link consultado é transmitido ao YouTube. Não há
serviço externo intermediário de download nem banco de dados de vídeos.

Cada lote usa uma pasta temporária própria, removida ao concluir o processamento
ou em erros tratados. O ZIP permanece na memória da sessão para download.
Encerramentos abruptos do servidor podem deixar temporários até a limpeza do
ambiente de hospedagem. A função de limpar descarta o resultado da interface;
o ciclo de vida dos downloads já servidos também depende do Streamlit.

## Dependências e implantação

Streamlit, yt-dlp, yt-dlp-ejs, imageio-ffmpeg e o binário FFmpeg distribuído
com ele possuem licenças próprias. Consulte os avisos de cada projeto antes
de redistribuir executáveis ou incorporar o código a um produto comercial:

- https://github.com/streamlit/streamlit
- https://github.com/yt-dlp/yt-dlp
- https://github.com/yt-dlp/ejs
- https://github.com/imageio/imageio-ffmpeg
- https://ffmpeg.org/legal.html

O código-fonte para download não incorpora vídeos nem binários FFmpeg.
O gerenciador de pacotes instala as dependências.

Limites por sessão e subprocessos com timeout reduzem consumo acidental, mas
não substituem controles globais de concorrência, banda, disco e memória.
Não exponha esta versão como serviço público de alto tráfego sem acrescentar
esses controles e avaliar os termos de uso da hospedagem.
