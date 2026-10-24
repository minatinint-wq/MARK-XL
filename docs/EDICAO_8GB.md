# JARVIS 8 GB — brilho de voz

Esta edição mantém a conversa por voz e os comandos. A área central mostra
somente um brilho que pulsa com a fala, sem armadura WebGL, cérebro 3D ou
processo Chromium. A animação de abertura, a detecção de palmas e serviços
automáticos opcionais ficam desligados no iniciador leve. O modelo local
começa no modo Normal (1B), sem carregar modelos grandes na abertura.
O detector local da frase de chamada também fica desligado: assim ele não
carrega o modelo Whisper em segundo plano. A conversa normal por microfone
continua disponível.

## No PC de destino

1. Faça uma cópia de segurança da pasta atual do Jarvis.
2. Copie **todo o conteúdo** do pacote privado para essa pasta, substituindo
   os arquivos da versão antiga. Mantenha a pasta `Python`/`.venv` já instalada
   no PC; ela não vai no pacote de atualização.
3. Inicie com `INICIAR_JARVIS_8GB.bat`, não com o iniciador padrão.
4. Na primeira abertura, a chave Fish é protegida para o usuário Windows do
   PC de destino e o arquivo temporário é removido. O token Spotify é
   importado se não houver uma sessão local; talvez seja preciso autorizar
   o Spotify novamente.

O pacote privado contém `config/api_keys.json` e outras credenciais **em
texto legível** até a migração. Transfira apenas por um meio de sua confiança;
não publique o pacote no GitHub, em chats ou em links abertos. Depois de
confirmar a instalação, remova as cópias extras do pacote de transferência.
As chaves não estão no repositório público.

Para preparar um novo pacote a partir desta instalação, execute
`python tools/build_lite_transfer.py --source CAMINHO_DA_INSTALACAO --output CAMINHO_PRIVADO`.
O script não altera a instalação de origem nem exporta o cofre de memórias.
