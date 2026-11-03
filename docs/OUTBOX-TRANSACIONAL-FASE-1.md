# Fase 1A — outbox transacional e reconciliação

## Escopo deste corte

Novo módulo `outbox.py` com uma intenção por arquivo em `MEMORIA/outbox/`. Ele ainda
**não está conectado ao respondedor nem a qualquer destino real**. Não muda a fila atual,
não reexecuta histórico e não publica comentários ou marketing.

## Invariantes

- A chave deriva de tipo, destino e origem. Outra mensagem tem outra chave.
- O payload fica imutável: mesma chave com corpo diferente exige revisão.
- Cada registro tem escrita otimista pelo SHA; conflito não sobrescreve outro escritor.
- Antes da primeira tentativa e depois do envio, o destino precisa ser reconciliado.
- Evidência remota encontrada é adotada, inclusive após queda entre envio e checkpoint.
- `em_envio`, `enviado` ou `incerto` sem evidência não autoriza retry cego.
- Mais de uma evidência remota para a mesma chave é incidente, não sucesso.
- Um recibo confirmado que deixa de ser observado também não autoriza reenvio.

## Máquina de estados

`preparado → em_envio → enviado → confirmado`

Qualquer tentativa sem evidência pode ir para `incerto`. A reconciliação pode adotar
o efeito e levar `preparado`, `em_envio`, `enviado` ou `incerto` a `confirmado`.
Não há transição automática de `incerto` para nova tentativa.

## Limite técnico

GitHub Contents e o destino externo não formam uma transação distribuída. APIs sem
chave de idempotência podem deixar um caso incerto quando a resposta se perde. Por isso
este corte prefere bloquear a repetir cegamente. Não promete exactly-once nem elimina
a necessidade de reconciliação independente.

## Testes

Os contratos usam armazenamento e destino sintéticos, sem rede. Cobrem reentrada,
payload divergente, queda antes/depois do efeito, perda de checkpoint, falha de leitura,
corrida na criação, SHA antigo, duplicidade remota e recibo que desaparece.

## Próximo corte

Criar o adaptador de comentários em modo shadow, com marcador determinístico e leitura
paginada de autoria/conteúdo. Só depois de novos contratos e revisão deve haver integração
ao respondedor, inicialmente sem efeitos reais.
