# Espelho Gmail no Jarvis

O botão **E-MAIL** (ou comando “Jarvis, abrir Gmail”) mostra somente
**remetente, assunto e data** da caixa de entrada. Clique numa linha para abrir
a conversa no Gmail. Não há busca automática em segundo plano, leitura do
corpo/anexos, envio, exclusão nem alteração de rótulos.

## Conectar sua conta

1. No [Google Cloud Console](https://console.cloud.google.com/), crie um
   projeto seu, ative a **Gmail API** e configure a tela de consentimento.
2. Crie um **OAuth Client ID → Desktop app**. Baixe o JSON e salve-o como
   `config/gmail_oauth_client.json` na instalação privada do Jarvis.
3. Instale `google-auth-oauthlib` no Python do Jarvis caso seu pacote ainda
   não o inclua. No pacote completo ele já deve estar presente.
4. Abra o Jarvis, clique **E-MAIL → Conectar Gmail** e autorize no navegador.
   Confirme que a permissão solicitada é apenas metadados de e-mail.

O token fica cifrado por DPAPI para **este usuário deste PC** em
`config/.gmail_token.dpapi`. Em outro computador é necessário conectar de
novo. O JSON OAuth e o token estão ignorados pelo Git. Não coloque credenciais
em `api_keys.json` nem mande o JSON por chat público.

O escopo utilizado é `https://www.googleapis.com/auth/gmail.metadata`; ele
permite a lista e os cabeçalhos, mas não o texto da mensagem. A interface
consulta no máximo 12 mensagens por clique. O Jarvis não usa SMTP.
