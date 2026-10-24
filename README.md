# motor — o trabalhador do Assistente Rebocl

> **Este repositório é público de propósito.** Repositório público tem minutos de
> GitHub Actions ilimitados e gratuitos; repositório privado tem 2.000 por mês e a casa
> estourou. Aqui roda **só código**: nenhuma memória, nenhuma conversa, nenhuma chave.

## Como funciona

```
motor (público, este)                        agente (privado)
├── comum.py, responder.py, casa.py          ├── MEMORIA/  ← diário, conversas, banco
├── varrer.py     ← procura o que respondeu  ├── provas/
├── sincronizar.py ← baixa e devolve memória └── issues   ← as conversas do Chat
└── .github/workflows/chat.yml ── PAT ────►
```

1. O job baixa `MEMORIA/` do repositório privado (`sincronizar.py baixar`).
2. `varrer.py` lista as conversas pendentes do privado e responde as que o dono escreveu.
3. No fim, devolve para o privado só o que mudou (`sincronizar.py subir`).

`.gitignore` bloqueia `MEMORIA/`: mesmo que algo dê errado no meio, ela não é commitada
aqui.

## Cinco travas

1. `permissions: contents: read` — o job não escreve neste repositório.
2. Nenhum gatilho de `pull_request`/`pull_request_target`: código de terceiro nunca roda
   com acesso a secret.
3. Dispatch só vale quando quem disparou é o dono (`github.actor`).
4. A varredura só considera mensagem do dono e nunca responde duas vezes (marca invisível).
5. Todo segredo vive em Actions secret; nada de valor em arquivo ou log.

Configuração de apoio já aplicada no repositório: issues/wiki/projects desativados,
`GITHUB_TOKEN` padrão somente-leitura e PR de fork exigindo aprovação.

## Segredos necessários

| segredo | para quê |
|---|---|
| `PAT_MEMORIA` | token com acesso ao repositório privado (issues + contents) |
| `REPO_MEMORIA` | `reboclbrank-max/agente` |
| chaves de motor (Gemini, Groq, OpenRouter, HuggingFace…) | o cérebro que responde |
| `ITCH_API_KEYS`, `YT_API_KEY`, `IG_TOKEN`, `IG_USER_ID` | leitura real da casa |

## Barreira

`teste-casa.py` roda antes de qualquer resposta: 38 verificações offline que cercam número
inventado, vazamento de credencial e publicação sem pedido explícito do dono.
