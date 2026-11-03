# Componentes privados autoaperfeiçoáveis

Autorização explícita: autonomia técnica segura, R$0 e dados privados. Dono autorizou
publicar somente a infraestrutura técnica revisada no Motor público. Propostas,
código evoluído, PRs, diagnósticos e artefatos permanecem no repositório privado.
Não é autorização de autoedição de executores com PAT, permissões ou proteções.

Primeiro alvo: apresentação/diagnóstico de execuções do Chat. Baseline extraído do
join ACOES de operacao_leitura.py no commit b519fbc0. Requisitos de escape Markdown,
campos ausentes/Unicode, tipos e não mutação foram especificados nesta manutenção.
Não alegar descoberta espontânea de defeito nem fabricação deliberada de bug.

Ciclo no relógio existente: auditoria isolada -> CI real -> falha observada -> modelo
LOCAL propõe correção -> contrato/testes anteriores protegidos -> CI no SHA exato
-> merge privado automático -> ativação CAS -> canário isolado -> uso no Chat.
Execução saudável do ativo não cria PR redundante.1rodada/diaUTC,3cadeias de modelo
por rodada, até2reparos; sem reset automático depois de bloqueio. Sem modelo remoto,
conta, credencial, cron, cobrança ou novo serviço. O modelo local opcional existente
pode ficar indisponível: backoff/teto, não promessa de conclusão qualquer tarefa.

O modelo só propõe código em PROJETOS/<alvo>/formatador.py; teste API e contrato de
11casos são controlados fora dele. CI/PR/transporte reutilizam o controlador existente.
A ativação aceita exatamente2arquivos no componente permitido. Novos escopos exigem
revisão, não são escolhidos pelo código gerado. Não usa conversa do robô como ordem
humana. Política privada própria com pin do controlador e hash do contrato.

Código gerado NUNCA importado/executado no host com credenciais. Docker sem rede,
segredos, socket, capabilities, escrita no projeto ou root; limites de tempo, CPU,
memória, pids e saída. Runtime recebe só snapshot de metadados de execução. Comparação
fora do container exige fatos/escape exatos, sem mutação. Não transforma texto do
modelo em comando ou autorização. Saída divergente falha fechada: restaura anterior
por CAS e usa referência confiável. Canário falho desfaz ponteiro; não apaga versão.

Estado/manifesto em MEMORIA/chat-componentes; política em POLITICAS/chat-componentes.json.
Pausa geral também pausa este fluxo. Política revogada/pin alterado é conferida antes
de cada escrita. Private workflows preservados e branch protections respeitadas.
Sem FORCE, sem apagar histórico, sem repetir dispatch incerto, sem orçamento infinito.
365rodadas preservadas antes de revisão administrativa. Ativação de worker novo
exige revisão dos pins privados; este componente não pode mudá-los sozinho.

É um ciclo real de autoaperfeiçoamento DENTRO de uma fronteira estreita, não autonomia
universal. Não promete qualquer linguagem, correção semântica universal ou remoção
das aprovações de gastos/credenciais/permissões/exclusões/publicações externas.

## Ampliação posterior explicitamente aprovada
Dono escolheu até8chamadas locais totais, preservando as3consumidas e sem resetar
origem/contrato/histórico. Política exige aprovação literal adicional; padrão de
projetos comuns continua3. ContextVar temporária somente no fluxo de componente;
restaurada depois. Modelo local7B, mesma família/runner, sem prompt remoto ou nova
credencial. Código inválido é journalado antes de AST; isso corrige a perda de
diagnóstico da3ªtentativa, não a recria nem finge que foi preservada.2reparos de
código válidos continuam o teto anterior, além da limitação total de chamadas.

## Recuperação coerente com as8tentativas autorizadas
O teto total8 inclui propostas testadas, não só rascunhos. Dentro desse contexto
aprovado: no máximo7reparos, sempre sujeitos às8chamadas totais e sem zerar nenhum
contador anterior; projetos comuns permanecem3chamadas/2reparos. ContextVars restauradas.
Falha REAL daCI é encaminhada ao modelo local, com contexto4096 para fonte+diagnóstico;
comportamento normal do motor local permanece2048. Não fornece algoritmo corretivo,
não altera testes/expectativas para fazer passar. Mantém todas as negativas.
