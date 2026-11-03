#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincroniza o conteúdo ATUAL de base e agente para os repositórios espelho (privados).
Só o conteúdo atual — sem histórico antigo (nada de credenciais velhas no espelho)."""
import os
import base64
import hashlib
import stat
import shutil
import subprocess
import sys
import tempfile

import comum as C

ESPELHOS = {"base": "base-espelho", "agente": "agente-espelho"}


def _git(args, cwd=None, env=None):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"git falhou (código {r.returncode}); argumentos e saída omitidos")
    return r.stdout


def _fotografia(raiz):
    """Snapshot fechado do checkout, sem atravessar links ou arquivos especiais."""
    if os.path.islink(raiz) or not os.path.isdir(raiz):
        raise RuntimeError("espelho: raiz insegura")
    vistos, pastas = {}, set()
    for caminho, dirs, files in os.walk(raiz, followlinks=False):
        if caminho == raiz:
            dirs[:] = [x for x in dirs if x != ".git"]
        for nome in dirs + files:
            p = os.path.join(caminho, nome)
            rel = os.path.relpath(p, raiz).replace(os.sep, "/")
            modo = os.lstat(p)
            if stat.S_ISLNK(modo.st_mode):
                raise RuntimeError("espelho: link simbolico recusado")
            if stat.S_ISDIR(modo.st_mode):
                pastas.add(rel)
                continue
            if not stat.S_ISREG(modo.st_mode) or modo.st_nlink != 1 or nome == ".git":
                raise RuntimeError("espelho: arquivo inseguro")
            descritor = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                st = os.fstat(descritor)
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                    raise RuntimeError("espelho: origem insegura")
                digest = hashlib.sha256()
                with os.fdopen(descritor, "rb", closefd=False) as stream:
                    for bloco in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(bloco)
                fim = os.fstat(descritor)
                novo = os.lstat(p)
                ident = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
                if ident(st) != ident(fim) or ident(fim) != ident(novo):
                    raise RuntimeError("espelho: arquivo alterado durante conferencia")
                vistos[rel] = digest.hexdigest()
            finally:
                os.close(descritor)
    return vistos, pastas


def sincronizar_caminhos(orig, esp, push=True, env=None):
    """Não apaga espelho; bloqueia arquivos extras e cópia não verificada."""
    fonte, dirs_fonte = _fotografia(orig)
    destino, dirs_destino = _fotografia(esp)
    if set(destino) - set(fonte):
        raise RuntimeError("espelho: itens extras exigem revisao")
    if set(fonte) & dirs_destino or dirs_fonte & set(destino):
        raise RuntimeError("espelho: conflito de tipo no caminho")
    for relativo in sorted(fonte):
        if fonte[relativo] == destino.get(relativo):
            continue
        origem = os.path.join(orig, relativo)
        alvo = os.path.join(esp, relativo)
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        shutil.copy2(origem, alvo, follow_symlinks=False)
    copia, _ = _fotografia(esp)
    fonte_apos, _ = _fotografia(orig)
    if copia != fonte or fonte_apos != fonte:
        raise RuntimeError("espelho: conferencia de bytes falhou")
    _git(["add", "-A"], cwd=esp, env=env)
    status = _git(["status", "--porcelain"], cwd=esp, env=env)
    if not status.strip():
        return False
    _git(["-c", "user.name=Espelho (agente)",
          "-c", "user.email=agente@reboclbrank.local",
          "commit", "-q", "-m", "espelho: sincronizado"], cwd=esp, env=env)
    if push:
        _git(["push", "-q", "origin", "HEAD:main"], cwd=esp, env=env)
    return True


def sincronizar(repo, espelho, token):
    """Clona os dois (raso) e sincroniza o conteúdo atual."""
    tmp = tempfile.mkdtemp(prefix=f"espelho-{repo}-")
    env=os.environ.copy()
    env.update({"GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+base64.b64encode(("x-access-token:"+token).encode()).decode(),
                "GIT_TERMINAL_PROMPT":"0"})
    try:
        _git(["clone", "-q", "--depth", "1",
              f"https://github.com/reboclbrank-max/{repo}.git", "orig"], cwd=tmp, env=env)
        _git(["clone", "-q", "--depth", "1",
              f"https://github.com/reboclbrank-max/{espelho}.git", "esp"], cwd=tmp, env=env)
        return sincronizar_caminhos(os.path.join(tmp, "orig"), os.path.join(tmp, "esp"), env=env)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    token = os.environ.get("CHAT_TOKEN", "").strip()
    if not token:
        print("espelho: sem CHAT_TOKEN — abortando")
        return 1
    falhou=False
    for repo, espelho in ESPELHOS.items():
        try:
            mudou = sincronizar(repo, espelho, token)
            C.log(f"espelho: {repo} → {espelho} {'sincronizado' if mudou else 'já estava igual'}")
        except Exception as e:
            falhou=True
            C.log(f"espelho: {repo} falhou ({type(e).__name__}); sem detalhes sensíveis")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
