# -*- coding: utf-8 -*-
"""Suíte do palcos + artigo (offline, com mocks). Roda no CI — 8 checagens."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comum as C  # noqa: E402
import artigo  # noqa: E402

ARQ_ARTIGOS_ORIG = artigo.ARQ_ARTIGOS
import palcos  # noqa: E402

ok = []


def checar(nome, cond):
    ok.append(cond)
    print(("✓" if cond else "✗") + " " + nome)


# 1. apelidos do Gmail (endereços infinitos na mesma caixa)
os.environ["EMAIL_ENDERECO"] = "dona@example.com"
checar("alias_para gera apelido", palcos.alias_para("bluesky") == "dona+bluesky@example.com")
del os.environ["EMAIL_ENDERECO"]
checar("alias_para sem e-mail → None", palcos.alias_para("x") is None)
os.environ["EMAIL_ENDERECO"] = "dona@example.com"

# 2. o livro de ensino tem as linhas duras
livro = palcos.TEXTO_PLAYBOOK
checar("playbook ensina captcha-nunca + selar + queda de conta",
       "Captcha NUNCA" in livro and "selar" in livro and "conta CAIR" in livro and "alias" in livro)

# 3. dividir artigo: título + parágrafos limpos
titulo, parags = artigo._dividir_artigo("## O diário nº 2\n\nParágrafo **um** aqui.\n\nParágrafo dois.")
checar("dividir_artigo extrai título sem #", titulo == "O diário nº 2")
checar("dividir_artigo limpa markdown", parags[0] == "Parágrafo um aqui." and len(parags) == 2)

# 4. teto de registros (cap 200)
store = {"ARQ": json.dumps([{"i": i} for i in range(200)])}
C.ler_remoto = lambda c, p="": store.get(c, p)
escritas = []
C.escrever_remoto = lambda c, n, m="": escritas.append(c) or store.update({c: n}) or True
artigo.ARQ_ARTIGOS = "ARQ"
artigo._registrar({"i": 999})
artigo.ARQ_ARTIGOS = ARQ_ARTIGOS_ORIG
final = json.loads(store["ARQ"])
checar("registro de artigos respeita teto 200", len(final) == 200 and final[-1]["i"] == 999)

# 5. createPage do Telegraph: formato + extração da URL
class _Resp:
    def read(self):
        return json.dumps({"ok": True, "result": {"url": "https://telegra.ph/bastidores-10"}}).encode()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

import urllib.request
origem = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=60: _Resp()
try:
    url = artigo._telegrafo_create_page("tok", "Título", ["a", "b"])
finally:
    urllib.request.urlopen = origem
checar("telegra.ph devolve URL pública", url == "https://telegra.ph/bastidores-10")

# 6. caminhos batizados
checar("arquivos da memória corretos",
       palcos.ARQ_PALCOS == "MEMORIA/palcos.json"
       and palcos.ARQ_PLAYBOOK == "MEMORIA/playbook-palcos.md"
       and artigo.ARQ_ARTIGOS == "MEMORIA/artigos.json")

# 7. criar_contas existem (recriação quando um canal cair)
checar("funções de (re)criação presentes",
       callable(palcos.criar_telegraph) and callable(palcos.criar_bluesky)
       and callable(palcos.criar_mastodon_social) and callable(palcos.confirmar_por_email)
       and callable(palcos.selar))

# 8. criar_artigo: ponta a ponta com mocks (pensar_bem devolve 2 valores!)
store2 = {"MEMORIA/artigos.json": "[]"}
C.ler_remoto = lambda c, p="": store2.get(c, p)
C.escrever_remoto = lambda c, n, m="": store2.update({c: n}) or True
C.pensar_bem = lambda q, s=None: ("Título do devlog\n\nPrimeiro parágrafo.", "motor-teste")
artigo.resumo_na_conversa = lambda t: None
artigo.SITE = "https://reboclbrank-max.github.io/site/"
import types
fake_piloto = types.ModuleType("piloto")
fake_piloto.LINKS = {"ceifalume": "https://ceifalume.itch.io/ceifalume", "prancheta": "https://prancheta.itch.io/prancheta"}
fake_piloto.proximo_jogo = lambda: "ceifalume"
sys.modules["piloto"] = fake_piloto
origem2 = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=60: _Resp()
os.environ["TELEGRAPH_TOKEN"] = "tok-fake"
try:
    url2 = artigo.criar_artigo()
finally:
    urllib.request.urlopen = origem2
regs = json.loads(store2["MEMORIA/artigos.json"])
checar("criar_artigo ponta-a-ponta registra e devolve URL",
       url2.startswith("https://telegra.ph/") and len(regs) == 1 and regs[0]["titulo"] == "Título do devlog")

print()
print("TUDO OK" if all(ok) else "FALHOU", f"({sum(ok)}/{len(ok)})")
sys.exit(0 if all(ok) else 1)
