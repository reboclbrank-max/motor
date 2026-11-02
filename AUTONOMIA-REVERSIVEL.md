# Autonomia reversível autorizada pelo dono

O dono escolheu expressamente: executar tarefas internas e mudanças reversíveis; planejar, pesquisar, escrever/testar código, abrir PR e integrar após CI/conferência; aprovação para gastos, contas, credenciais, exclusões e comunicação/publicação externa.

## Executores disponíveis
- Leituras operacionais conservadoras anteriores: preservadas.
- Objetivos naturais de pesquisa: fontes realmente coletadas, síntese identificada como de modelo, relatório privado e recibo.
- Documentos: rascunhos privados, não fatos presumidos nem publicação externa.
- Projetos Python internos: código/testes em `PROJETOS/<id>/` do repositório **privado** de conversas. Nenhum arquivo existente é apagado. Atualização de projeto existente exige `projeto <32hex>` no pedido atual; testes anteriores são protegidos.

Exemplo: “Crie um projeto Python interno com uma função para resumir uma fila de tarefas e testes unittest. Sem publicar, excluir ou gastar.” Não exige tag técnica. O modelo propõe JSON; não escolhe shell, repositório, caminho livre, workflow, credencial ou permissão. A origem/autoria e o hash da mensagem são reconferidos via API antes de executar.

## Ciclo de código
1. Política privada ativa e dono conferidos; estado/limite de inferência persistido antes da chamada.
2. Proposta validada (até12arquivos/100KB, nomes simples, implementação e testes obrigatórios).
3. Branch/PR privados, restritos ao projeto; commits por árvore com pai conhecido, sem force.
4. Dispatch fixo de `projeto-autonomo.yml`, manual e restrito ao dono. Não há cron novo. Não se executa CI no repositório privado: os hashes dos workflows privados são conferidos contra a política para impedir ativação desconhecida de gatilhos pagos.
5. Worker público lê apenas os arquivos do projeto para o container. Código/saída permanecem privados. Python oficial fixado por digest; Docker sem rede, sem capabilities, não root, filesystem readonly, sem Docker socket/segredos/memória montados, CPU/memória/PIDs/saída/tempo limitados. Sem Docker: falha fechada, nunca fallback de código gerado no host. Container é removido inclusive após timeout.
6. Resultado CI privado vinculado ao SHA; status no commit; callback fixo para o Chat. A espera é progresso persistido, não sucesso de entrega nem falha artificial do job.
7. Retomada exige job CI realmente concluído com sucesso, workflow/ator corretos, SHA, diff restrito, status/checks aprovados e proteção de branch satisfeita. Edições concorrentes no projeto impedem merge de combinação não testada. Merge não força regras; conteúdo de main é reconferido depois.
8. Relatório/recibo privado. Reentrada entregue lê o mesmo recibo, sem novo modelo/PR/dispatch/merge.

CI que falha pode produzir até2reparos de implementação, sem trocar testes anteriores; cada SHA requer nova CI. Limite total de3chamadas à cadeia de modelos por objetivo (não é limite de tentativas internas dos provedores). Falhas operacionais pré-CI têm até3retomadas; dispatch incerto não é repetido. Depois do limite ou de conflito/risco, bloqueio explícito e revisão, nunca relato inventado de sucesso.

## Política e controle
Política: `POLITICAS/chat-autonomia-reversivel.json`, fora da área que o modelo pode alterar. O modelo não edita essa política por argumentos ou texto de ferramenta. Comandos exatos do dono: `pausar autonomia` e `retomar autonomia`; só mudam o booleano de ativação, não ampliam poderes. Estado e recibos em `MEMORIA/autonomia-reversivel/<origem>/` e `MEMORIA/trabalhos/`.

Alterar executores de produção ou as próprias travas pode expor credenciais; **não** é auto-integração de código isolado. Sites, contas, marketing, email, gastos, credenciais, exclusões e objetivos sem executor seguro não são liberados por pedido genérico. Essas situações exigem aprovação/implementação específica. Não há execução arbitrária de Python no processo que tem PAT.

A política não cria nova conta, cron, segredo, serviço pago ou infraestrutura externa. O CI manual é necessário para separar teste de código e integração. Segredos existentes são usados apenas pelo controlador. Rotacionar PAT ainda é ação do titular; escopo mínimo precisa cobrir Contents/Issues/Pull requests/statuses do privado e Actions do worker público, não administração de organização/empresa.

## O que não se promete
Não é autonomia ilimitada ou garantia semântica universal. CI e testes podem ser insuficientes; modelo pode errar e fontes podem falhar. Recibo de entrega significa resultado tecnicamente observado para revisão. Container é isolamento operacional, não prova de invulnerabilidade do kernel. Projetos internos não são silenciosamente implantados como Chat de produção. Objetivos históricos/finais não são reabertos. Logs novos não imprimem o texto privado do pedido, código ou saída do container.
