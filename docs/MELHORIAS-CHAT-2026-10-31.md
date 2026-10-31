# Melhorias grandes do Chat — 31/10/2026

O dono pediu *"melhorias muito grandes para o chat"*. Antes de mexer em qualquer coisa, medi o
chat funcionando de ponta a ponta — criei uma conversa, acordei o motor e cronometrei. O que
apareceu não estava na interface: estava no **motor da resposta**.

## Como o chat estava, medido

| medida | valor |
| --- | --- |
| caminho completo (dispatch → resposta na conversa) | **~2 minutos** ✅ |
| fila no momento da medição | "respondidas **3 de 15**" |
| dessas 15 "pendentes" | **26 conversas eram a própria casa falando** (boletim, piloto automático, rotinas) |
| ritmo real do cron `*/10` | ~5 execuções por dia, não 144 (o GitHub espaça cron de repositório público) |
| despachos do sentinela e do comando `caçar` | **nunca funcionaram** (mirados no repositório errado) |

## O que foi corrigido (commits `97439c4` e `dd72e86`, no repositório `motor`)

### 1. O robô parou de responder a si mesmo

A automação publica com o **mesmo login do dono**. A varredura só olhava o login, então tratava
"🤖 **Piloto automático** — post de hoje publicado" como pergunta do dono **e respondia**. Nas
conversas #60, #61, #62 e #68 há pares *Assistente → Assistente* separados por ~400 minutos.

Correção em dois níveis:

- `comum.comentar()` agora põe **marca invisível** (`<!--robo:origem-->`) em toda fala da casa —
  um lugar só, vale para todos os módulos, sem tocar em cada um;
- a varredura reconhece a marca **e** o cabeçalho antigo (`🤖`) para não apagar histórico.

Prova em produção (run `41155621546`): `[varredura] 26 conversa(s) só com fala da casa — não é
pergunta` / `5 pendente(s) do dono`.

### 2. A fila drena sozinha

Teto de 3 respostas por rodada + cron esparso = espera de horas. Agora, terminada a rodada **com
progresso** e ainda com gente esperando, a varredura pede a próxima rodada.

Prova em produção: run `41155621546` → `respondidas 3 de 5` + `cadeia: outra rodada pedida
(faltam 2)`; o encadeado `41156001630` → `respondidas 2 de 2` e **parou** (sem laço). Os 5
atendimentos levaram **8,5 minutos**; antes seria o próximo cron, horas depois.

Trava: **sem progresso, sem cadeia**. Motor fora do ar não vira laço infinito.

### 3. Despachos que nunca chegavam

`sentinela` e `!cacar` disparavam em `C.REPO` — o repositório das **conversas** — onde
`chat.yml` e `caca-motores.yml` **não existem** (404), e o do sentinela ainda mandava `inputs`
que o workflow não declara (422). Ou seja: o "reprocessamento automático" e o comando de caça
estavam mortos desde sempre. Agora os dois miram o repositório do **código** e mandam só `{ref}`.

### 4. Mensagem antiga não desaparece mais em silêncio

A janela era 72 h e 30 conversas por leitura: pergunta de 4 dias atrás nunca era respondida e
ninguém ficava sabendo. Agora 7 dias e 100 conversas por página.

**Testes:** `teste-varredura.py` novo, **24 verificações offline** (marca da casa, falso-positivo
com mensagem de gente, cadeia com e sem progresso, destino dos despachos). Suíte do motor segue
verde: `teste-casa` 156/156, `teste-chat`, `teste-cerebro`, `teste-fila`, `teste-v37`,
`teste-responder-emergencia` — todas OK. O teste entrou na barreira do `testes.yml`.

## O que eu proporia como próximo degrau (com o tamanho de cada um)

| # | melhoria | por que importa | tamanho |
| --- | --- | --- | --- |
| 1 | **Cérebro fora do repositório bloqueado** | os repositórios privados (`agente`, `base`) estão **100% vermelhos**: 40 de 40 runs com `The job was not started because recent account payments have failed or your spending limit needs to be increased`. Isso derruba memória, sentinela e rotinas — o chat responde, mas não lembra nem age. Migrar essas rotinas para o repositório público (que tem minutos ilimitados), mantendo os dados no privado via token | médio |
| 2 | **Resposta que responde à pergunta** | testei com "quantos jogos a casa tem publicados e qual o próximo passo do roadmap" e recebi um relatório de retorno por tipo de post — bonito e fora da pergunta | médio |
| 3 | **Fila visível na tela** | hoje o dono manda e não sabe se entrou na fila; um selo "na fila há 40 s · resposta em ~2 min" acaba com a dúvida | pequeno |
| 4 | **Uma conversa por assunto, não por mensagem** | 73 conversas, muitas de aviso automático; separar "conversa" de "aviso" na lista deixa a lista utilizável | pequeno |
| 5 | **Resposta em pedaços (streaming)** | a espera de 2 min parece 10 sem sinal de vida; publicar "pensando…" e ir completando reduz a sensação de travado | médio |

