# Funcionário digital: registro de trabalho e falhas honestas

## Escopo e estado

O dono pediu implementar um funcionário, deixando marketing para depois. Isto é
engenharia de assistente digital, não criação de humano, vida ou consciência.
Mantidos GitHub e custo R$0/sem cartão. Nenhum serviço novo, cron novo, conta,
publicação de marketing ou dispatch manual neste corte.

## Falha não é entrega

- Avisos de indisponibilidade novos usam estado pendente e marcador próprio, não
  marca de resposta final. O varredor continua considerando o pedido pendente.
- Três prefixos de avisos legados conhecidos são reconhecidos como não finais,
  mesmo contendo a antiga marca de resposta.
- Respondedor, dedupe e varredor compartilham essa classificação. Aviso pendente
  existente é atualizado, quando possível, em vez de criar avisos repetidos.
- Só se anuncia entrada na fila se a gravação retornou sucesso ou o item já foi
  localizado nela. Leitura da fila falhando/corrompida interrompe, não devolve
  lista vazia a ser sobrescrita; somente 404 observado equivale a arquivo ausente.
- Se o dreno respondeu a mensagem atual, o fluxo principal não a responde de novo.
- Auditoria somente GET encontrou uma mensagem histórica reaberta por corrigir a
  classificação; adicionada à revisão privada antes da integração, sem executá-la
  e sem declará-la concluída. A revisão histórica passa de 17 para 18 mensagens.

## Registro persistente de trabalhos

Nova ferramenta TRABALHO, integrada ao parser, roteador e instruções do modelo.
Também disponível pelo comando `trabalho: JSON` no chat privado. Operações:

- criar: objetivo e lista de etapas; retorna ID aleatório e estado planejado;
- status: recupera o registro pelo ID;
- bloquear: registra motivo; retomar preserva etapas e remove bloqueio;
- registrar_etapa: exige arquivo de evidência existente em MEMORIA/ e guarda SHA;
- entregar: exige evidências de todas as etapas, reconfere seus SHAs e guarda
  resultado; estado final é **entregue_para_revisao**, nunca aprovado/concluído.

Exemplo de criação:

```json
{"acao":"criar","objetivo":"Preparar um relatório solicitado pelo dono","etapas":["Reunir fontes","Redigir relatório"]}
```

Depois usar o ID retornado, não inventar um. Exemplo de registro de etapa:

```json
{"acao":"registrar_etapa","id":"ID_RETORNADO","etapa":1,"arquivo":"MEMORIA/entregas/fontes.md"}
```

Arquivos privados em MEMORIA/trabalhos/ são gravados com SHA otimista: conflito
recusa sobrescrita. Espelho local atualizado depois de cada PUT confirmado para
não perder o trabalho na sincronização seguinte. Registro permite inspecionar e
retomar o plano, mas NÃO inicia executor autônomo de etapas nem fornece permissão
nova para ações externas. Contexto/tempo/quotas do modelo continuam finitos.

## Testes e o que eles não provam

27 arquivos de testes locais passaram. Dois novos arquivos somam 20 testes para
indisponibilidade/reentrada, corrupção da fila, plano, etapas, bloqueio, entrega,
conflito e evidências. Teste de evidência verifica existência e SHA do arquivo,
NÃO a qualidade ou a verdade de seu conteúdo, nem sucesso de campanha de marketing.
Execução local com serviços simulados não equivale a execução Actions real.

Persistem: concorrência da fila JSON, retomada dentro de ferramenta, acionamento
autônomo geral de planos, validação de qualidade e 18 históricos em revisão.
Não declarar funcionário autônomo completo, humano, consciente ou ilimitado.
