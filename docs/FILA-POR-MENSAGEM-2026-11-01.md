# Fila individual por mensagem — 2026-11-01

A unidade de trabalho passa a ser a abertura da conversa (aNUMERO) ou cada comentário
(cID), não somente a última fala. Cada pedido do dono sem marca de entrega é listado
em ordem cronológica. Resposta posterior ou fala automática não apaga pedido anterior.
Autoria e assinatura são verificadas ao aceitar uma marca de resposta.

As mensagens e marcas remotas sobrevivem à troca do runner; não há fila apenas em RAM.
Isso NÃO constitui transação exatamente-uma-vez nem checkpoint dentro de ferramentas.

## Migração do histórico
Auditoria autenticada encontrou 17 mensagens antigas sem marca individual. Não se
pode concluir que sejam tarefas não realizadas: versões antigas não tinham o mesmo
contrato. Elas estão em MEMORIA/fila-revisao-historica.json no repositório PRIVADO,
com estado revisao_historica. Não são marcadas respondidas nem reexecutadas. Revisão
exige leitura/decisão do dono, sobretudo para antigas ações externas. Nenhuma mensagem
nova entra automaticamente nesse registro. Não é expiração por idade.

O atendimento exige o arquivo de revisão histórica. Ausência ou formato inválido
interrompe com erro, em vez de reativar histórico sem revisão.

## Testes
24 arquivos de teste locais passaram; oito casos novos. O teste legado de ignorar a
conversa quando o robô fala por último foi substituído pelo contrato correto: a fala
do robô é ignorada, mas a pergunta anterior ainda não entregue continua na fila.

## Limites que permanecem
GitHub Actions continua efêmero, com quotas/termos e timeout. Não é hospedagem 24/7.
A fila atual continua nas issues abertas e não cobre conversas fechadas. Aviso de
falha assinado ainda pode ter marca de entrega; não significa tarefa concluída.
Não há posse distribuída ou garantia de idempotência de qualquer efeito externo.
Contexto, saída, rodadas de ferramentas e limites de provedores não foram removidos.
Não remover autenticação/segredos como se fossem limitação de capacidade.
