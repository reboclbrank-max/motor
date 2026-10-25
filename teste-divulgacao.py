# -*- coding: utf-8 -*-
"""Suíte da divulgação keyless (offline, com mocks) — 7 checagens."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comum as C  # noqa: E402
import divulgacao  # noqa: E402

ok = []


def checar(nome, cond):
    ok.append(cond)
    print(("✓" if cond else "✗") + " " + nome)


# mocks de rede (ANTES de qualquer teste: runner não tem .token-github)
chamadas = []


class _Resp:
    def __init__(self, payload, status=200):
        self._payload = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
        self._status = status
    def read(self):
        return self._payload.encode()
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def getcode(self):
        return self._status


divulgacao._token = lambda: "tok-fake"


def _http_fake(method, url, corpo=None, cabeceras=None, timeout=60):
    chamadas.append((method, url, corpo))
    if url.endswith("/gists") or "gists?" in url or "/gists/" in url:
        if method == "GET":
            return 200, [{"description": "REBOCL-CHANGELOG", "url": "https://api.github.com/gists/velho"}]
        if method == "PATCH":
            return 200, {"html_url": "https://gist.github.com/x/velho"}
        return 201, {"html_url": "https://gist.github.com/x/novo"}
    if url == "https://write.as/api/posts":
        return 201, {"data": {"id": "abc123"}}
    if url == "https://paste.rs/":
        return 200, "https://paste.rs/xyz"
    return 404, "não sei"

divulgacao._http = _http_fake
import urllib.request
urllib.request.urlopen_orig = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=60: _Resp("https://paste.rs/xyz")
divulgacao.urllib.request.urlopen = lambda req, timeout=60: _Resp("https://paste.rs/xyz")

# 1. gist atualiza o changelog EXISTENTE (procura pela descrição)
url = divulgacao.gist_changelog("Semana 41", "# changelog")
checar("gist atualiza o existente (PATCH)", url.endswith("/velho")
       and any(m == "PATCH" for m, _, _ in chamadas))

# 2. sem token → erro claro, sem exceção feia
divulgacao._token = lambda: ""
try:
    divulgacao.gist_changelog("t", "c")
    checar("sem token levanta RuntimeError", False)
except RuntimeError:
    checar("sem token levanta RuntimeError", True)
divulgacao._token = lambda: "tok-fake"

# 3. write.as espelho devolve URL pública
checar("write.as devolve url da página", divulgacao.writeas_espelho("t", "c") == "https://write.as/abc123")

# 4. rentry sem variáveis → RuntimeError limpa (não quebra o lote)
os.environ.pop("RENTRY_URL", None)
try:
    divulgacao.rentry_atualizar("x")
    checar("rentry sem segredo → RuntimeError", False)
except RuntimeError:
    checar("rentry sem segredo → RuntimeError", True)

# 5. publicar_tudo: lote completo com mocks (rentry falha, resto sobe)
os.environ["EMAIL_X"] = "1"
store = {}
C.ler_remoto = lambda c, p="": store.get(c, p)
C.escrever_remoto = lambda c, n, m="": store.update({c: n}) or True
C.log = lambda m: None
links = divulgacao.publicar_tudo("Artigo da semana", "corpo")
checar("publicar_tudo sobe gist+write.as mesmo com rentry ausente",
       "gist" in links and "write.as" in links and "rentry" not in links)

# 6. registro do lote
regs = json.loads(store[divulgacao.ARQ_DIVULGACAO])
checar("lote registrado na memória", len(regs) == 1 and regs[0]["titulo"] == "Artigo da semana")

# 7. arquivo de registro batizado
checar("registro em MEMORIA/divulgacao.json", divulgacao.ARQ_DIVULGACAO == "MEMORIA/divulgacao.json")

print()
print("TUDO OK" if all(ok) else "FALHOU", f"({sum(ok)}/{len(ok)})")
sys.exit(0 if all(ok) else 1)
