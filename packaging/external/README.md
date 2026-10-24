# Assistente XLIV — edição externa (código-fonte)

Pacote para instalar no **Windows 10/11 de outra pessoa**, com interface leve
de brilho/voz e sem chaves, contas, contatos ou memórias do criador. É um
**pacote-fonte**, não um executável nem uma licença de marca pronta para venda.
O comprador instala as dependências e usa credenciais próprias. O iniciador
não solicita administrador.

## Instalação

1. Instale [Python 3.14 para Windows, 64 bits](https://www.python.org/downloads/windows/)
   e marque a opção do `py launcher`; reserve espaço para as dependências.
2. Extraia o ZIP numa pasta do seu usuário, por exemplo `Documentos\AssistenteXLIV`.
   Não execute diretamente de dentro do ZIP.
3. Execute `INSTALAR.bat` nessa pasta. O script cria `.venv`, instala
   `requirements.txt` e copia o exemplo para `config\api_keys.json` **somente
   se o arquivo ainda não existir**. Ele não pede administrador.
4. Crie **sua própria** chave Gemini no
   [Google AI Studio](https://aistudio.google.com/app/apikey). Abra
   `config\api_keys.json` e substitua `PASTE_YOUR_GEMINI_API_KEY_HERE` no
   campo `gemini_api_key`. Salve o arquivo. Não envie a chave ao vendedor.
5. Execute `INICIAR.bat`. Autorize o microfone no Windows se solicitado. A
   janela mostra o brilho falante e o campo de texto; digite uma mensagem
   curta para testar antes da voz. Se não ouvir resposta, confira o microfone,
   o dispositivo de saída e a cota/validade da chave no AI Studio.

O Jarvis atual usa o Gemini Live para a conversa por voz. A API pode ter
**cota gratuita apenas para projetos elegíveis**; limites, regiões, modelos e
preços mudam. Confira o [painel de uso/cotas](https://aistudio.google.com/)
e a [tabela oficial de preços](https://ai.google.dev/gemini-api/docs/pricing)
antes de ativar faturamento. Esta edição não promete uso ilimitado nem
operação 100% offline. Se a chave não tiver acesso gratuito, a conversa por
voz não será gratuita neste código.

## Chaves e integrações opcionais

| Recurso | Como obter | Onde configurar | Observação |
| --- | --- | --- | --- |
| Gemini (voz e respostas) | [AI Studio → API Keys](https://ai.google.dev/gemini-api/docs/api-key) | `config\api_keys.json` → `gemini_api_key` | Necessária para a conversa principal; use uma chave do comprador. |
| Gmail (lista de remetente/assunto/data) | [Gmail API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python): projeto Google Cloud, ativar Gmail API, consentimento e OAuth Client ID **Desktop app** | Baixe o JSON como `config\gmail_oauth_client.json`; depois clique **E-MAIL → Conectar Gmail** | Escopo `gmail.metadata`; não lê corpo/anexos, não envia. Cada comprador conecta sua conta. |
| Spotify | [Spotify Developer Dashboard](https://developer.spotify.com/dashboard): crie seu app e copie Client ID/Secret | Copie `config\spotify_credentials.example.json` para `config\spotify_credentials.json`, preencha os campos e registre a URI de retorno indicada no exemplo | A API em modo de desenvolvimento tem limites e exige Premium do proprietário do app; não é garantidamente gratuita. |
| NVIDIA API | [NVIDIA API Catalog](https://build.nvidia.com/) | `config\api_keys.json` → `nvidia_api_key` | Somente módulos de mídia compatíveis; podem exigir créditos ou elegibilidade. NVIDIA Camera Lab é instalação separada. |
| Ollama local | [Instalação do Ollama](https://ollama.com/download/windows) | Instale no mesmo PC e baixe um modelo compatível | Opcional e consome RAM/disco; não substitui automaticamente a chave Gemini da conversa principal. |
| WhatsApp Bird local | Instância Bird própria, instalada/pareada pelo comprador | Configure a URL/chave local conforme a documentação do módulo | O servidor Bird **não acompanha** este ZIP. Revise e confirme o destinatário antes de enviar. |

Não há chave compartilhada de IA remota do criador. O gateway remoto privado
fica desativado nesta edição. Não peça ao vendedor sua chave pessoal de
Gemini, Gmail, Spotify, NVIDIA ou outro serviço. Nunca publique
`config\api_keys.json`, `config\gmail_oauth_client.json`, tokens OAuth,
`.env` ou a pasta `.venv`.

## O que foi retirado

- Modelo 3D da armadura, reator, assets do laboratório e áudio de abertura:
  direitos de terceiros/procedência não verificados para revenda.
- Memórias do criador, dados pessoais, credenciais, tokens e runtime Python
  privado. O novo comprador começa sem dados de outra pessoa.
- Inicialização elevada, integração remota privada e atalhos de módulos 3D.

A voz Fish/um perfil de voz do criador vem desativado por padrão. A conversa
usa a saída de áudio Gemini quando disponível; para outro provedor de voz,
o comprador precisa cadastrar sua própria conta e verificar os direitos de
uso comercial da voz escolhida.

Alguns comandos opcionais do código histórico ainda dependem de outros
aplicativos ou de um cofre Obsidian configurado pelo próprio comprador. Eles
podem informar “indisponível” até a configuração; não são parte do teste básico
de voz e texto. Não prometa ao cliente que esses módulos funcionam sem setup.

## Licenças e venda

O código original de minatinint-wq neste pacote está sob [MIT](LICENSE).
Textos e elementos visuais originais têm a declaração separada de
[conteúdo autoral](CONTENT_LICENSE.md). Essas licenças **não cobrem** marcas,
personagens, software e serviços de terceiros. Este pacote não inclui as
bibliotecas Python: elas são instaladas pelo comprador e mantêm suas próprias
licenças.

**Antes de vender como produto fechado**, revise a marca/nome “Jarvis” e
remova referências a franquias/personagens; revise também a licença do
PyQt6. A distribuição com PyQt6 é GPLv3 ou requer licença comercial da
Riverbank para um produto incompatível com GPL. Licenciar o código original
como MIT não elimina essas obrigações. Esta nota não substitui avaliação
jurídica. O vendedor deve publicar termos de suporte, privacidade e limites
dos serviços externos sem prometer que APIs de terceiros serão sempre grátis.

## Teste rápido / diagnóstico

- `INICIAR.bat` não abre: verifique se `.venv\Scripts\python.exe` existe;
  caso contrário, rode `INSTALAR.bat` e leia o erro no console.
- “Chave inválida”/sem resposta: confira seu próprio projeto e cotas no AI
  Studio. Não use uma chave obtida em outro computador sem autorização.
- Microfone mexe no gráfico mas não transcreve: confira permissões de
  microfone do Windows e escolha o dispositivo correto; teste também texto.
- Spotify 403/404: cheque conta Premium, modo de desenvolvimento, URI exata
  de callback, lista de usuários autorizados e dispositivo de reprodução.
- Gmail não conecta: confira JSON OAuth Desktop, Gmail API ativada e tela de
  consentimento. O arquivo JSON não deve ir junto com cópias de venda.

Titular desta edição: **minatinint-wq**. Data de preparação: 24/10/2026.
