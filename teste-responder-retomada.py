#!/usr/bin/env python3
"""Retomada offline da fiação do respondedor em processos realmente novos.

O destino e a outbox são um repositório sintético em arquivo temporário. Nenhum worker
herda segredos ou chama rede. Falhas podem ocorrer antes ou depois do efeito simulado.
"""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlparse

REPO = "sintetico/conversas"
ASSINATURA = "🤖 **Assistente Rebocl**"
DONO = "dono-sintetico"


def carregar(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def salvar(caminho, estado):
    destino = Path(caminho)
    temporario = destino.with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    os.replace(temporario, destino)


def inicial(falha=None, comentarios=None):
    return {"arquivos": {}, "comentarios": copy.deepcopy(comentarios or []),
            "posts": 0, "edicoes": 0, "proximo_id": 100,
            "proximo_sha": 1, "falha": falha}


def worker(caminho, cenario):
    import comum as C
    import outbox as O
    import responder as R

    estado = carregar(caminho)
    C.REPO = REPO
    C.DONO_GITHUB = DONO
    C.ASSINATURA = ASSINATURA
    C.MARCA_DO_ROBO = "<!--robo:"

    def gh(metodo, rota, corpo=None):
        prefixo = "/repos/" + REPO + "/contents/"
        if rota.startswith(prefixo):
            chave = rota[len(prefixo):]
            atual = estado["arquivos"].get(chave)
            if metodo == "GET":
                if atual is None:
                    raise RuntimeError("HTTP 404: outbox sintética ausente")
                return copy.deepcopy(atual)
            if metodo == "PUT":
                sha_recebido = corpo.get("sha")
                if atual is not None and sha_recebido != atual["sha"]:
                    raise RuntimeError("HTTP 409: checkpoint sintético divergente")
                if atual is None and sha_recebido:
                    raise RuntimeError("HTTP 409: atualização de checkpoint ausente")
                sha = str(estado["proximo_sha"])
                estado["proximo_sha"] += 1
                estado["arquivos"][chave] = {"content": corpo["content"], "sha": sha}
                salvar(caminho, estado)
                return {"content": {"sha": sha}}
        parsed = urlparse(rota)
        if parsed.path == f"/repos/{REPO}/issues/1/comments" and metodo == "GET":
            pagina = int(parse_qs(parsed.query)["page"][0])
            inicio = (pagina - 1) * 100
            return copy.deepcopy(estado["comentarios"][inicio:inicio + 100])
        if parsed.path == f"/repos/{REPO}/issues/1/comments" and metodo == "POST":
            estado["posts"] += 1
            falha = estado["falha"]
            estado["falha"] = None
            if falha == "antes_post":
                salvar(caminho, estado)
                raise RuntimeError("falha injetada antes do POST")
            ident = estado["proximo_id"]
            estado["proximo_id"] += 1
            estado["comentarios"].append(
                {"id": ident, "body": corpo["body"], "user": {"login": DONO}})
            salvar(caminho, estado)
            if falha == "depois_post":
                raise RuntimeError("falha injetada depois do POST")
            return {"id": ident}
        raise AssertionError("rota sintética inesperada: " + metodo + " " + rota)

    def editar(ident, payload):
        estado["edicoes"] += 1
        falha = estado["falha"]
        estado["falha"] = None
        if falha == "antes_edicao":
            salvar(caminho, estado)
            raise RuntimeError("falha injetada antes da edição")
        for comentario in estado["comentarios"]:
            if comentario["id"] == ident:
                comentario["body"] = payload
                break
        else:
            salvar(caminho, estado)
            return False
        salvar(caminho, estado)
        if falha == "depois_edicao":
            raise RuntimeError("falha injetada depois da edição")
        return True

    C.gh = gh
    C.editar_comentario = editar
    C.comentar = lambda *args: (_ for _ in ()).throw(AssertionError("fallback legado proibido"))
    C.comentarios_da_conversa_verificados = lambda numero: copy.deepcopy(estado["comentarios"])
    R._parar_batida = lambda: None
    os.environ["REBOCL_OUTBOX_COMENTARIOS"] = "1"
    try:
        if cenario == "edicao":
            retorno = R.responder(1, "edição retomada", "a9201", editar=77)
        elif cenario == "conflito":
            retorno = R.responder(1, "payload divergente", "a9101")
        else:
            retorno = R.responder(1, "resposta retomada", "a9101")
        print(json.dumps(retorno, ensure_ascii=False, sort_keys=True))
        return 0
    except O.EfeitoIncerto as erro:
        print("INCERTO: " + str(erro))
        return 23
    except O.ConflitoOutbox as erro:
        print("CONFLITO: " + str(erro))
        return 24


def principal():
    resultados = []

    def checar(nome, condicao):
        resultados.append((nome, bool(condicao)))
        print(("PASS" if condicao else "FAIL") + " — " + nome)

    def invocar(caminho, cenario, codigo):
        env = {k: os.environ[k] for k in
               ("HOME", "PATH", "LANG", "LC_ALL", "TMPDIR", "PYTHONPATH") if k in os.environ}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        executado = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker", str(caminho), cenario],
            cwd=Path(__file__).resolve().parent, env=env, text=True,
            capture_output=True, timeout=20)
        if executado.returncode != codigo:
            print(executado.stdout, end="")
            print(executado.stderr, end="", file=sys.stderr)
        checar(f"worker {cenario} retorna {codigo}", executado.returncode == codigo)
        return carregar(caminho)

    def registros(estado):
        saida = []
        for info in estado["arquivos"].values():
            saida.append(json.loads(base64.b64decode(info["content"]).decode("utf-8")))
        return saida

    with tempfile.TemporaryDirectory(prefix="retomada-respondedor-") as pasta:
        alvo = Path(pasta) / "depois-post.json"
        salvar(alvo, inicial("depois_post"))
        estado = invocar(alvo, "normal", 23)
        registro = registros(estado)[0]
        checar("falha pós-POST preserva um único efeito e marca incerteza",
               estado["posts"] == 1 and len(estado["comentarios"]) == 1
               and registro["estado"] == "incerto" and registro["tentativas"] == 1)
        estado = invocar(alvo, "normal", 0)
        registro = registros(estado)[0]
        checar("processo novo reconcilia pós-POST sem repetir efeito",
               estado["posts"] == 1 and len(estado["comentarios"]) == 1
               and registro["estado"] == "confirmado" and registro["tentativas"] == 1)
        estado = invocar(alvo, "normal", 0)
        checar("terceiro processo mantém confirmação idempotente",
               estado["posts"] == 1 and len(estado["comentarios"]) == 1
               and registros(estado)[0]["estado"] == "confirmado")
        estado["comentarios"] = []
        salvar(alvo, estado)
        estado = invocar(alvo, "normal", 23)
        checar("evidência confirmada que desaparece bloqueia novo POST",
               estado["posts"] == 1 and not estado["comentarios"]
               and registros(estado)[0]["estado"] == "confirmado")

        alvo = Path(pasta) / "antes-post.json"
        salvar(alvo, inicial("antes_post"))
        estado = invocar(alvo, "normal", 23)
        checar("falha antes do POST deixa intenção incerta sem efeito",
               estado["posts"] == 1 and not estado["comentarios"]
               and registros(estado)[0]["estado"] == "incerto")
        estado = invocar(alvo, "normal", 23)
        checar("ausência remota não libera retry cego após reinício",
               estado["posts"] == 1 and not estado["comentarios"]
               and registros(estado)[0]["tentativas"] == 1)
        corpo = registros(estado)[0]["payload"]["body"]
        estado["comentarios"].append({"id": 200, "body": corpo, "user": {"login": DONO}})
        salvar(alvo, estado)
        estado = invocar(alvo, "normal", 0)
        checar("evidência tardia é adotada sem segunda tentativa",
               estado["posts"] == 1 and len(estado["comentarios"]) == 1
               and registros(estado)[0]["estado"] == "confirmado")
        estado = invocar(alvo, "conflito", 24)
        checar("mesma origem com payload diferente exige revisão",
               estado["posts"] == 1 and len(estado["comentarios"]) == 1)

        alvo = Path(pasta) / "depois-edicao.json"
        pendente = {"id": 77, "body": ASSINATURA + "\n\npensando",
                    "user": {"login": DONO}}
        salvar(alvo, inicial("depois_edicao", [pendente]))
        estado = invocar(alvo, "edicao", 23)
        checar("falha pós-edição preserva efeito no mesmo comentário",
               estado["edicoes"] == 1 and estado["posts"] == 0
               and len(estado["comentarios"]) == 1
               and registros(estado)[0]["estado"] == "incerto")
        estado = invocar(alvo, "edicao", 0)
        checar("processo novo reconcilia edição sem reeditar nem criar POST",
               estado["edicoes"] == 1 and estado["posts"] == 0
               and estado["comentarios"][0]["id"] == 77
               and registros(estado)[0]["estado"] == "confirmado")

    falhas = [nome for nome, ok in resultados if not ok]
    print(f"\n{len(resultados)-len(falhas)}/{len(resultados)} contratos PASS")
    if falhas:
        raise SystemExit("Falhas: " + "; ".join(falhas))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=2, metavar=("ARQUIVO", "CENARIO"))
    args = parser.parse_args()
    if args.worker:
        raise SystemExit(worker(args.worker[0], args.worker[1]))
    principal()
