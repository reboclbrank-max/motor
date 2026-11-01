# Autonomia: primeiro corte de integridade — 01/11/2026

## Pedido e escolha

Dono pediu reduzir a necessidade de conduzir cada etapa e obter um ciclo pedido→plano→execução→estado→retomada→entrega comprovada. Aceito o primeiro corte: duas falhas reproduzidas da sincronização e isolamento do pedido durante entrada, retomada e fila. Alternativas recusadas nesta rodada: mais comandos, executor genérico, ativar supervisor, aumentar cron, iniciar marketing e alegar autonomia completa com testes verdes.

## Mudanças

- Baixar valida SHA dos bytes e grava arquivos atomicamente. Só um download completo estabelece o manifesto `.memoria-sync.json`, fora da memória e ignorado pelo Git; contém apenas escopo e versões, não conteúdo/token.
- Subir distingue cópia intocada, conteúdo já confirmado na API e alteração local. Usa a versão-base; divergência concorrente não é sobrescrita usando SHA recém-lido.
- Remoção remota não ressuscita cópia local intocada; arquivo novo que colide com outro escritor não é sobrescrito. Não apaga arquivos do remoto.
- Falha individual de download, disco, upload ou recibo torna o resultado não zero. Sem base completa válida, não sobe arquivos órfãos/antigos. HTTP409 continua protegido pelo SHA do GitHub.
- PUT só é confirmado quando o SHA retornado corresponde ao conteúdo. Subidas confirmadas atualizam a base local para repetição idempotente.
- Pedido da casa usa ContextVar e acompanha o contexto de origem do trabalho, com restauração garantida inclusive em exceção. A mesma cobertura atende a entrada normal, a retomada antecipada e cada item da fila. A verificação existente de pedido explícito para publicação foi preservada, não substituída por outra política.
- Novos contratos entram na barreira do atendimento e na suíte geral. A integração pública teste-chat.py foi separada do laço offline. A suíte geral deixou de receber PAT/sincronizar memória sintética; teste não deve publicar seus dados na memória real.

## Validação e limites

Dois novos arquivos: 20 contratos de sincronização e oito de contexto. Incluem dois escritores divergentes, API direta+espelho, criação, remoção remota, HTTP409 após listagem,503, disco, SHA incorreto, recibo ausente, manifesto inválido/ausente/outro escopo, fila, retorno antecipado de retomada, exceção e contextos independentes. Transporte/modelo substituídos por mocks e diretórios temporários. Nenhuma postagem, dispatch, conversa real ou segredo usado nos ensaios.

A regressão completa e a versão efetivamente integrada são registradas na Base junto da promoção. Testes locais não provam queda real do Actions nem disponibilidade do provedor. A integração pública é GET real identificado separadamente, não teste offline.

## O que ainda falta

Não existe merge automático de memórias divergentes ou transação entre arquivos. Conflito protege a versão remota e sinaliza falha: isso não garante recuperar uma edição apenas local se o runner for descartado. Uma retomada deve partir do pedido/trabalho já persistido, não do manifesto efêmero. Manifesto não é backup, fila distribuída nem prova de qualidade. No caminho somente local sem base válida não se finge salvamento.

Não corrigidos neste corte: merge de fila no Site, laço do Site com falso verde, URLs, sete marcadores de ferramentas, diagnóstico da interface, reconciliação de marketing, integração das filas/memórias, avaliação de qualidade ou exatamente-uma-vez para ações externas. Sem alteração de canal/cron/segredo/permissão/infraestrutura. Falta ensaio real isolado de tarefa com interrupção e retomada. Não declarar o sistema autônomo de ponta a ponta.

## Rollback

Reverter o conjunto desta PR restaura sincronização/contexto e barreiras anteriores, mas reintroduz os defeitos. O manifesto local pode permanecer ignorado e será invalidado no próximo download do código novo. Não reverter dados, memória ou recibos privados nem reexecutar ordens históricas como parte do rollback.
