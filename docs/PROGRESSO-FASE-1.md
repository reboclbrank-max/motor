# Progresso — Fase 1 da autonomia segura

## Linha do tempo versionada

| Corte | Entrega | Referência |
|---|---|---|
| Fase 0 | Contenção e privacidade na `main` | PR #36; Site PR #7 |
| Fase 1A | Outbox durável, payload imutável, SHA otimista, reconciliação e 19 contratos | PR #37; run 41661496248 |
| Fase 1B | Adaptador de comentários shadow, marcador determinístico e reconciliação paginada | PR #38; run 41667764095 |
| Fase 1C | Fiação opcional no respondedor, desativada por padrão e sem fallback após incerteza | PR #39; run 41669164084 |
| Gate sintético | 10.000 tarefas, cinco classes de falha, sem duplicidade externa no ensaio | PR vinculada a este documento |

## Próximos gates

1. Compatibilidade adicional e ensaio de retomada da fiação ainda desativada.
2. Shadow operacional sem efeitos externos.
3. Canário pequeno e reversível, somente depois de revisão.

Os quatro publicadores antigos permanecem desativados. Nenhuma mensagem histórica entra
na migração ou nos testes. O progresso central entre repositórios também é registrado no
repositório privado `reboclbrank-max/ambiente`.
