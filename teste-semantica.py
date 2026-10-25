#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste offline da memória semântica (índice, busca por conceito, injeção no cérebro)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa
import memoria_semantica as S  # noqa

licoes = [
    "Poste nos canais no horário de maior movimento (12h e 19h) para mais views",
    "O medo nasce da ameaça à segurança, não do sangue — dread antes do gore",
    "Use coyote time de 0.1s para o pulo parecer justo",
    "Responda todo comentário em até 24h para o algoritmo te empurrar",
    "Save com 3 backups rotativos evita perder o progresso do jogador",
]
store = {
    C.ARQ_LICOES: "\n".join("- " + l for l in licoes),
    "MEMORIA/manual.md": "# Manual\n- sempre variar o ângulo dos posts",
}
C.gh = lambda metodo, caminho, corpo=None: []
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)
C.escrever_remoto = lambda caminho, conteudo, mensagem="": store.update({caminho: conteudo}) or True

ok = True


def checar(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


r = S.indexar()
checar("índice semântico criado", "indexadas" in r)
a = S.buscar("o jogador perdeu o save dele")
checar("busca por conceito acha a lição certa", a and "Save" in a[0])
b = S.buscar("como deixar o pulo mais gostoso")
checar("busca acha game feel", b and "coyote" in b[0])
checar("busca sem índice não explode", S.buscar("qualquer coisa") is not None)
fonte = open("comum.py", encoding="utf-8").read()
checar("cérebro injeta lições relacionadas", "memória semântica" in fonte and "Lições da sua memória" in fonte)

print("\nTESTE SEMANTICA:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
