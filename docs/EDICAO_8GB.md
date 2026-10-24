# JARVIS 8 GB — brilho de voz

Esta edição mantém a conversa por voz e os comandos. A área central mostra
somente um brilho que pulsa com a fala, sem armadura WebGL, cérebro 3D ou
processo Chromium ao iniciar. Sketchbook, instrumentos e Libras abrem o
módulo 3D/WebEngine somente quando solicitados; feche essa janela para liberar
os recursos. A animação de abertura, a detecção de palmas e serviços
automáticos opcionais ficam desligados no iniciador leve. O modelo local
começa no modo Normal (1B), sem carregar modelos grandes na abertura.
O detector local da frase de chamada também fica desligado: assim ele não
carrega o modelo Whisper em segundo plano. A conversa normal por microfone
continua disponível.

Os atalhos Câmera, Gestos, Desenho e Braille funcionam sob demanda. NVIDIA
Camera Lab depende de uma instalação separada do `NVIDIA_AI_ART_STUDIO` no
Desktop, ou da variável `JARVIS_NVIDIA_STUDIO` apontando para `art_studio.py`.
O botão Spotify verifica a API e, se a sessão expirou, inicia uma nova
autorização local pela porta 8888; renovar o plano não renova o token sozinho.
O WhatsApp local requer API Bird instalada e pareada no PC de destino, com
consentimento explícito para cada destinatário e confirmação antes do envio.

O iniciador `INICIAR_JARVIS_8GB.bat` solicita permissão de administrador pelo
UAC a cada abertura. Se cancelar, o Jarvis não inicia. Isso amplia o acesso
do controle do PC; use somente com sua própria conta e revise operações
sensíveis. No Nexus Lab há atalhos para controle do PC e agente de programação.
O agente cria sempre uma pasta de projeto nova em `Desktop/JarvisProjects` e
pede confirmação antes de começar. Quando o Jarvis está elevado, ele não
instala dependências nem executa automaticamente o código que a IA gerou.

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
