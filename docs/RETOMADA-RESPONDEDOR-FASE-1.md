# Retomada da fiação do respondedor — Fase 1

## Objetivo

Validar a integração opcional da outbox atravessando reinícios de processo, sem usar
conversas, comentários, memória ou credenciais reais. Este corte adiciona somente testes
e documentação; não ativa `REBOCL_OUTBOX_COMENTARIOS` em nenhum workflow.

## Método

`teste-responder-retomada.py` executa cada tentativa em um processo Python novo. Um
arquivo temporário representa tanto os checkpoints da outbox quanto os comentários
remotos sintéticos. As chamadas de `comum.gh` e `comum.editar_comentario` são substituídas
por esse destino determinístico, e o worker recebe somente variáveis de ambiente básicas.

O ensaio injeta falhas antes e depois dos efeitos e verifica:

1. falha depois do POST: um comentário permanece, a intenção fica incerta e o processo
   seguinte confirma por reconciliação, sem segundo POST;
2. nova execução já confirmada: nenhum efeito adicional;
3. evidência confirmada que desaparece: novo POST permanece bloqueado;
4. falha antes do POST sem evidência: a retomada continua incerta e não faz retry cego;
5. evidência tardia: é adotada sem nova tentativa;
6. mesma origem com payload diferente: conflito explícito, sem publicação;
7. falha depois da edição: o processo seguinte confirma o mesmo comentário, sem reeditar
   e sem criar POST de fallback.

## Resultado local antes da PR

- **20/20 contratos aprovados**;
- uma tentativa de efeito por intenção nos cenários de incerteza;
- zero fallback para o publicador legado;
- zero chamadas a provedores ou canais reais;
- zero leitura ou alteração de histórico real.

A CI da PR precisa repetir a suíte isolada e a suíte completa antes do merge. O resultado
local não substitui esse gate.

## Limites

O destino sintético não prova comportamento de uma API real, entrega externa, desempenho
em produção ou exactly-once. Incertezas sem evidência continuam exigindo reconciliação
ou revisão. A fiação real permanece desativada por padrão; shadow operacional e canário
reversível continuam sendo gates posteriores.
