# Ensaio de restauração offline de espelhos — 03/11/2026

**Objetivo:** demonstrar em arquivos fictícios o ciclo de criar uma nova cópia a partir de um snapshot local, sem eliminar dados ou usar credenciais.

O módulo `restauracao_espelho.py` oferece `ensaiar_restauracao(origem, destino)`, usado apenas quando chamado explicitamente. Ele:
- exige destino inexistente e recusa origem/destino sobrepostos;
- faz inventário de arquivos regulares e SHA-256, bloqueando symlink, hardlink e arquivo especial;
- copia para pasta nova, compara os hashes de origem e destino e recusa qualquer diferença;
- em falha, não declara sucesso nem limpa automaticamente o destino parcial;
- não tem comandos Git, API, rede, PAT, cron, upload, exclusão ou promoção.

Os testes de `teste-restauracao-espelho.py` usam apenas diretórios temporários e conteúdo fictício, cobrindo cópia integral, destino ocupado, link, sobreposição, fonte vazia, erro de cópia e hardlink. A CI principal do Motor executa esse teste na barreira isolada.

**Limitações:** não é uma restauração dos espelhos privados verdadeiros, nem um plano automático de disaster recovery; arquivos extras, lacunas e diferenças históricas permanecem pendentes de revisão. Uma restauração real exige identificação da fonte aprovada, comparação de commits, destino temporário, autorização e prova externa independente. Não há garantia de zero perda em falhas simultâneas.

Rollback: reverter PR pelo fluxo normal, conferir pin do worker privado, preservar arquivos e estados reais.
