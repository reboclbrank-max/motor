#!/usr/bin/env python3
"""Memória privada: versão-base, conflito explícito e falhas não silenciosas.

O manifesto local não contém conteúdo nem credenciais e não vai para o Git.
Não mescla versões divergentes, não apaga memória remota e não garante transação
entre arquivos. Escritas feitas diretamente pela API continuam canônicas.
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import urllib.request

API = "https://api.github.com"
REPO_MEMORIA = (os.environ.get("REPO_MEMORIA") or "reboclbrank-max/agente").strip() or "reboclbrank-max/agente"
TOKEN = os.environ.get("PAT_MEMORIA", "").strip()
PASTA = os.environ.get("PASTA_MEMORIA", "MEMORIA").strip() or "MEMORIA"
RAMO = os.environ.get("RAMO_MEMORIA", "main").strip() or "main"
MANIFESTO = ".memoria-sync.json"


def log(*partes):
    print("[memoria]", *partes, flush=True)


def _http(metodo, caminho, corpo=None):
    if not TOKEN:
        raise RuntimeError("PAT_MEMORIA ausente")
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(API + caminho, data=dados, method=metodo)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "motor-rebocl")
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        texto = r.read().decode("utf-8")
    return json.loads(texto) if texto else None


def _sha(conteudo):
    return hashlib.sha1(b"blob %d\0" % len(conteudo) + conteudo).hexdigest()


def _escopo():
    return {"repo": REPO_MEMORIA, "ramo": RAMO, "pasta": os.path.abspath(PASTA)}


def _atomico(caminho, conteudo):
    pasta = os.path.dirname(caminho) or "."
    os.makedirs(pasta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sync-", dir=pasta)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _salvar_base(arquivos):
    _atomico(MANIFESTO, json.dumps({"versao": 1, "escopo": _escopo(), "arquivos": arquivos}).encode())


def _ler_base():
    with open(MANIFESTO, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("versao") != 1 or d.get("escopo") != _escopo() or not isinstance(d.get("arquivos"), dict):
        raise ValueError("manifesto de outro escopo ou inválido")
    return d["arquivos"]


def _caminho_seguro(caminho):
    alvo, raiz = os.path.realpath(caminho), os.path.realpath(PASTA)
    return alvo != raiz and os.path.commonpath([alvo, raiz]) == raiz


def listar_remoto():
    try:
        arvore = _http("GET", f"/repos/{REPO_MEMORIA}/git/trees/{RAMO}?recursive=1")
        if not isinstance(arvore, dict) or not isinstance(arvore.get("tree"), list) or arvore.get("truncated"):
            raise ValueError("árvore incompleta")
        return {t["path"]: t["sha"] for t in arvore["tree"]
                if t.get("type") == "blob" and t["path"].startswith(PASTA + "/")}
    except Exception as e:
        log("não consegui listar:", type(e).__name__)
        return None


def baixar():
    # Invalida a base anterior antes de uma nova tentativa, inclusive se a rede cair.
    try:
        if os.path.lexists(MANIFESTO):
            os.unlink(MANIFESTO)
    except OSError:
        log("não consegui invalidar manifesto")
        return 1
    remoto = listar_remoto()
    if remoto is None:
        return 1
    base, erros = {}, 0
    for caminho, sha in sorted(remoto.items()):
        try:
            if not _caminho_seguro(caminho):
                raise ValueError("caminho fora da memória")
            dados = _http("GET", f"/repos/{REPO_MEMORIA}/git/blobs/{sha}")
            conteudo = base64.b64decode(dados["content"])
            if _sha(conteudo) != sha:
                raise ValueError("blob divergente")
            _atomico(caminho, conteudo)
            base[caminho] = sha
        except Exception as e:
            erros += 1
            log("falha ao baixar arquivo:", type(e).__name__)
    # Sem base completa, um passo always() não deve enviar arquivos órfãos/antigos.
    if not erros:
        try:
            _salvar_base(base)
        except Exception as e:
            erros += 1
            log("falha no manifesto:", type(e).__name__)
    log(f"baixados {len(base)}; falhas {erros} (conteúdo não impresso)")
    return int(bool(erros))


def _ler_local(caminho):
    with open(caminho, "rb") as f:
        return f.read()


def subir():
    if not os.path.isdir(PASTA):
        log("nada para subir")
        return 0
    try:
        base = _ler_base()
    except Exception as e:
        log("base não confirmada; nenhum envio:", type(e).__name__)
        return 1
    remoto = listar_remoto()
    if remoto is None:
        return 1
    enviados, iguais, erros = 0, 0, 0
    for raiz, pastas, arquivos in os.walk(PASTA, followlinks=False):
        pastas[:] = [d for d in pastas if not os.path.islink(os.path.join(raiz, d))]
        for nome in sorted(arquivos):
            caminho = os.path.join(raiz, nome).replace(os.sep, "/")
            try:
                if not _caminho_seguro(caminho) or os.path.islink(caminho):
                    raise ValueError("caminho inseguro")
                conteudo = _ler_local(caminho)
                local, existente, anterior = _sha(conteudo), remoto.get(caminho), base.get(caminho)
                if local == existente:
                    iguais += 1
                    base[caminho] = local
                    continue
                if anterior is not None and local == anterior:
                    # O runner não editou: preserve o remoto novo, inclusive remoção.
                    iguais += 1
                    continue
                if existente != anterior:
                    raise ValueError("conflito de versão; remoto preservado")
                corpo = {"message": "memoria: sincroniza alteração do runner", "content": base64.b64encode(conteudo).decode("ascii"), "branch": RAMO}
                if existente:
                    corpo["sha"] = existente
                resposta = _http("PUT", f"/repos/{REPO_MEMORIA}/contents/{caminho}", corpo)
                if not isinstance(resposta, dict) or resposta.get("content", {}).get("sha") != local:
                    raise ValueError("escrita sem recibo de conteúdo confirmado")
                base[caminho] = local
                enviados += 1
            except Exception as e:
                erros += 1
                log("arquivo não confirmado:", type(e).__name__)
    try:
        _salvar_base(base)
    except Exception as e:
        erros += 1
        log("falha no manifesto:", type(e).__name__)
    log(f"subidos {enviados}; sem edição necessária {iguais}; falhas/conflitos {erros}")
    return int(bool(erros))


def main(argv):
    acao = (argv[1] if len(argv) > 1 else "baixar").lower()
    if acao == "baixar":
        return baixar()
    if acao == "subir":
        return subir()
    log("ação desconhecida (use baixar|subir)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
