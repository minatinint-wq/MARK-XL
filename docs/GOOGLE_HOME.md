# Google Home no Jarvis

Casa: Grow jarvis.

Dispositivos configurados:

- Depósito: `smart plug`
- Depósito: `Cafeteira switch_1` (apelidos de voz: `cafeteira sweet`, `cafeteira switch 1`, `cafeteira do depósito`)
- Quarto: `Cafeteira` (apelido de voz: `cafeteira do quarto`)

Reinicie o Jarvis e peça "abrir google home". Faça login no navegador que ele abrir e selecione Dispositivos. O login no navegador do Codex não é compartilhado automaticamente. Peça o status do dispositivo específico antes de testar ligar/desligar.

A implementação reaproveita Playwright, verifica um cartão interativo único e lê o estado antes de clicar. Só confirma sucesso após mudança de estado. Mudanças de layout podem bloquear o controle. O clique real e o login ainda precisam ser validados neste navegador. Nenhuma API Google/Tuya foi configurada; voz usa o roteamento existente.

## Sessão persistente

Chrome usa sempre `%USERPROFILE%\.jarvis_profiles\chrome`. O próprio navegador mantém cookies e dados da sessão. Faça login uma vez nessa janela. Se o perfil estiver ocupado, o Jarvis informa o bloqueio em vez de criar outro perfil. Não foram copiados cookies de outros perfis. A conta Google ainda pode exigir nova autenticação por expiração ou revogação.
