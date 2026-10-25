#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memória semântica: indexa as lições (cadernos + manual + lições do dono) por
SIGNIFICADO usando TF-IDF local (scikit-learn, grátis, roda nos servidores).
Busca por conceito: "como divulgar" acha lições de marketing mesmo sem a palavra."""
import json
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


def indexar():
    """(Re)constrói o índice TF-IDF das lições. Roda no ciclo de 6h."""
    itens = _fontes()
    if len(itens) < _MIN:
        return f"Semântica: só {len(itens)} itens; índice fica para o próximo ciclo."
    from sklearn.feature_extraction.text import TfidfVectorizer
    vet = TfidfVectorizer(tokenizer=_tokenizar, ngram_range=(1, 2), min_df=1)
    matriz = vet.fit_transform(itens)
    C.escrever_remoto(ARQ_INDICE, json.dumps(
        {"itens": itens, "vocab": vet.vocabulary_}, ensure_ascii=False)[:1500000],
        "semântica: índice de significados atualizado")
    return f"🔎 Semântica: {len(itens)} lições indexadas por significado."


def buscar(consulta, quantos=4):
    """Busca as lições mais parecidas com a pergunta (por conceito, não palavra exata)."""
    try:
        dados = json.loads(C.ler_remoto(ARQ_INDICE, "{}") or "{}")
        itens, vocab = dados.get("itens") or [], dados.get("vocab") or {}
        if len(itens) < _MIN or not vocab:
            return []
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy  # noqa — garante disponível junto com sklearn
        vet = TfidfVectorizer(tokenizer=_tokenizar, ngram_range=(1, 2), min_df=1, vocabulary=vocab)
        matriz = vet.fit_transform(itens + [consulta])
        sims = (matriz[:-1] @ matriz[-1].T).toarray().ravel()
        ordem = sims.argsort()[::-1][:quantos]
        return [itens[i] for i in ordem if sims[i] > 0.05]
    except Exception as e:
        C.log(f"semântica: busca falhou ({str(e)[:60]})")
        return []


if __name__ == "__main__":
    print(indexar())
