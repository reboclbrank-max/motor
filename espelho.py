#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincroniza o conteúdo ATUAL de base e agente para os repositórios espelho (privados).
Só o conteúdo atual — sem histórico antigo (nada de credenciais velhas no espelho)."""
import os
import shutil
import subprocess
import sys
import tempfile

import comum as C

ESPELHOS = {"base": "base-espelho", "agente": "agente-espelho"}


def _git(args, cwd=None):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:200]}")
    return r.stdout


def sincronizar_caminhos(orig, esp, push=True):
    """Copia o conteúdo de `orig` para `esp` (diretórios git) e commita. Devolve True se mudou."""
    for item in os.listdir(esp):
        if item == ".git":
            continue
        p = os.path.join(esp, item)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
    for item in os.listdir(orig):
        if item == ".git":
            continue
        src, dst = os.path.join(orig, item), os.path.join(esp, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    _git(["add", "-A"], cwd=esp)
    r = subprocess.run(["git", "status", "--porcelain"], cwd=esp, capture_output=True, text=True)
    if not r.stdout.strip():
        return False  # nada mudou
    _git(["-c", "user.name=Espelho (agente)", "-c", "user.email=agente@reboclbrank.local",
          "commit", "-q", "-m", "espelho: sincronizado"], cwd=esp)
    if push:
        _git(["push", "-q", "origin", "HEAD:main"], cwd=esp)
    return True


def sincronizar(repo, espelho, token):
    """Clona os dois (raso) e sincroniza o conteúdo atual."""
    tmp = tempfile.mkdtemp(prefix=f"espelho-{repo}-")
    try:
        _git(["clone", "-q", "--depth", "1",
              f"https://x-access-token:{token}@github.com/reboclbrank-max/{repo}.git", "orig"], cwd=tmp)
        _git(["clone", "-q", "--depth", "1",
              f"https://x-access-token:{token}@github.com/reboclbrank-max/{espelho}.git", "esp"], cwd=tmp)
        return sincronizar_caminhos(os.path.join(tmp, "orig"), os.path.join(tmp, "esp"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    token = os.environ.get("CHAT_TOKEN", "").strip()
    if not token:
        print("espelho: sem CHAT_TOKEN — abortando")
        return 1
    for repo, espelho in ESPELHOS.items():
        try:
            mudou = sincronizar(repo, espelho, token)
            C.log(f"espelho: {repo} → {espelho} {'sincronizado' if mudou else 'já estava igual'}")
        except Exception as e:
            C.log(f"espelho: {repo} falhou: {str(e)[:150]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
