#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova as duas correções grandes do chat (31/10/2026), sem rede.

1. O ROBÔ NÃO RESPONDE A SI MESMO.
   A automação publica com o MESMO login do dono. A varredura só olhava o login, então tratava
   boletim e piloto automático como pergunta do dono — e respondia. Medido nos dados reais:
   "[varredura] respondidas 3 de 15" com a maioria das 15 sendo aviso da própria casa, e pares
   "Assistente Rebocl → Assistente Rebocl" separados por ~400 min nas conversas #60, #61, #62,
   #68. Custo: cota de LLM e ruído na conversa do dono.

2. A FILA DRENA SOZINHA.
   Teto de 3 respostas por rodada + cron que na prática roda poucas vezes por dia = espera de
   horas. Agora, terminada a rodada COM progresso e ainda com gente esperando, a varredura pede
   a próxima rodada. Trava: sem progresso, sem cadeia (nada de laço infinito com motor fora).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C
import varrer as V

CERTOS, FALHAS = [], []


def ok(nome, condicao, detalhe=""):
    CERTOS.append(nome) if condicao else FALHAS.append(nome)
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome
          + ("" if condicao else "  <" + str(detalhe)[:160] + ">"))


DONO = "reboclbrank-max"
DONO_U = {"login": DONO, "type": "User"}


def comentario(cid, corpo, usuario=None):
    return {"id": cid, "body": corpo, "user": usuario or DONO_U,
            "created_at": "2026-10-31T00:00:00Z"}


class FalsoGH:
    """Guarda o que a varredura lê e o que ela publica."""

    def __init__(self, issues, comentarios):
        self.issues = issues
        self.comentarios = comentarios
        self.posts = []
        self.dispatches = []

    def __call__(self, metodo, caminho, dados=None):
        if metodo == "GET" and "/issues?" in caminho:
            return self.issues
        if metodo == "GET" and "/comments" in caminho:
            numero = int(caminho.split("/issues/")[1].split("/")[0])
            return self.comentarios.get(numero, [])
        if metodo == "POST" and caminho.endswith("/comments"):
            self.posts.append((caminho, dados))
            return {"id": 999}
        if metodo == "POST" and "dispatches" in caminho:
            self.dispatches.append((caminho, dados))
            return {}
        return {}


def issue(numero, corpo="", usuario=None, quando="2026-10-31T00:00:00Z", comentarios=0):
    return {"number": numero, "body": corpo, "user": usuario or DONO_U,
            "updated_at": quando, "comments": comentarios}


def com_fakes(issues, comentarios, funcao):
    """Troca a rede por fakes; devolve (resultado_da_funcao, falso_gh)."""
    falso = FalsoGH(issues, comentarios)
    original = C.gh
    C.gh = falso
    try:
        return funcao(falso), falso
    finally:
        C.gh = original


print("== 1. marca da casa em toda fala do robô (comum.comentar)")
falso = FalsoGH([], {})
_orig = C.gh
C.gh = falso
try:
    C.comentar(7, "aviso qualquer do piloto automático", autor="piloto")
    C.comentar(7, "resposta com marca própria\n\n<!--resp:a7-->")
finally:
    C.gh = _orig
_corpo_aviso = falso.posts[0][1]["body"]
_corpo_resp = falso.posts[1][1]["body"]
ok("comentar acrescenta a marca invisível da casa", C.MARCA_DO_ROBO in _corpo_aviso, _corpo_aviso)
ok("a marca diz QUAL automação falou", "piloto" in _corpo_aviso)
ok("comentar não duplica marca já existente",
   _corpo_resp.count("<!--resp:") == 1 and C.MARCA_DO_ROBO not in _corpo_resp, _corpo_resp)

print("== 2. a varredura ignora fala da casa")
ok("resposta com marca é do robô", V._do_robo("texto\n\n<!--resp:c1-->"))
ok("aviso com marca nova é do robô", V._do_robo("texto\n\n" + C.MARCA_DO_ROBO + "boletim-->"))
ok("aviso antigo (sem marca) é reconhecido pelo cabeçalho",
   V._do_robo("🤖 **Piloto automático** — post de hoje (ceifalume) publicado"))
ok("assinatura do assistente também é do robô",
   V._do_robo(C.ASSINATURA + "\n\nresposta"))
ok("mensagem de gente NÃO é tratada como robô",
   not V._do_robo("queria saber quantos jogos a casa tem publicados"))

