# Confirmação de entrega no motor em uso — 2026-11-01

## Alteração
Reaproveita o varredor atual, incluindo janela de 168h, identificação de falas do robô,
diagnóstico e encadeamento já existentes. Não substitui pelo varredor antigo do privado.

Agora o varredor confere o comentário na API antes/depois de executar o responder.
Confirma assinatura, autor permitido e marca; pagina comentários. Processo que termina
sem entrega ou sai com erro não conta como resposta. Falha de consulta não é fila vazia.
Restaura ambiente e remove o evento temporário. Teste offline entra antes do atendimento.
Não muda cadência, destinatários, limites de rodada, provedores, memória ou marketing.

## Evidências
- 21/21 arquivos teste-*.py executados localmente com saída zero.
- 16 casos novos de contrato, incluindo execução do principal/exatidão/registro reais
  com transporte simulado, memória em disco e reentrada sem duplicar.
- Leitura autenticada real: 37 GET, nenhuma escrita, nenhuma pendência observada.
  Não processou mensagens nem invocou modelos, não prova disponibilidade contínua.
- Teste de segurança de workflows repetido após inclusão do novo teste: passou.

## Limites
Entrega de comentário NÃO prova tarefa cumprida nem resposta correta. Aviso de falha
assinado pode contar como entrega. Não há posse distribuída nem garantia exactly-once.
A consulta anterior ao envio não elimina corridas com outro processo. Não ativar o
supervisor experimental concorrendo com o atendimento. A janela de issues e limites
de rodada existentes permanecem. Não há hospedagem permanente nova nem SLA universal.

A alteração elimina um falso positivo técnico conhecido; não torna o agente humano,
consciente, ilimitado ou capaz de cumprir sozinho todas as metas.
