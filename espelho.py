#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sincroniza o conteúdo ATUAL de base e agente para os repositórios espelho (privados).
Só o conteúdo atual — sem histórico antigo (nada de credenciais velhas no espelho)."""
import os
import base64
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


def sincronizar_caminhos(orig, esp, push=True, env=None):
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