# Conversa em que a última fala é do robô (o caso medido) → não é pendência.
_issues = [issue(61, comentarios=5), issue(79, comentarios=1)]
_comentarios = {
    61: [comentario(501, "pergunta de verdade"),
         comentario(502, "🤖 **Piloto automático** — post de hoje publicado\n\n" + C.MARCA_DO_ROBO + "piloto-->")],
    79: [comentario(503, "pergunta nova do dono, sem resposta")],
}
diagnostico = {}
_lista, falso = com_fakes(_issues, _comentarios, lambda f: V.pendentes(diagnostico=diagnostico))
ok("boletim/piloto no fim da conversa NÃO vira pendência",
   [i["number"] for i, _c in _lista] == [79], [i["number"] for i, _c in _lista])
ok("o diagnóstico diz quantas foram ignoradas por serem da casa",
   diagnostico.get("ignoradas_do_robo") == 1, diagnostico)
ok("a leitura das conversas pede 100 por página (não 30)",
   True if V.POR_PAGINA == 100 else False, V.POR_PAGINA)
ok("a janela é de uma semana, não de 72 h", V.JANELA_HORAS >= 168, V.JANELA_HORAS)

# O dono falando DEPOIS do robô continua sendo pergunta pendente.
_comentarios[61] = [comentario(502, "🤖 **Assistente Rebocl**\n\nresposta antiga"),
                    comentario(504, "e agora, quantos downloads?")]
_lista2, _ = com_fakes([issue(61, comentarios=2)], _comentarios, lambda f: V.pendentes())
ok("mensagem do dono DEPOIS do robô continua pendente",
   [i["number"] for i, _c in _lista2] == [61], [i["number"] for i, _c in _lista2])

print("== 3. a fila drena sozinha (cadeia)")
# A varredura desiste sem token; aqui o token é de mentira e a rede é falsa.
C.GH_TOKEN = "token-de-teste"
_pedidos = []
_processados = []


def _processa(i, c):
    _processados.append(i["number"])
    return True


def _disparo(motivo="fila"):
    _pedidos.append(motivo)
    return True


# 5 pendentes, teto 3, todas respondidas → cadeia pedida
_issues = [issue(n, comentarios=1) for n in (90, 91, 92, 93, 94)]
_comentarios = {n: [comentario(700 + n, f"pergunta {n}")] for n in (90, 91, 92, 93, 94)}
_res, falso = com_fakes(_issues, _comentarios,
                        lambda f: V.main(processar_um=_processa, disparar=_disparo))
ok("com 5 na fila e teto 3, responde exatamente 3", len(_processados) == 3, _processados)
ok("com sobra e progresso, pede outra rodada", _pedidos == ["faltam 2"], _pedidos)

# nada pendente → não pede nada
_pedidos.clear()
_res, _ = com_fakes([], {}, lambda f: V.main(processar_um=lambda i, c: True, disparar=_disparo))
ok("sem pendência, não pede rodada", _pedidos == [], _pedidos)

# progresso zero (motores fora) → NÃO pede outra rodada (evita laço infinito)
_pedidos.clear()
_issues = [issue(n, comentarios=1) for n in (95, 96)]
_comentarios = {n: [comentario(710 + n, f"pergunta {n}")] for n in (95, 96)}
_res, _ = com_fakes(_issues, _comentarios,
                    lambda f: V.main(processar_um=lambda i, c: False, disparar=_disparo))
ok("sem nenhuma resposta, a cadeia NÃO é pedida", _pedidos == [], _pedidos)

# uma resposta só e nada sobrando → não pede
_pedidos.clear()
_issues = [issue(97, comentarios=1)]
_comentarios = {97: [comentario(717, "pergunta única")]}
_res, _ = com_fakes(_issues, _comentarios,
                    lambda f: V.main(processar_um=lambda i, c: True, disparar=_disparo))
ok("fila que esvaziou na rodada não pede outra", _pedidos == [], _pedidos)

print("== 4. a cadeia vai para o repositório do CÓDIGO (não para o das conversas)")
_destinos = []
_orig_gh = C.gh


def _gh_espiao(metodo, caminho, dados=None):
    if metodo == "POST" and "dispatches" in caminho:
        _destinos.append(caminho)
        return {}
    return {}


C.gh = _gh_espiao
try:
    V.acordar_de_novo("teste")
finally:
    C.gh = _orig_gh
ok("o dispatch vai para o repositório do robô",
   _destinos and C.REPO_ROBO in _destinos[0] and C.REPO not in _destinos[0], _destinos)
ok("o repositório do código é público e separado das conversas", C.REPO_ROBO != C.REPO,
   (C.REPO_ROBO, C.REPO))

print()
if FALHAS:
    print("%d de %d verificações da varredura FALHARAM" % (len(FALHAS), len(CERTOS) + len(FALHAS)))
    sys.exit(1)
print("%d/%d verificações da varredura passaram" % (len(CERTOS), len(CERTOS)))
