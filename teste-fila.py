#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa a fila de respostas pendentes (v3.13): adicionar, dedupe, drenar, limites."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C
import responder as R

store = {}
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)


def fake_escrever(caminho, conteudo, mensagem=""):
    store[caminho] = conteudo
    return True


C.escrever_remoto = fake_escrever

ok = True


def check(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


# ---- adicionar + dedupe ----
check("adiciona pendência", C.fila_respostas_adicionar(10, "explique quantum", "c101") is True)
check("dedupe por marca", C.fila_respostas_adicionar(10, "explique quantum de novo", "c101") is False)
C.fila_respostas_adicionar(11, "outra pergunta", "c102")
itens = C.fila_respostas_carregar()
check("2 itens na fila", len(itens) == 2)

# ---- drenar: motores ok → responde e esvazia (máx 2) ----
publicados = []


def fake_responder(numero, texto, marca, extra=""):
    publicados.append((numero, marca))


R.responder = fake_responder
R.ja_respondida = lambda numero, marca: False
C.responder_com_ferramentas = lambda historico, numero=None, preferir=None: ("resposta ok", "Motor X", [], None)
C.historico_da_conversa = lambda numero, pular_id=None: []
C.registrar_conversa = lambda *a, **k: True
R.drenar_fila_respostas()
check("drenou 2 por execução (e esvaziou)", len(publicados) == 2 and not C.fila_respostas_carregar())
check("respondeu com as marcas originais", {m for _n, m in publicados} == {"c101", "c102"})

# ---- drenar: motores fora → mantém a fila ----
publicados.clear()
C.fila_respostas_salvar([])
C.fila_respostas_adicionar(20, "pergunta pendente", "c200")
C.responder_com_ferramentas = lambda historico, numero=None, preferir=None: (None, None, [], "todos falharam")
R.drenar_fila_respostas()
check("motores fora: nada publicado", not publicados)
check("motores fora: fila mantida", len(C.fila_respostas_carregar()) == 1)

# ---- drenar: pendência já respondida → descarta sem publicar ----
publicados.clear()
R.ja_respondida = lambda numero, marca: True
R.drenar_fila_respostas()
check("já respondida: descarta sem publicar", not publicados and not C.fila_respostas_carregar())

# ---- limite: 2 por execução ----
R.ja_respondida = lambda numero, marca: False
C.responder_com_ferramentas = lambda historico, numero=None, preferir=None: ("ok", "M", [], None)
for i in range(5):
    C.fila_respostas_adicionar(30 + i, f"pergunta {i}", f"c30{i}")
publicados.clear()
R.drenar_fila_respostas()
check("máx 2 por execução", len(publicados) == 2)
check("restaram 3 na fila", len(C.fila_respostas_carregar()) == 3)

# ---- corte MAX_FILA_RESPOSTAS ----
for i in range(40):
    C.fila_respostas_adicionar(100 + i, f"q{i}", f"m{i}")
check("corte em MAX_FILA_RESPOSTAS", len(C.fila_respostas_carregar()) <= C.MAX_FILA_RESPOSTAS)

print("\nTESTE FILA DE RESPOSTAS:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
