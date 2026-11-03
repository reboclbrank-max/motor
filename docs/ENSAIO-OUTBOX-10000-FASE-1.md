# Ensaio da outbox — 10.000 tarefas sintéticas

## Metodologia

Cada tarefa tem conversa, origem e marcador próprios. Repositório e comentários são
simulados em memória; não há rede, segredos ou histórico real. Cinco classes de 2.000
tarefas: sucesso, perda de resposta após efeito, falha antes do efeito, perda do checkpoint
`em_envio` e perda do checkpoint `enviado`.

## Resultado antes do push

- 10.000 registros finais íntegros;
- 6.000 efeitos sintéticos confirmados, inclusive após reconciliação;
- 4.000 incertezas preservadas sem efeito indevido;
- 6.000 comentários sintéticos únicos;
- nenhuma duplicidade externa e nenhuma tarefa reenviada após incerteza.

A CI da PR repete o mesmo ensaio junto com a suíte completa. Isso não certifica integrações
reais nem exactly-once: prova apenas que os contratos sintéticos e as falhas injetadas
foram tratados sem duplicidade neste ensaio.
