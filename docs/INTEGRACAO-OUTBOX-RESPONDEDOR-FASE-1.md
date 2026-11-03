# Fase 1C — integração opcional da outbox ao respondedor

## Estado de ativação

A fiação existe, mas **está desativada por padrão**. O caminho legado só é substituído
quando `REBOCL_OUTBOX_COMENTARIOS=1` estiver explicitamente definido. Nenhum workflow
recebe essa variável neste corte; portanto, o comportamento de produção não muda.

## Proteções

- O POST preserva byte a byte o payload que será reconciliado.
- A transformação legada da marca de robô ocorre antes de fixar o payload.
- Criação e edição usam a outbox e a reconciliação paginada da Fase 1B.
- Resultado incerto de edição não cai em um novo POST legado.
- Valores como `true` ou `0` não ativam a integração; somente `1`.

## Limites

Não houve ativação, leitura de conversas reais, publicação ou reprocessamento histórico.
Os testes usam fiação e destinos simulados. Antes de qualquer shadow operacional são
necessários testes de compatibilidade adicionais, ensaio de falhas e revisão explícita.
