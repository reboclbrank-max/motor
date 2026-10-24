#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincroniza a MEMÓRIA do repositório privado com o runner público — 2026-10-24.

POR QUE EXISTE: este repositório (`motor`) é público para ter minutos de Actions
ilimitados. A memória da casa (diário, conversas, banco, anotações) **não pode** morar
aqui. Então o job baixa a memória do repositório privado no início, trabalha em cima
dela e devolve o que mudou no fim — sempre pela API, com o token em secret.

REGRAS (não regredir):
  * nada de MEMORIA/ entra no git deste repositório (está no .gitignore);
  * a memória nunca é impressa no log, só contada;
  * `subir` só envia arquivos que mudaram de verdade, e nunca apaga nada do privado;
  * falha de rede não derruba o trabalho: avisa e segue.
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
REPO_MEMORIA = os.environ.get("REPO_MEMORIA", "reboclbrank-max/agente").strip()
TOKEN = os.environ.get("PAT_MEMORIA", "").strip()
PASTA = os.environ.get("PASTA_MEMORIA", "MEMORIA").strip() or "MEMORIA"
RAMO = os.environ.get("RAMO_MEMORIA", "main").strip() or "main"


def log(*partes):
    print("[memoria]", *partes, flush=True)


def _http(metodo, caminho, corpo=None):
    if not TOKEN:
        raise RuntimeError("PAT_MEMORIA ausente")
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(caminho if caminho.startswith("http") else API + caminho,
                                 data=dados, method=metodo)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "motor-rebocl")
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        texto = r.read().decode("utf-8")
    return json.loads(texto) if texto else None


def listar_remoto():
    """Devolve {caminho: sha} de todos os arquivos da memória no repositório privado."""
    try:
        arvore = _http("GET", f"/repos/{REPO_MEMORIA}/git/trees/{RAMO}?recursive=1")
    except Exception as e:
        log(f"não consegui listar: {e}")
        return None
    if not isinstance(arvore, dict) or "tree" not in arvore:
        log("resposta sem árvore")
        return None
    return {t["path"]: t["sha"] for t in arvore["tree"]
            if t.get("type") == "blob" and t["path"].startswith(PASTA + "/")}


def baixar():
    remoto = listar_remoto()
    if remoto is None:
        return 1
    baixados = 0
    for caminho in sorted(remoto):
        try:
            dados = _http("GET", f"/repos/{REPO_MEMORIA}/git/blobs/{remoto[caminho]}")
            conteudo = base64.b64decode(dados["content"])
        except Exception as e:
            log(f"falhou {caminho}: {type(e).__name__}")
            continue
        pasta = os.path.dirname(caminho)
        if pasta and not os.path.isdir(pasta):
            os.makedirs(pasta, exist_ok=True)
        with open(caminho, "wb") as f:
            f.write(conteudo)
        baixados += 1
    log(f"baixados {baixados} arquivo(s) de {REPO_MEMORIA}/{PASTA} (o conteúdo não é impresso)")
    return 0


def _ler_local(caminho):
    with open(caminho, "rb") as f:
        return f.read()


def subir():
    remoto = listar_remoto()
    if remoto is None:
        return 1
    enviados, iguais = 0, 0
    if not os.path.isdir(PASTA):
        log("nada para subir")
        return 0
    for raiz, _, arquivos in os.walk(PASTA):
        for nome in sorted(arquivos):
            caminho = os.path.join(raiz, nome).replace(os.sep, "/")
            try:
                conteudo = _ler_local(caminho)
            except OSError:
                continue
            existente = remoto.get(caminho)
            if existente:
                # compara pelo sha do blob que o GitHub já tem
                import hashlib
                sha_local = hashlib.sha1(b"blob %d\0" % len(conteudo) + conteudo).hexdigest()
                if sha_local == existente:
                    iguais += 1
                    continue
            corpo = {
                "message": f"memoria: sincroniza {caminho} (runner público)",
                "content": base64.b64encode(conteudo).decode("ascii"),
                "branch": RAMO,
            }
            if existente:
                corpo["sha"] = existente
            try:
                _http("PUT", f"/repos/{REPO_MEMORIA}/contents/{caminho}", corpo)
                enviados += 1
            except Exception as e:
                log(f"não subi {caminho}: {type(e).__name__}")
    log(f"subidos {enviados} arquivo(s), {iguais} sem mudança (nada é apagado no privado)")
    return 0


def main(argv):
    acao = (argv[1] if len(argv) > 1 else "baixar").lower()
    if acao == "baixar":
        return baixar()
    if acao == "subir":
        return subir()
    log(f"ação desconhecida: {acao} (use baixar|subir)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
