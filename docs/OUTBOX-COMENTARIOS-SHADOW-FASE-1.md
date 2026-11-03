# Fase 1B — adaptador de comentários em shadow mode

## Escopo

`outbox_comentarios.py` liga o modelo de comentários à outbox somente por dependências
injetadas. O padrão é `shadow=True`: devolve o plano e não grava, não lê páginas e não
publica. Nenhuma parte do respondedor foi alterada neste corte.

## Reconciliação

- O comentário recebe `<!--outbox:ID-->`, derivado de tipo, destino e origem.
- Pendente/final e criar/editar têm identidades diferentes.
- A evidência exige autor da casa, assinatura, corpo integralmente igual e id observável.
- Marcador copiado por terceiro é ignorado; marcador da casa com corpo divergente bloqueia.
- Edição só aceita evidência no próprio comentário de destino.
- Duplicidade remota é incidente e não autoriza outra tentativa.
- A leitura percorre todas as páginas; página repetida ou erro não significa ausência.

## Validação e limites

Os contratos usam repositório e comentários sintéticos, sem rede. Cobrem shadow puro,
reentrada, queda após publicação, 205 comentários em três páginas, forja de autoria,
conteúdo divergente, duplicidade, edição idempotente e paginação sem progresso.

O adaptador ainda não está conectado ao respondedor. Não houve leitura de conversas reais,
publicação, reprocessamento histórico ou alteração da fila atual. Exactly-once continua
não garantido; a proteção é reconciliar ou bloquear antes de repetir.
