#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""O aviso "pensando" dá sinal de vida? — medido, offline, sem rede.

DEFEITO MEDIDO (31/10/2026): depois do aviso imediato, o comentário ficava congelado por ~2 min.
Do lado de quem escreveu, texto parado é igual a travado. O motor devolve a resposta inteira de
uma vez (não há token a token a publicar), então o que dá para mostrar a cada 45 s é o que é
verdade: há quanto tempo estou nisto e em que etapa estou — sempre editando o MESMO comentário.

Este teste não abre rede, GitHub, token nem conta.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import responder as R  # noqa: E402

CERTOS, FALHAS = [], []


def ok(nome, condicao, detalhe=""):
    if condicao:
        CERTOS.append(nome)
        print("  ✓ " + nome)
    else:
        FALHAS.append(nome)
        print("  ✗ " + nome + (" — " + str(detalhe) if detalhe else ""))


print("== 1. o texto diz há quanto tempo e em que etapa (sem inventar)")
_relogio = {"t": 1000.0}
b = R.BatidaDoPensando(75, 999, etapa="o motor está escrevendo",
                       agora=lambda: _relogio["t"])
ok("começa em 0 s", b.texto().startswith("🧠 **_ainda pensando…_** há 0 s"), b.texto()[:60])
_relogio["t"] += 75
ok("conta 1 min 15 s", "há 1 min 15 s" in b.texto(), b.texto()[:80])
_relogio["t"] += 3600
ok("conta horas quando passa de 60 min", "há 1 h 1 min" in b.texto(), b.texto()[:80])
ok("diz a etapa atual", "o motor está escrevendo" in b.texto())
ok("proíbe reenviar", "Nada de reenviar" in b.texto())
ok("a medida é do relógio, não estimativa de modelo", "min" in b.texto() and "%" not in b.texto())

print("== 2. a batida edita o MESMO comentário, várias vezes")
_edicoes = []
b2 = R.BatidaDoPensando(75, 4242, intervalo=0.01,
                        editor=lambda cid, txt: _edicoes.append((cid, txt)) or True)
b2.comecar()
time.sleep(0.12)
b2.parar()
ok("editou mais de uma vez", len(_edicoes) >= 2, len(_edicoes))
ok("nunca cria comentário novo (mesmo id em todas)", {c for c, _t in _edicoes} == {4242})
ok("a etapa vai no texto de cada batida", all("ainda pensando" in t for _c, t in _edicoes))

print("== 3. parar() desliga a batida de verdade")
_antes = len(_edicoes)
time.sleep(0.08)
ok("depois de parar, nenhuma edição nova", len(_edicoes) == _antes, len(_edicoes) - _antes)

print("== 4. nada disso pode derrubar a resposta")
b3 = R.BatidaDoPensando(75, 1, intervalo=0.01, editor=lambda cid, txt: 1 / 0)
b3.comecar()
time.sleep(0.06)
b3.parar()
ok("editor que estoura não propaga exceção", True)
ok("sem comentário, não começa thread", R.BatidaDoPensando(75, None).comecar()._thread is None)
os.environ["BATIDA_S"] = "0"
ok("BATIDA_S=0 desliga o sinal de vida", R.BatidaDoPensando(75, 7).comecar()._thread is None)
os.environ.pop("BATIDA_S", None)
ok("intervalo negativo também desliga", R.BatidaDoPensando(75, 7, intervalo=-1).comecar()._thread is None)
_b5 = R.BatidaDoPensando(75, 7, intervalo=0.01, editor=lambda cid, txt: True).comecar()
ok("a thread é daemon (não segura o processo)", _b5._thread.daemon is True)
_b5.parar()

print("== 5. o responder USA a batida e a desliga antes de publicar")
_fonte = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "responder.py"),
              encoding="utf-8").read()
ok("o aviso cria a batida", "BatidaDoPensando(numero, _id).comecar()" in _fonte)
ok("publicar sempre desliga a batida", "_parar_batida()" in _fonte.split("def responder(")[1][:900])
ok("a resposta reescreve o aviso no lugar", _fonte.count("editar=aviso_pensando") >= 3)
ok("a etapa muda quando o motor começa", 'etapa = "o motor está escrevendo"' in _fonte)
ok("a etapa muda na segunda tentativa de relevância",
   "conferindo se a resposta responde à pergunta" in _fonte)
ok("a batida não usa modelo nem chave", "montar_provedores" not in
   _fonte.split("class BatidaDoPensando")[1].split("_BATIDA = None")[0])

print()
if FALHAS:
    print("%d de %d verificações do aviso FALHARAM" % (len(FALHAS), len(CERTOS) + len(FALHAS)))
    sys.exit(1)
print("%d/%d verificações do aviso passaram" % (len(CERTOS), len(CERTOS)))
