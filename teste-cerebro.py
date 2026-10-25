#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline do pacote cérebro (v3.14): rota por força, extras dinâmicos,
pergunta complexa, varredura de motores e relatório curto."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa
import relatorio as R  # noqa
import varredura as V  # noqa

store = {"MEMORIA/motores-extras.json": json.dumps(["motor-extra-x", "motor-morto-y"])}
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)
C.escrever_remoto = lambda caminho, conteudo, mensagem="": store.update({caminho: conteudo}) or True

ok = True


def checar(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


# ---- rota por força: código tenta codestral primeiro ----
ordem = []
C._chamar_llm7_modelo = lambda p, mensagens, system, modelo: ordem.append(modelo) or "resposta"
p_llm7 = {"modelos": ["GLM-5.3-Flash", "gemma4:31b", "codestral-latest"]}
C._chamar_llm7(p_llm7, [{"role": "user", "content": "meu código python deu erro de sintaxe"}], "")
checar("pergunta de código → codestral primeiro", ordem and ordem[0] == "codestral-latest")
ordem.clear()
C._chamar_llm7(p_llm7, [{"role": "user", "content": "oi, tudo bem?"}], "")
checar("pergunta normal → ordem padrão", ordem and ordem[0] == "GLM-5.3-Flash")

# ---- extras dinâmicos entram na fila ----
provs = C.montar_provedores()
extras = [p for p in provs if str(p.get("id", "")).startswith("llm7-ex")]
checar("motores extras da varredura entram na fila", len(extras) == 2
       and extras[0]["modelos"] == ["motor-extra-x"])
# O teste antigo exigia chave == "unused" (llm7 sem chave). Isso deixou de ser verdade em
# 25/10/2026, quando LLM7_API_KEY passou a existir no repositório público. O que importa não
# é o valor literal: é que os extras REUSEM a chave do llm7, sem exigir credencial nova.
checar("extras não exigem credencial nova (reusam a do llm7)",
       all(p["chave"] in ("unused", C.CHAVE_LLM7) for p in extras))

# ---- pergunta complexa ----
checar("pergunta complexa detectada", C._pergunta_complexa("Compare a estratégia A e B para meu jogo e planeje o lançamento"))
checar("pergunta simples não é complexa", not C._pergunta_complexa("oi, tudo bem?"))
checar("pergunta longa é complexa", C._pergunta_complexa("x" * 220))

# ---- varredura: cata novos, remove mortos, escreve extras ----
C.UA_BOT = getattr(C, "UA_BOT", "teste")
V._catalogo = lambda: ["GLM-5.3-Flash", "motor-extra-x", "motor-morto-y", "novo-musculo-z", "velho-w"]
V._modelo_vivo = lambda modelo: modelo not in ("motor-morto-y", "velho-w")
avisos = []
C.notificar = lambda titulo, texto, **kw: avisos.append(titulo) or True
r = V.varrer()
checar("varredura achou músculo novo", "novo-musculo-z" in r)
extras_final = json.loads(store[V.ARQ_EXTRAS])
checar("extras finais: morto saiu, novo entrou", "motor-morto-y" not in extras_final
       and "novo-musculo-z" in extras_final and len(extras_final) <= V.MAX_EXTRAS)
checar("aviso de motor novo disparado", bool(avisos))

# ---- relatório curto (bom-dia) ----
C.ler_remoto = lambda caminho, padrao="": {
    "MEMORIA/manual.md": "## Saber destilado dos estudos\n- lição de marketing prática",
    C.ARQ_LICOES: "- lição do dono\n- (auto) revisar saves",
}.get(caminho, padrao)
C.ler_diagnostico = lambda: {"provedores": {"llm7": {"ok": True, "ms_medio": 900}}}
enviados = []
C.ferramenta_email = lambda argumento: enviados.append(argumento) or "📧 enviado"
R.enviar_relatorio(curto=True)
checar("bom-dia curto saiu por e-mail", enviados and "Bom dia!" in enviados[0]
       and "lição de marketing" in enviados[0] and "Motores vivos agora: 1" in enviados[0])

print("\nTESTE CEREBRO:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
