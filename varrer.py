#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Varre as conversas do repositório privado e responde as pendentes — 2026-10-24.

POR QUE EXISTE: o trabalhador agora roda no repositório público `motor` (minutos
ilimitados), mas as conversas ficam em issues do `agente`, que é privado. Um repositório
não recebe evento de issue de outro, então este varredor procura o que ficou pendente.
Também serve de rede de segurança: se o evento do `agente` falhar, a varredura pega.

REGRAS (não regredir):
  * só processa mensagem escrita pelo DONO (nunca a de estranho que apareça na issue);
  * nunca responde duas vezes: usa a mesma marca invisível do responder;
  * teto de mensagens por rodada (custo de cota de LLM);
  * silêncio não é opção: erro em uma conversa não impede as outras.
"""
import datetime
import json
import os
import sys
import tempfile

import comum as C
import responder

MAX_POR_RODADA = int(os.environ.get("MAX_POR_RODADA", "3"))
JANELA_HORAS = int(os.environ.get("JANELA_HORAS", "72"))


def log(*partes):
    print("[varredura]", *partes, flush=True)


def _marca_de(corpo):
    """Extrai a marca `<!--resp:...-->` de um comentário, se existir."""
    texto = corpo or ""
    i = texto.find("<!--resp:")
    if i < 0:
        return None
    fim = texto.find("-->", i)
    return texto[i + len("<!--resp:"):fim].strip() if fim > i else None


def _do_dono(usuario):
    return (usuario or {}).get("login") == C.DONO_GITHUB and (usuario or {}).get("type") != "Bot"


def pendentes(limite_dias=None):
    """Lista (issue, comentario|None) cuja última mensagem do dono não foi respondida."""
    # utcnow (naive) para comparar com o updated_at da API, que é naive depois do slice
    desde = datetime.datetime.utcnow() - datetime.timedelta(
        hours=JANELA_HORAS if limite_dias is None else limite_dias)
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?state=open&sort=updated&direction=desc&per_page=30") or []
    except Exception as e:
        log(f"não consegui listar as conversas: {e}")
        return []
    achados = []
    for issue in issues:
        if issue.get("pull_request"):
            continue
        try:
            quando = issue.get("updated_at", "")
            instante = datetime.datetime.fromisoformat(quando.replace("Z", "+00:00")).replace(tzinfo=None)
            if instante < desde:
                continue
        except (ValueError, AttributeError):
            pass
        if not _do_dono(issue.get("user")):
            continue
        numero = issue.get("number")
        try:
            comentarios = C.gh("GET", f"/repos/{C.REPO}/issues/{numero}/comments?per_page=100") or []
        except Exception as e:
            log(f"conversa #{numero}: comentários ilegíveis ({type(e).__name__})")
            continue
        respondidas = {_marca_de(c.get("body")) for c in comentarios}
        # conversa sem comentário: a própria issue é a mensagem (marca a{numero})
        if not comentarios:
            if f"a{numero}" not in respondidas:
                achados.append((issue, None))
            continue
        ultimo = comentarios[-1]
        if not _do_dono(ultimo.get("user")):
            continue  # a última fala é do robô: já respondida
        marca = f"c{ultimo.get('id')}"
        if marca in respondidas:
            continue
        achados.append((issue, ultimo))
    return achados


def _evento_falso(issue):
    """Grava um evento sintético para o novo-conversa, e devolve o caminho."""
    caminho = os.path.join(tempfile.mkdtemp(), "evento.json")
    # do_evento() exige action == "opened" para tratar como conversa nova — sem esse
    # campo o evento era "ignorado" e a primeira mensagem de uma conversa nunca saía.
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({
            "action": "opened",
            "issue": {
                "number": issue.get("number"),
                "body": issue.get("body") or "",
                "user": issue.get("user") or {},
            },
        }, f)
    return caminho


def processar(issue, comentario):
    """Roda o responder para uma conversa pendente, sem deixar o processo morrer."""
    numero = issue.get("number")
    os.environ.pop("REPROCESSAR_ISSUE", None)
    os.environ.pop("REPROCESSAR_COMMENT", None)
    if comentario:
        os.environ["REPROCESSAR_ISSUE"] = str(numero)
        os.environ["REPROCESSAR_COMMENT"] = str(comentario.get("id"))
        os.environ["GITHUB_EVENT_NAME"] = "varredura"
    else:
        os.environ["GITHUB_EVENT_NAME"] = "issues"
        os.environ["GITHUB_EVENT_PATH"] = _evento_falso(issue)
    try:
        responder.principal()
        return True
    except SystemExit:
        return True
    except Exception as e:
        log(f"conversa #{numero}: falhou ({type(e).__name__}: {str(e)[:120]})")
        return False


def main():
    if not C.GH_TOKEN:
        log("sem token de conversas — nada a fazer")
        return 1
    lista = pendentes()
    if not lista:
        log("nenhuma mensagem pendente")
        return 0
    log(f"{len(lista)} pendente(s); processando até {MAX_POR_RODADA}")
    feitas = 0
    for issue, comentario in lista[:MAX_POR_RODADA]:
        if processar(issue, comentario):
            feitas += 1
    log(f"respondidas {feitas} de {len(lista)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
