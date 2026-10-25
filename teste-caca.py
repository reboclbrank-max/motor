#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline da ferramenta [[CACA:]]: última caça às nuvens, keyless do
mundo, caso vazio honesto. Fakes no padrão da casa (GITHUB_TOKEN="")."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa

store = {
    "MEMORIA/caza-motores.json": json.dumps({
        "quando": "2026-10-11T22:35:46",
        "or_free": {"vivos": ["nvidia/nemotron-3-ultra-550b-a55b:free"]},
        "ollama": {"vivos": ["nemotron-3-ultra", "gpt-oss:120b"]},
        "hf": {"vivos": []},
        "polli": {"vivos": ["openai-fast"]},
    }),
    "MEMORIA/caza-mundial.json": json.dumps({
        "alvos_testados": 34,
        "VIVO_no_ar": [{"motor": "pollinations/openai-fast"}],
    }),
}
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)

ok = True


def checar(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


s = C._ferramenta_caca()
checar("mostra vivos da caça (ultra + gpt-oss)", "nemotron-3-ultra" in s and "gpt-oss:120b" in s)
checar("mostra keyless do mundo (pollinations)", "pollinations/openai-fast" in s)
checar("mostra a autópsia mundial (34 alvos)", "34" in s)
checar("traz a regra da casa (prova de fogo)", "prova de fogo" in s)

store.clear()
s2 = C._ferramenta_caca()
checar("sem caça → mensagem honesta", "sem caça registrada" in s2)

print("teste-caca:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
