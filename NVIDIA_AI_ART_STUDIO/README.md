# NVIDIA AI Art Studio integrado ao Jarvis

Esta pasta acompanha o Jarvis. Ela fica ao lado de `main.py`, em qualquer
diretório ou nome de usuário do Windows. O comando de voz **NVIDIA Camera Lab**
abre `art_studio.py --tab camera` com o mesmo Python do Jarvis.

O Studio usa `../config/api_keys.json` da instalação atual. Nenhuma chave
fica nesta pasta ou no patch público. Para testar sem voz, abra
`ABRIR_CAMERA_LAB.bat`; para validar a configuração sem expor a chave, execute
`Python\pythoncore-3.14-64\python.exe NVIDIA_AI_ART_STUDIO\art_studio.py --check`
na raiz do Jarvis.

A prévia da câmera é local. Quadros são enviados à API NVIDIA somente quando
você pede uma análise no Studio. Geração de imagem/vídeo também usa serviços
externos quando acionada. O Studio não depende do caminho do Desktop deste PC.
