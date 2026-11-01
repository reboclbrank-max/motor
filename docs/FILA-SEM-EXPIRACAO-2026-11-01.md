# Remoção de restrições locais da fila — 2026-11-01

Decisão atual: continuar no GitHub, sem cartão e sem hospedagem externa.
Não confundir essa decisão com hospedagem contínua ou recursos ilimitados.

## Alterações
- JANELA_HORAS padrão zero: mensagens não são ignoradas apenas por terem mais de sete dias.
- Lista todas as páginas de issues abertas, em vez de somente a primeira.
- MAX_POR_RODADA padrão zero: sem teto padrão de três respostas por quantidade.
- Retirado MAX_POR_RODADA=3 do workflow chat existente.
- Mantido limite positivo opcional, se configurado explicitamente pelo operador.
- Ao atingir 480 segundos entre tarefas, encerra lote e pede sucessor pelo mecanismo
  já existente quando houve progresso e sobrou trabalho. Não é cota diária.
- Falha ao pedir sucessor retorna erro observável. Sem progresso não gera laço.

## Validação
23 arquivos de teste locais passaram; sete casos novos de idade, paginação,
quantidade, handover, ausência de progresso, erro de dispatch e API ilegível.
Teste histórico de lote três continua com configuração explícita três; sua antiga
asserção de janela mínima foi atualizada para a regra nova sem expiração.
Um fake novo de paginação inicialmente entrou em loop por confundir page=1 com
per_page=100; corrigido o fake, reexecutada a suíte inteira. Não ocultar esse erro de teste.
Leitura real sem escrita: 41 GET, nenhuma mensagem pendente encontrada. Não foi
executada tarefa antiga nem feito dispatch manual nesta rodada.

## Limitações explícitas
- Limites do GitHub, APIs e recursos físicos não foram removidos.
- Timeout configurado do job de atendimento continua 12 minutos. O handover de 480s
  é contado após descoberta da fila, não após início do job; preparação e uma tarefa
  longa podem consumir o prazo antes de pedir sucessor. Não é garantia de continuidade.
- Se um job for interrompido, marcas permitem procurar entregas novamente; não há
  checkpoint das etapas internas de toda ferramenta nem posse distribuída.
- O varredor ainda atende a última fala pendente de cada conversa, não uma fila
  durável individual de todas as mensagens. Não declarar que todo histórico é atendido.
- Listagem ainda usa somente issues abertas e pode sofrer mudanças durante paginação.
- Outras quotas internas do projeto não foram removidas nesta alteração; limites
  do histórico, saídas, rodadas de ferramentas e estudo precisam de trabalho próprio.
- Não desativar autenticação, proteção de segredo ou checagem de autoria para simular
  liberdade. Não contornar quotas de terceiros nem fabricar atividade para evitar suspensão.
