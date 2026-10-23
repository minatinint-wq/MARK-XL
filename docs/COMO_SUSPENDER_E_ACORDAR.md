# Suspensão e resposta de voz — MARK XLIV

- Diga **Jarvis, desliga** para suspender o assistente. A sessão Gemini, o streaming Fish e a reprodução de áudio são encerrados; a câmera e os gestos param. A UI permanece aberta.
- O reator fica **vermelho e parado**. Os olhos e as luzes laterais da máscara ficam apagados. O visual passa a atualizar apenas duas vezes por segundo.
- Diga **Jarvis, acorda** para retomar. Durante a suspensão só um reconhecedor local procura essa frase; outras falas não executam comandos e não são enviadas ao Gemini. A escuta local não salva gravações.
- Os mesmos comandos funcionam na caixa de texto. Durante a suspensão, outros comandos digitados também são ignorados. O log indica quando a escuta local está pronta.
- Ao acordar, o processo de escuta local é encerrado, liberando seu modelo; a sessão online é recriada e a iluminação e animação retornam. A câmera só reabre mediante seu comando.

A suspensão mantém o aplicativo e o reconhecedor local necessários para acordar. Aplicativos que você abriu, como Spotify e Studio, continuam sob seu controle.

## Caminho da resposta

Microfone PCM16 de 16 kHz → ganho e supressão locais → Gemini Live (entendimento e resposta) → texto incremental → Fish Audio PT-BR → alto-falante.

O áudio nativo do Gemini é guardado para fallback. Fish WebSocket permanece prioritário; se falhar, tenta a mesma voz Fish via HTTP. Gemini só é reproduzido após falha das duas tentativas Fish. Nenhum modelo pago foi adicionado.

A voz Fish voltou ao envio por frases: libera na pontuação, a cada sete palavras ou ao finalizar a resposta. Não troca de voz apenas por demora.

## Recuperação e captura

- Erros 1011 dentro de ExceptionGroup agora são identificados. Primeira nova tentativa após 0,75 s, com espera progressiva se as quedas persistirem. Limite de cota mantém uma espera maior.
- A sessão caída libera o dispositivo de reprodução e suas filas antes de reconectar. Comandos já executados não são repetidos automaticamente.
- O microfone usa blocos de 40 ms e captura de baixa latência, com tolerância de 600 ms para pequenas travadas do notebook. O RNNoise roda fora do loop de rede; as filas continuam limitadas para evitar fala antiga acumulada.
- Pacotes de silêncio não apagam mais o sinal de fim da resposta, evitando prender o estado de fala e bloquear o próximo comando.
- A pausa após a reprodução passa a 300 ms mais o áudio ainda no dispositivo.
- Mensagens digitadas declaram explicitamente o papel user.

Gemini e Fish continuam sendo serviços externos e podem apresentar espera ou indisponibilidade. A captura e a suspensão local não eliminam falhas no servidor.

O Gemini Live usa thinking_budget=0 para reduzir a espera de raciocínio na conversa. O modelo e a voz permanecem os mesmos.
