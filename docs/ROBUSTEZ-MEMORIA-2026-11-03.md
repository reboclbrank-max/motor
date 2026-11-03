# Robustez da memória privada — 2026-11-03

## Incidente observado e escopo

Em 2026-11-03, o workflow público `batente` (run 41703359179) concluiu com falha na etapa de baixar a memória privada; o ciclo de checkup não foi executado. Outro ciclo anterior havia concluído com sucesso. A fotografia de jobs é insuficiente para afirmar se o motivo foi rede, limite de API ou credencial. Não foram lidos conteúdos de memória, log privado, segredos ou mensagens.

## Correção conservadora

- Leituras GET da API recebem no máximo três tentativas, com pausas de 0,5 e 1 s, exclusivamente em falha de conexão/tempo ou HTTP 429, 500, 502, 503 ou 504. Não insiste em 401/403.
- Qualquer escrita PUT conserva tentativa única: não reenvia uma operação cujo resultado remoto pode ser desconhecido.
- Falhas na leitura da árvore, de blobs ou de manifesto registram apenas categoria e código de HTTP, sem URL, header, exceção textual ou conteúdo.
- Uma transferência incompleta continua sem manifesto válido: a etapa de upload nunca deve regravar memória a partir de um download parcial.

## Provas e limites

O contrato offline `teste-sincronizacao-versao.py` passou a cobrir 503 transitório seguido de sucesso, 401 sem repetição e PUT sem retry. O workflow `testes.yml` já executa essa suíte em PR; promover somente com CI comprovada e verificação do SHA remoto. Esse endurecimento não repara token ausente, escopo insuficiente, revogação nem serviço totalmente indisponível; tais casos ficam bloqueados e pedem investigação sanitizada. Sem aumento de periodicidade, novo cron, segredo, conta, custo, postagem ou alterações no repositório privado de memória.
