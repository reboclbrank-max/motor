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

Propostas brutas e erros ficam privados. A normalização aceita envelope JSON em Markdown e pós-texto sem autoridade, descarta somente ramos textuais conhecidos inativos e desfaz uma camada de escapes de arquivo inteiro somente se o original falhar no parser e o candidato passar. Não muda caminhos, comandos, política ou testes. Campos de efeito desconhecidos continuam rejeitados; AST não executa o código nem substitui CI.

Ao atualizar projeto explicitamente identificado, o controlador lê somente esse diretório privado, confere blobs/commit, limita o contexto e barra padrões conhecidos de credenciais antes de enviar ao modelo. Projeto inexistente não vira outro projeto silenciosamente. O snapshot de leitura é a base da alteração; mudança concorrente no projeto impede integração sem nova conferência.

## Evolução técnica de 2026-11-02 — missões e aceite observado (estado v2)

Novos projetos são decompostos em até5subtarefas verificáveis. Uma segunda
passagem de modelo recebe o objetivo ORIGINAL e a proposta como dados (sem histórico),
deriva casos de entrada/saída/exceção e vincula cada subtarefa a pelo menos um caso.
Esse contrato declarativo é validado e congelado por SHA256 ANTES do PR/CI.
Não contém código de teste executável, shell, repo, workflow ou autoridade.

Além dos unittests do projeto, um segundo container executa chamadas públicas JSON
ou CLI Python com stdin/argv e observa resultado/erro/argumentos após chamada,
ou stdout/exit code. O supervisor no container não importa o projeto: cada caso
roda em subprocesso. Expectativas ficam no controlador, fora do container, que
compara valores/tipos JSON, exceções, não-mutação solicitada ou stdout/exit code.
Um `unittest` verde ou um booleano `sucesso` do programa não substitui essas
observações. É obrigatório resultado CI do mesmo SHA de código E contrato.

Falha nos casos alimenta o reparo automático com observado versus esperado.
Implementação pode mudar; contrato e testes anteriores não. Nova CI antes de merge.
Subtarefas só recebem `aceite_observado` com os números dos casos, SHA e URL da CI.
Recibo contém roteiro/evidência; reentrada não regenera contrato nem executa novamente.
Estados antigos permanecem compatíveis e entregas históricas não são reabertas.
“Atualize/Atualizar projeto <id>” também passa a ser reconhecido.

Nenhuma ampliação de poderes/gastos/contas/credenciais/exclusões/envios externos.
Mesma política e teto de3chamadas à cadeia: geração+revisor normalmente usam2;
sobra1para reparar. Máximo2reparos continua subordinado a esse teto.
Contrato:1a12casos/20KB,1a5subtarefas; cada container mantém45s/256MB/sem rede,
não-root/read-only/sem segredos. Não existe fallback de código gerado no host.
Projetos não representáveis por esses executores/casos não ganham aprovação falsa.

Segunda passagem pode usar o MESMO provedor/modelo: não é juiz independente
infalível. Casos derivados por LLM podem omitir/reinterpretar requisitos; comparação
é independente do veredito do código, não prova universal da intenção do usuário.
Autonomia técnica ampliada não é agenda empresarial autoinventada, qualquer linguagem
ou autonomia irrestrita. Continua dependendo de Actions, modelos e quotas existentes.
