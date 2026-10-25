#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memória semântica: indexa as lições (cadernos + manual + lições do dono) por
SIGNIFICADO usando TF-IDF local em Python puro.
Busca por conceito: "como divulgar" acha lições de marketing mesmo sem a palavra.

Sem scikit-learn de propósito: o runner do GitHub não traz sklearn e instalar a
cadeia (numpy/scipy/scikit-learn) custa minutos por execução. TF-IDF é conta
simples — aqui roda em qualquer Python 3, offline e sem dependência nenhuma."""
import json
import math
import re

import comum as C

ARQ_INDICE = "MEMORIA/indice-semantico.json"
_MIN = 3


def _fontes():
    """Recolhe as lições atuais: cadernos de estudo da semana + lições + manual."""
    itens = []
    try:
        lista = C.gh("GET", f"/repos/{C.REPO}/contents/MEMORIA") or []
        for f in lista:
            if re.match(r"estudos-\d{2}-\d{2}-\d{4}\.md$", f.get("name", "")):
                txt = C.ler_remoto("MEMORIA/" + f["name"], "")
                for l in txt.splitlines():
                    l = l.strip()
                    if l.startswith("- "):
                        itens.append(l[2:][:180])
    except Exception as e:
        C.log(f"semântica: cadernos falharam ({str(e)[:60]})")
    for arq in (C.ARQ_LICOES, "MEMORIA/manual.md"):
        try:
            for l in C.ler_remoto(arq, "").splitlines():
                l = l.strip()
                if l.startswith("- ") and len(l) > 10:
                    itens.append(l[2:][:180])
        except Exception:
            pass
    vistos, unicos = set(), []
    for it in itens:
        chave = it.lower()[:80]
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(it)
    return unicos[:800]


def _tokenizar(t):
    return [w for w in re.findall(r"[a-záéíóúâêôãõç]{3,}", t.lower())]


def _termos(texto):
    """Unigramas + bigramas, o mesmo vocabulário que o índice guarda."""
    palavras = _tokenizar(texto)
    termos = list(palavras)
    termos += [palavras[i] + " " + palavras[i + 1] for i in range(len(palavras) - 1)]
    return termos


def _tf(texto):
    """Frequência do termo normalizada pelo tamanho do texto."""
    conta = {}
    termos = _termos(texto)
    if not termos:
        return {}
    for t in termos:
        conta[t] = conta.get(t, 0) + 1
    total = float(len(termos))
    return {t: n / total for t, n in conta.items()}


def _idf(docs):
    """IDF suavizado: termo que aparece em todo documento vale quase nada."""
    n = float(len(docs))
    vistos = {}
    for d in docs:
        for t in set(_termos(d)):
            vistos[t] = vistos.get(t, 0) + 1
    return {t: math.log((1.0 + n) / (1.0 + f)) + 1.0 for t, f in vistos.items()}


def _vetor(texto, idf):
    """Vetor TF-IDF esparso (dict) restrito ao vocabulário do índice."""
    tf = _tf(texto)
    return {t: v * idf[t] for t, v in tf.items() if t in idf}


def _cosseno(a, b):
    if not a or not b:
        return 0.0
    num = sum(v * b.get(t, 0.0) for t, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return num / (na * nb) if na and nb else 0.0


def indexar():
    """(Re)constrói o índice TF-IDF das lições. Roda no ciclo de 6h."""
    itens = _fontes()
    if len(itens) < _MIN:
        return f"Semântica: só {len(itens)} itens; índice fica para o próximo ciclo."
    idf = _idf(itens)
    C.escrever_remoto(ARQ_INDICE, json.dumps(
        {"itens": itens, "vocab": list(idf), "idf": idf}, ensure_ascii=False)[:1500000],
        "semântica: índice de significados atualizado")
    return f"🔎 Semântica: {len(itens)} lições indexadas por significado."


def buscar(consulta, quantos=4):
    """Busca as lições mais parecidas com a pergunta (por conceito, não palavra exata)."""
    try:
        dados = json.loads(C.ler_remoto(ARQ_INDICE, "{}") or "{}")
        itens = dados.get("itens") or []
        if len(itens) < _MIN:
            return []
        idf = dados.get("idf")
        # índice antigo (gravado com sklearn) não tem idf: recalcula na hora, sem quebrar.
        if not isinstance(idf, dict) or not idf:
            idf = _idf(itens)
        alvo = _vetor(consulta, idf)
        if not alvo:
            return []
        notas = [(_cosseno(_vetor(it, idf), alvo), it) for it in itens]
        notas.sort(key=lambda par: par[0], reverse=True)
        return [it for nota, it in notas[:quantos] if nota > 0.05]
    except Exception as e:
        C.log(f"semântica: busca falhou ({str(e)[:60]})")
        return []


if __name__ == "__main__":
    print(indexar())