Nada aqui é opinião de marketing: cada linha saiu de um número medido nesta rodada.

## As 5 melhorias — fechadas, com a prova de cada uma (rodada 127, ainda 31/10/2026)

| # | melhoria | como foi fechada | prova medida |
| --- | --- | --- | --- |
| 1 | **Cérebro fora do repositório bloqueado** | 27 workflows **com `cron`** do repositório privado `agente` tiveram o bloco `schedule:` desativado (motivo medido: 40 de 40 runs vermelhos por falha de pagamento — *"recent account payments have failed"*); os 12 sem cron ficaram intactos. `bom-dia` — o único com cron que **não** existia no `motor` — foi portado para `motor-work/.github/workflows/bom-dia.yml` | `agente`: **0 agendado** depois da mudança. `bom-dia` no `motor`: run `41157237293` = `success`, log com `📧 E-mail enviado` e `📦 Pacote Instagram enviado` |
| 2 | **Resposta que responde à pergunta** | `relevancia.py` (cobertura por termos, sem modelo) + **todo atalho** passa por `atalho_serve()` — `casa.pede_decisao`, `dados.resposta_direta`, `cache_exato` — e o motor tem uma segunda tentativa reforçada. Commits `350ec38`, `46d6ae1`, `152b768` | Log real do run `41157729268`: `relevância: atalho 'análise da casa' cobriu 40% da pergunta — deixei o motor responder` → `relevância: resposta cobriu 100%`. A mesma pergunta que antes voltava com o relatório de Bluesky agora volta com **"A casa tem 2 jogos publicados: Ceifalume 0.1 e Prancheta 0.1"** + roadmap |
| 3 | **Fila visível na tela** | `pensando()` ganhou **relógio andando** e as faixas medidas (`FILA_MEDIDA`): típico ~2 min com o motor acordado; sem acordar, mediana 198,5 min e p90 379 min | PR **#55** mergeado (`chat` `main` = `3c00761`), `testes` = success, barreira **112/112**; página publicada servindo `⏱ na fila há …` |
| 4 | **Uma conversa por assunto (aviso ≠ conversa)** | cartão com `label: aviso` ganha etiqueta 📣, estilo próprio e vai **para o fim** da lista; a faixa conta `N conversas · M avisos da casa` | medição: **30 de 31 cartões** eram aviso da casa. PR **#55**, teste novo `fila-visivel-e-avisos.js` (13/13) |
| 5 | **Resposta em pedaços (sinal de vida)** | o aviso nasce em segundos e é **reescrito no mesmo comentário** no fim; agora também há **batida a cada 45 s** (`BatidaDoPensando`) dizendo há quanto tempo e em que etapa está — o motor devolve a resposta inteira de uma vez, então token a token não existe: o que dá para publicar é o tempo e a etapa | prova HTTP real: comentário criado `02:58:14`, editado `02:58:21` com `🧠 ainda pensando… há 6 s · teste de sinal de vida` (mesmo id, nenhum comentário novo). `teste-pensando.py` **21/21** |

**Sinal de vida do aviso em produção:** conversa #76 (run do `chat` disparado por `repository_dispatch`) → **1 comentário só**: nasceu "🧠 pensando…" e foi reescrito na resposta em 23 s, sem duplicata.

### Tropeço honesto desta rodada

O merge #55 levou junto um **link simbólico `node_modules`** criado por engano no ambiente local. O `tar --dereference` do Pages falhou (`tar: ./node_modules: File removed before we read it`) e **a publicação do site parou** (run `41160786207` = `failure`). Corrigido no PR **#56**: link removido, `.gitignore` com `node_modules/` **e** `node_modules`, e verificação permanente no teste (falha se um link desses voltar). Pages voltou a publicar (`41161764584` = `success`).

**Barreira do motor:** `teste-relevancia` 36/36 · `teste-pensando` 21/21 · `teste-varredura` 24/24 · `teste-casa` 156/156 · `teste-chat`, `teste-fila`, `teste-cerebro`, `teste-v37`, `teste-responder-emergencia` OK — todas na barreira `testes.yml`.
