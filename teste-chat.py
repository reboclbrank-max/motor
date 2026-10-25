#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste de integração do CHAT (chat/index.html): os superpoderes precisam
estar presentes no ar — mãos, vigia, ouro, streaming, TTS, ditado, seletor.
Usa só URLs públicas (github.io + censo.json); nenhum segredo."""
import json
import sys
import urllib.request

ok = True


def checar(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


def pagina():
    r = urllib.request.Request("https://reboclbrank-max.github.io/chat/",
                               headers={"User-Agent": "teste-chat"})
    return urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "replace")


s = pagina()
checar("chat no ar (index servido)", len(s) > 20000)
for marcador, nome in [
    ("maosDaCasa", "mãos da casa (!status/!censo/!livro)"),
    ("cacarFrota", "vigia automático (caça da frota)"),
    ("A CASA ACORDOU", "pulso da casa (amanhecer)"),
    ("pensarStream", "streaming token-a-token"),
    ("reasoning_content", "💭 pensamento ao vivo"),
    ("btn-mic", "🎤 ditado por voz"),
    ("btn-turbo", "⚡ TURBO"),
    ("sel-cerebro", "🧠 seletor de cérebro"),
    ("OURO", "cadeia do ouro (14)"),
    ("!pesquisar", "📖 pesquisa aberta"),
]:
    checar("tem " + nome, marcador in s)
checar("cadeia tem 14 motores", s.count("base: 'https://nvidia.g4f.dev/v1'") >= 13 and "text.pollinations.ai" in s)
try:
    censo = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://reboclbrank-max.github.io/site/censo.json",
        headers={"User-Agent": "teste-chat"}), timeout=30).read().decode())
    checar(f"censo.json vivo ({len(censo)} motores)", len(censo) >= 1500)
except Exception as e:
    checar("censo.json vivo (" + str(e)[:40] + ")", False)

print("teste-chat:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
