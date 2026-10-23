# Instrumentos com as mãos

Abra Música, clique em Ampliar e depois em Usar mãos. A câmera aparece ao lado. O áudio é local e usa o banco de instrumentos já instalado.

## Violão, guitarra e baixo

O braço mostra oito casas e as notas de cada corda. Cada casa sobe um semitom. As pontas dos dedos são rastreadas separadamente. No modo Toque direto nas notas, coloque o dedo na casa para tocar. Segurar a posição não repete a nota; mudar de casa muda a altura. Os marcadores P/I/M/A/m identificam polegar, indicador, médio, anelar e mindinho.

Em 2 mãos: casas + dedilhado, uma mão seleciona as casas e a outra cruza as cordas no corpo do instrumento. A seleção das casas é atualizada antes do dedilhado, independentemente da ordem das mãos na câmera. Fechar a mão recolhe os dedos e permite reposicionar. O baixo usa quatro cordas. Mouse e teclas físicas continuam funcionando.

## Bateria

As baquetas seguem as palmas. Desça uma mão sobre um tambor para tocar. Levante essa mão antes de bater novamente. Cada mão mantém seu próprio estado, permitindo alternar golpes. Ficar parado ou mover só o indicador não produz batidas repetidas. Uma descida mais rápida produz um golpe mais forte.

## Teclado frontal

Selecione um piano e mantenha Frontal: pinça para tocar. Abra polegar e indicador, mire a tecla com o indicador, feche a pinça para tocar e solte para preparar outra nota. A tecla amarela é a selecionada. Durante o fechamento, a seleção fica presa à tecla que estava sob o cursor, evitando trocar a nota quando o indicador se desloca para encontrar o polegar. As duas mãos funcionam independentemente. Há também o modo anterior de toque direto pelo indicador.

## Movimento e limites

Cursores e baquetas são interpolados na animação, com previsão visual curta e limitada. Essa previsão nunca gera notas: os disparos usam as observações da câmera. A captura solicita 24 quadros/s e o processamento de mãos tenta até 20 vezes/s, com apenas um quadro em processamento e sem fila acumulada. A taxa real depende da câmera e da carga do notebook. É uma simulação com webcam comum; não mede contato físico ou profundidade como um sensor dedicado.

Verificação: 33 cenários automatizados de gestos/movimento e 81 verificações booleanas da interface, mais medição de áudio real. Incluem notas MIDI por casa, dedos independentes, notas da pinça, golpes de bateria, suspensão, sketchbook e Libras. O perfil gráfico compatível permanece ativo.
