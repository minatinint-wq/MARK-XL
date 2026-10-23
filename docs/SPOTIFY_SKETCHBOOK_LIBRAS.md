# Spotify, mãos e Libras

## Spotify

Os dois caminhos (`spotify_control` e `smart_home` com `domain=spotify`) usam o mesmo controle de reprodução pela API. Nomes completos exibidos, como `iPhone (Smartphone)`, e IDs são aceitos. Nomes ambíguos precisam ser especificados; o Jarvis não escolhe outro aparelho silenciosamente.

Exemplos: “Spotify, volume em 80% no iPhone”, “aumentar volume do Spotify em 10”, “pausar Spotify no iPhone”. O volume absoluto usa `action=volume, value=80`; o relativo usa `volume_up`/`volume_down`, com passo padrão de 10. A API deve estar autorizada e o aparelho visível no Spotify Connect.

Erros de permissão, player indisponível e limite de chamadas são apresentados sem repetir o comando em outro dispositivo. Quando o aparelho informa `supports_volume=false`, o volume precisa ser ajustado nele. Referências: [volume na API Spotify](https://developer.spotify.com/documentation/web-api/reference/set-volume-for-users-playback), [dispositivos disponíveis](https://developer.spotify.com/documentation/web-api/reference/get-a-users-available-devices).

## Sketchbook

Cada mão controla um pincel independente:

- Indicador estendido, demais dedos recolhidos: desenhar.
- Mão aberta: mover o cursor sem desenhar.
- Punho totalmente fechado, incluindo polegar recolhido: borracha.
- Retirar uma mão: termina apenas o traço daquela mão.

Uma mão pode apagar enquanto a outra desenha. Fechar uma forma não interrompe o pincel: o ajuste geométrico acontece quando essa mão solta o gesto. Desfazer/refazer inclui a borracha, preservada no PNG e no JSON editável. A borracha é uma operação branca sobre o papel branco.

O alcance padrão usa os 60% centrais da câmera para preencher o quadro inteiro. Diminuir **Alcance** exige menos movimento. **Calibrar cantos** permite apontar primeiro para o canto superior esquerdo confortável e depois para o inferior direito, segurando cada posição por um segundo. Abra a mão antes de retomar o desenho. A calibração vale durante a sessão; é possível cancelar sem substituir o alcance anterior. A moldura amarela na câmera mostra a área ativa.

## Libras

Abra **Libras** na barra do 3D ou diga “Jarvis, modo Libras”. Esse modo fecha o Sketchbook e impede gestos de girar a armadura. A câmera e a interpretação ficam nesse painel.

1. Enquadre rosto, tronco e as duas mãos.
2. Escolha sinais do cotidiano, alfabeto/soletração ou frase curta.
3. Clique **Interpretar gesto · 4 s** e faça o sinal. A prévia é espelhada, mas os quadros enviados não são invertidos.
4. Confira a sugestão. **Usar sugestão** copia para a mensagem editável. **Enviar ao Jarvis** envia somente o texto revisado como um comando comum.

A opção **Captura contínua** faz novas sequências, com intervalo mínimo de oito segundos entre pedidos. Fechar, limpar ou suspender descarta resultados atrasados; sair do modo encerra a câmera. A análise não roda no loop de áudio. O detector de mãos e o 3D reduzem trabalho enquanto o painel Libras está aberto.

**Limitação:** interpretação experimental pelo Gemini já configurado, não um modelo de Libras treinado e validado com sinalizantes. Não promete reconhecer todo o alfabeto, todas as palavras, variações regionais ou frases. Sem evidência suficiente, pede repetição e não inventa um comando. Referências didáticas: [Manuário INES](https://manuario.ines.gov.br/) e [Signbank UFSC](https://signbank.libras.ufsc.br/).

Ao clicar para interpretar ou ativar captura contínua, até 20 quadros da câmera vão ao Gemini, usando sua cota. Eles ficam temporariamente na memória, sem salvar vídeo em disco. No controle 3D e no Sketchbook, os quadros da câmera continuam locais; a interpretação do Sketchbook envia apenas o desenho.

## Validação desta entrega

Testes automatizados de reprodução/dispositivos/erros, duas mãos, borracha, alcance, calibração, salvamento, exclusividade e descarte de respostas atrasadas. API Spotify validada no notebook mantendo o volume existente em 80%; o iPhone estava ausente da lista no teste real. API Gemini validada com quadros sintéticos sem sinal, retornando “não reconhecido”. Não foi medida a precisão de tradução de Libras real; os testes de movimento usam pontos simulados.


## Webcam, gestos e modos — 09/09/2026

O desenho confirma o indicador por 100 ms e o punho fechado por 340 ms. Uma falha de rastreamento de até 320 ms pausa a tinta e preserva o traço; perdas maiores terminam o segmento. Saltos de posição não viram riscos atravessando a tela. Cada mão mantém seu próprio pincel/borracha. A câmera solicita 640×480 e o reconhecimento continua no worker, sem fila de frames.

- 👉👈: segure os dois indicadores frente a frente por cerca de 0,6 s para inserir um quadrado.
- Círculo: faça duas mãos curvas em C, voltadas uma à outra; segure e afaste para criar e ampliar.
- Retângulo: dois gestos em L/arma, com indicador esticado e polegar aberto; afaste para dimensionar.
- Solte o gesto para fixar a forma. Desfazer remove a forma inteira. Calibrar cantos e Alcance continuam disponíveis.

Diga ou digite “Jarvis modo evil”/“modo devil”: iluminação vermelha e voz Gemini Algenib com interpretação grave e teatral. “Jarvis modo anjo” (também angel/fofo): iluminação branca e voz Gemini Leda com interpretação doce. “Jarvis modo normal” restaura a aparência anterior e a voz Fish configurada. O modo Normal só usa o áudio Gemini após falha nas duas tentativas Fish (WebSocket e HTTP); não há corrida por tempo. Os modos especiais selecionam deliberadamente o áudio nativo e não chamam Fish.

“Jarvis desliga” e “desliga” suspendem, inclusive com Sketchbook aberto. O nome antigo shutdown_jarvis agora também suspende e não encerra o processo. A UI fica aberta, máscara apagada e reator vermelho; “Jarvis acorda” reativa.

Validação: gestos com landmarks simulados, interface Qt/WebGL real e roteamento de voz com serviços simulados. Nenhuma cota Hugging Face usada. A precisão na webcam física e a interpretação vocal gerada precisam ser conferidas no uso.

Atualização de 10/09/2026: veja SKETCH_E_ESTUDIO_MUSICAL.md para mindinho/mover, quadrado redimensionável, os 128 timbres e os novos tempos de Libras.
