# Segurança dos espelhos — 03/11/2026

A auditoria encontrou dois problemas verificáveis: o workflow não oferecia a variável CHAT_TOKEN exigida pelo espelhador, embora injetasse diversas credenciais de IA/marketing que não eram necessárias; e o código apagava recursivamente todos os arquivos de destino antes de copiar.

## Mudança
- O workflow continua **manual**, sem agendamento novo, e agora fornece apenas o segredo já existente PAT_MEMORIA como CHAT_TOKEN, exclusivamente ao passo do espelho; não cria, revela ou altera a credencial.
- Foram retirados os passos de baixar/subir MEMORIA: o espelhador já clona diretamente os dois repositórios. Eles acrescentavam um caminho desnecessário de escrita em memória privada.
- A sincronização confere arquivos regulares por hash, recusa arquivos especiais e links, bloqueia conteúdo no destino ausente na origem e nunca apaga automaticamente arquivos extras.
- A cópia é feita apenas no clone temporário do espelho, com segunda conferência de todos os bytes antes de commit/push. Se houver falha, nenhuma gravação remota é feita.
- Testes com diretórios fictícios cobrem conteúdo extra, atualização sem exclusões, links/FIFO e erro de cópia. A CI de PR também roda o contrato do workflow.

## Limites
Esta mudança **não comprova restauração de espelhos reais** nem recuperação de desastre. A comparação observada encontrou itens extras em agente-espelho: uma execução nesse estado será recusada até revisão, sem exclusão automática. Não executamos o workflow manual nem lemos conteúdo privado dos arquivos. Falhas concorrentes de escrita remota podem ainda bloquear push; não há transação em dois repositórios.

Rollback: reverter PR pelo processo normal e conferir pin da agenda do Agente com o Motor aprovado; manter conteúdo e histórico dos espelhos.

## Complemento — menor exposição de credencial nos subprocessos Git
Depois de clonar as fontes com autorização, os comandos locais `git add`, `git status` e `git commit` recebem somente um ambiente com PATH/HOME/idioma/TMPDIR e `GIT_TERMINAL_PROMPT=0`, sem token ou extraheader. O `git push` continua recebendo a autenticação efêmera, por ser uma operação remota. Teste adicional usa segredo falso e verifica presença somente no push. Não houve troca, rotação ou leitura do valor real da credencial.
