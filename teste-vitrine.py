#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste da vitrine: os canais parados trabalham, mas NÃO publicam.

A regra do dono é curta: publicar em rede social só com pedido explícito. Então este
teste não verifica se o post ficou bonito — verifica o que importa:

* nenhuma chamada de escrita (POST/PUT/DELETE) sai da vitrine;
* canal sem credencial não vira erro, vira "ausente";
* o rascunho é gravado na fila marcado "aguardando pedido do dono";
* o texto respeita o limite de cada canal.
"""
import json
import os
import sys

os.environ.pop("IG_TOKEN", None)
os.environ.pop("IG_USER_ID", None)
os.environ.pop("ITCH_API_KEYS", None)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("YT_API_KEY", None)

import comum as C
import vitrine as V

ok = True


def checar(nome, condicao):
    global ok
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome)
    ok = ok and condicao


# ---- 1. a vitrine nunca escreve na rede -------------------------------------------------
escritas = []


def http_espiao(metodo, url, cabeceras=None, corpo=None, timeout=30):
    if metodo.upper() != "GET":
        escritas.append((metodo, url))
        return False, "bloqueado pelo teste"
    return False, "sem rede no teste"


V._http = http_espiao
V.conferir()
checar("vitrine só faz GET (nenhuma escrita na rede)", not escritas)


# ---- 2. canal ausente não explode -------------------------------------------------------
V.C = C
estado = V.conferir()
checar("todos os canais são reportados", set(estado) == set(V.CANDEIROS))
checar("canal sem credencial vira 'ausente', não erro",
       all(e == "ausente" for e, _ in estado.values()))


# ---- 3. rascunho entra na fila marcado como rascunho ------------------------------------
gravado = {}


def escrever(caminho, conteudo, mensagem):
    gravado[caminho] = conteudo


def ler(caminho, padrao=""):
    if caminho == "MEMORIA/estado-casa.md":
        return "- port concluído com 22 robôs no ar\n- barreira em 106 verificações"
    return padrao


C.escrever_remoto = escrever
C.ler_remoto = ler
C.chamar_llm = lambda msgs, system=None, **k: ("Post do dia: 22 robôs no ar.", "fake", None)
C.log = lambda *a: None
V.CANDEIROS = {"telegram": lambda: ("vivo", "getMe ok")}

frase = V.montar()
fila = json.loads(gravado.get(V.ARQ, "{}"))
checar("vitrine grava a fila na memória", V.ARQ in gravado)
checar("rascunho existe para canal vivo", "telegram" in (fila.get("rascunhos") or {}))
checar("rascunho marcado aguardando o dono",
       (fila.get("rascunhos", {}).get("telegram", {}).get("estado", "")
        == "rascunho — aguardando pedido do dono"))
checar("a regra fica escrita no arquivo", "Nada é publicado" in gravado.get(V.ARQ, ""))
checar("frase final diz que nada foi publicado", "nada publicado" in frase)
C.chamar_llm = lambda msgs, system=None, **k: ("", None, "nenhum motor vivo")
texto, motivo = V._rascunho("telegram", [], False)
checar("canal sem motor vivo não inventa texto", texto == "" and "motor" in motivo)
checar("rascunho respeita o limite do canal",
       len(V._rascunho("bluesky", ["fato"], True)[0]) <= V.LIMITE["bluesky"])


# ---- 4. o robô existe e roda a barreira antes de tocar a rede ----------------------------
caminho_wf = os.path.join(".github", "workflows", "vitrine.yml")
fonte = open(caminho_wf, encoding="utf-8").read() if os.path.exists(caminho_wf) else ""
checar("workflow da vitrine existe", bool(fonte))
checar("workflow roda a barreira antes da vitrine",
       fonte.index("teste-casa.py") < fonte.index("vitrine.py"))
checar("workflow tem permissão só de leitura", "contents: read" in fonte)

print("\nteste-vitrine:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
