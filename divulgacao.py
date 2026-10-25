# -*- coding: utf-8 -*-
"""divulgacao.py — publica nos palcos que não dependem do dono.

Palcos keyless/conta-própria (todos sem captcha, testados em 09/10):
  1. Gist (changelog público)          — usa o token da casa (MARKETING_PAT)
  2. Rentry (kit de imprensa editável) — RENTRY_URL + RENTRY_EDIT_CODE
  3. Write.as anônimo (espelho do devlog) — sem conta nenhuma
  4. Paste.rs (snapshot de divulgação) — sem conta, texto puro

Toda função falha SOZINHA (try/except) e devolve o que conseguiu:
`publicar_tudo()` é chamado no domingo, depois do artigo.
"""
import base64
import json
import os
import urllib.parse
import urllib.request

import comum as C

ARQ_DIVULGACAO = "MEMORIA/divulgacao.json"
MAX_REGISTROS = 300
SITE = "https://reboclbrank-max.github.io/site/"


def _http(method, url, corpo=None, cabeceras=None, timeout=60):
    dados = None
    headers = {"User-Agent": "Mozilla/5.0 rebocl-divulgacao/1.0", **(cabeceras or {})}
    if corpo is not None:
        if isinstance(corpo, dict):
            dados = json.dumps(corpo).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            dados = corpo.encode() if isinstance(corpo, str) else corpo
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    r = urllib.request.Request(url, data=dados, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as x:
        bruto = x.read().decode("utf-8", "replace")
        return x.status, (json.loads(bruto) if bruto.strip().startswith(("{", "[")) else bruto)


def _token():
    caminho = "/home/user/tools/.token-github"
    if os.path.exists(caminho):
        return open(caminho).read().strip()
    return os.environ.get("MARKETING_PAT") or os.environ.get("GITHUB_TOKEN") or ""


# ---------------------------------------------------------------- 1. Gist
def gist_changelog(titulo, corpo_markdown):
    """Cria/atualiza o changelog público da Rebocl Brank (identificado pela descrição)."""
    token = _token()
    if not token:
        raise RuntimeError("sem token para gists")
    st, lista = _http("GET", "https://api.github.com/gists?per_page=100", None,
                      {"Authorization": "token " + token})
    gist = None
    if isinstance(lista, list):
        for g in lista:
            if g.get("description") == "REBOCL-CHANGELOG":
                gist = g
                break
    arquivos = {"changelog.md": {"content": corpo_markdown}}
    if gist:
        st, r = _http("PATCH", gist["url"], {"description": "REBOCL-CHANGELOG",
                      "files": arquivos}, {"Authorization": "token " + token})
    else:
        st, r = _http("POST", "https://api.github.com/gists",
                      {"description": "REBOCL-CHANGELOG", "public": True, "files": arquivos},
                      {"Authorization": "token " + token})
    if st not in (200, 201):
        raise RuntimeError(f"gist recusou ({st})")
    return r["html_url"]


# ---------------------------------------------------------------- 2. Rentry
def rentry_atualizar(texto_markdown):
    """Atualiza o kit de imprensa (rentry.co/rebocl-press) com o texto novo."""
    url = (os.environ.get("RENTRY_URL") or "").strip()
    codigo = (os.environ.get("RENTRY_EDIT_CODE") or "").strip()
    if not url or not codigo:
        raise RuntimeError("sem RENTRY_URL/RENTRY_EDIT_CODE")
    st, html = _http("GET", url)
    import re as _re
    m = _re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if not m:
        raise RuntimeError("rentry: csrf não achado na página de edição")
    r = urllib.request.Request(url, method="POST",
        data=urllib.parse.urlencode({"csrfmiddlewaretoken": m.group(1),
            "text": texto_markdown, "edit_code": codigo, "status": "public"}).encode(),
        headers={"User-Agent": "Mozilla/5.0 rebocl-divulgacao/1.0",
                 "Referer": url,
                 "Cookie": "csrftoken=" + _re.search(r'name="csrfmiddlewaretoken"', html).group(0)[:0] or ""})
    with urllib.request.urlopen(r, timeout=60) as x:
        x.read()
    return url


# ---------------------------------------------------------------- 3. Write.as anônimo
def writeas_espelho(titulo, corpo_markdown):
    """Publica o artigo espelho sem conta nenhuma (write.as aceita POST anônimo)."""
    st, r = _http("POST", "https://write.as/api/posts", {"body": corpo_markdown})
    if st not in (200, 201) or not r.get("data", {}).get("id"):
        raise RuntimeError(f"write.as recusou ({st})")
    return "https://write.as/" + r["data"]["id"]


# ---------------------------------------------------------------- 4. Paste.rs
def paste_snapshot(texto):
    r = urllib.request.Request("https://paste.rs/", data=texto.encode(),
                               headers={"User-Agent": "Mozilla/5.0 rebocl-divulgacao/1.0"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.read().decode().strip()


# ---------------------------------------------------------------- registro
def _registrar(item):
    registros = C.ler_remoto(ARQ_DIVULGACAO, [])
    if isinstance(registros, str):
        try:
            registros = json.loads(registros)
        except Exception:
            registros = []
    registros.append(item)
    registros = registros[-MAX_REGISTROS:]
    C.escrever_remoto(ARQ_DIVULGACAO, json.dumps(registros, ensure_ascii=False, indent=1),
                      f"divulgacao: {item.get('acao', 'lote')}")


# ---------------------------------------------------------------- orquestrador
def publicar_tudo(titulo, corpo_markdown):
    """Publica em todos os palcos keyless; devolve resumo honesto do que subiu."""
    links = {}
    # gist: changelog vivo (atualiza o mesmo documento)
    try:
        links["gist"] = gist_changelog(titulo, corpo_markdown)
    except Exception as e:
        C.log(f"divulgacao: gist falhou ({str(e)[:60]})")
    # write.as: página nova por artigo
    try:
        links["write.as"] = writeas_espelho(titulo, corpo_markdown)
    except Exception as e:
        C.log(f"divulgacao: write.as falhou ({str(e)[:60]})")
    # rentry: kit de imprensa permanente (só se as variáveis existirem)
    try:
        kit = ("# Rebocl Brank — Press Kit\n\n" + SITE + "\n\n## Último artigo\n"
               + titulo + "\n\n" + corpo_markdown[:1500])
        links["rentry"] = rentry_atualizar(kit)
    except Exception as e:
        C.log(f"divulgacao: rentry pulado ({str(e)[:60]})")
    _registrar({"data": C.agora().strftime("%Y-%m-%d"), "acao": "publicar_tudo",
                "titulo": titulo, "links": links})
    return links
