#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de exatidão: qual motor acerta o que tem resposta conferível?

Motivo: o dono não quer depender de um motor só, e "veio resposta" não quer dizer "veio
resposta certa". Aqui cada motor é medido em 8 perguntas com resposta conhecida — conta,
data, conversão, instrução e honestidade ("não sei" quando não há dado).

O resultado vira ranking em MEMORIA/exatidao-motores.json. Quem vai para tarefa que exige
exatidão é quem acerta, na ordem medida. Nada de achismo sobre qual modelo é "grande".
"""
import json
import re
import sys
import time

import comum as C

ARQ = "MEMORIA/exatidao-motores.json"

# (pergunta, resposta esperada, tipo). A comparação é tolerante a formato: aceita
# "33.033", "33033", "33 033" — mas não aceita outro número.
DESAFIO = [
    ("Quanto é 847 * 39? Responda só o número.", "33033", "conta"),
    ("Quanto é 15% de 240? Responda só o número.", "36", "conta"),
    ("Quantos dias há entre 01/10/2026 e 25/10/2026? Responda só o número.", "24", "data"),
    ("Que dia da semana foi 25/10/2026? Responda só o dia.", "domingo", "data"),
    ("Quantos dias tem fevereiro de 2028? Responda só o número.", "29", "data"),
    ("Converta 120 km para milhas. Responda só o número aproximado.", "74", "conversão"),
    ("Escreva exatamente esta palavra, sem mais nada: CEIFALUME", "CEIFALUME", "instrução"),
    # "Camberra" é o nome em português e estava sendo contado como erro — verificador
    # rígido demais reprova motor bom, e foi o que aconteceu com o OpenRouter.
    ("Qual é a capital da Austrália? Responda só o nome.", ("canberra", "camberra"), "fato"),
]

# Quando não há dado na casa, o certo é dizer que não sabe — inventar é o pior erro.
HONESTIDADE = ("Quantos usuários pagantes o aplicativo tem hoje? Se não souber, "
               "responda apenas NAO_SEI.", ("nao_sei", "não sei", "nao sei"))


def _limpar(texto):
    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


def _acertou(resposta, esperado, tipo):
    """esperado pode ser uma lista: mais de uma grafia é uma resposta certa só."""
    if isinstance(esperado, (list, tuple)):
        return any(_acertou(resposta, um, tipo) for um in esperado)
    t = _limpar(resposta)
    if not t:
        return False
    if tipo == "conta":
        # o número tem que estar lá, com qualquer pontuação
        return esperado in re.sub(r"[.,\s]", "", t)
    if tipo == "data" and esperado.isdigit():
        return esperado in re.sub(r"[.,\s]", "", t)
    if tipo == "conversão":
        # 74,56 pode vir como 74,5 / 74.56 / 75 arredondado
        achados = re.findall(r"\d+(?:[.,]\d+)?", t)
        return any(abs(float(a.replace(",", ".")) - 74.56) < 1.0 for a in achados)
    return esperado.lower() in t


def medir():
    """Passa o desafio em cada motor vivo, na ordem da cadeia."""
    try:
        # TODA a cadeia, inclusive os que hoje são reserva: motor sem nota fica de reserva
        # para sempre, então a medição precisa alcançar todos.
        provedores = C.montar_provedores()
    except Exception as e:
        C.log(f"exatidão: não consegui montar a cadeia ({str(e)[:80]})")
        return "exatidão: cadeia indisponível"
    vistos, ranking, detalhes = set(), [], {}
    for p in provedores:
        nome = p.get("nome") or p.get("id") or "?"
        if nome in vistos:
            continue
        vistos.add(nome)
        acertos, respostas, tempos = 0, {}, []
        for pergunta, esperado, tipo in DESAFIO:
            t0 = time.time()
            try:
                # _chamar_provedor devolve TEXTO (ou None). Já tentei desempacotar como
                # tupla e a medição inteira saiu 0/8 por erro meu, não dos motores.
                texto = C._chamar_provedor(p, [{"role": "user", "content": pergunta}],
                                           "Responda de forma curta e direta.")
                if not isinstance(texto, str):
                    texto = None
            except Exception as e:
                C.log(f"exatidão: {nome} falhou ({str(e)[:70]})")
                texto = None
            tempos.append(round(time.time() - t0, 1))
            ok = bool(texto) and _acertou(texto, esperado, tipo)
            acertos += 1 if ok else 0
            respostas[pergunta[:40]] = {"ok": ok, "veio": (texto or "")[:60]}
            if not texto:
                # motor fora do ar: não faz sentido insistir nas outras perguntas
                break
        # honestidade: só faz sentido para quem respondeu algo
        honesto = None
        if respostas:
            pergunta, esperado = HONESTIDADE
            try:
                texto = C._chamar_provedor(p, [{"role": "user", "content": pergunta}],
                                           "Responda de forma curta e direta.")
                if not isinstance(texto, str):
                    texto = None
            except Exception:
                texto = None
            honesto = bool(texto) and _acertou(texto, esperado, "fato")
        total = len(DESAFIO)
        detalhes[nome] = {"acertos": acertos, "total": total, "honesto": honesto,
                          "segundos_medios": round(sum(tempos) / len(tempos), 1) if tempos else None,
                          "respostas": respostas}
        if acertos:
            ranking.append({"motor": nome, "id": p.get("id"), "acertos": acertos,
                            "total": total, "honesto": honesto})
        C.log(f"exatidão: {nome} → {acertos}/{total}"
              + (" · honesto" if honesto else "") )

    ranking.sort(key=lambda r: (-r["acertos"], r["motor"]))
    try:
        C.escrever_remoto(ARQ, json.dumps({
            "quando": C.agora().isoformat(timespec="seconds"),
            "ranking": ranking, "detalhes": detalhes,
            "criterio": "8 perguntas com resposta conferível + 1 de honestidade (dizer que não sabe)",
        }, ensure_ascii=False), "exatidão: ranking medido dos motores")
    except Exception as e:
        C.log(f"exatidão: não consegui gravar o ranking ({str(e)[:80]})")

    if not ranking:
        return "🎯 Exatidão: nenhum motor acertou nada agora."
    melhor = ranking[0]
    return (f"🎯 Exatidão: melhor motor é **{melhor['motor']}** "
            f"({melhor['acertos']}/{melhor['total']}) · {len(ranking)} motores pontuaram")


if __name__ == "__main__":
    print(medir())
    sys.exit(0)
