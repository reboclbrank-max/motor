#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressão da ponte web: comentário da emergência do navegador é resposta,
não novo pedido ao trabalhador. Não usa rede, segredo ou GitHub."""
import os

import responder

ok = 0
falhas = 0
MARCA = "<!-- rebocl-emergencia -->"
DONO = responder.C.DONO_GITHUB


def testa(nome, fn):
    global ok, falhas
    try:
        fn()
        ok += 1
        print("✓ " + nome)
    except Exception as exc:
        falhas += 1
        print("✗ " + nome + " — " + str(exc))


def com_evento(nome, evento, fn):
    antigo_nome = os.environ.get("GITHUB_EVENT_NAME")
    antiga_leitura = responder.ler_evento
    try:
        os.environ["GITHUB_EVENT_NAME"] = nome
        responder.ler_evento = lambda: evento
        fn()
    finally:
        responder.ler_evento = antiga_leitura
        if antigo_nome is None:
            os.environ.pop("GITHUB_EVENT_NAME", None)
        else:
            os.environ["GITHUB_EVENT_NAME"] = antigo_nome


def com_reprocessamento(dados, fn):
    antigo_issue = os.environ.get("REPROCESSAR_ISSUE")
    antigo_comentario = os.environ.get("REPROCESSAR_COMMENT")
    antiga_gh = responder.C.gh
    try:
        os.environ["REPROCESSAR_ISSUE"] = "44"
        os.environ["REPROCESSAR_COMMENT"] = "93"
        responder.C.gh = lambda metodo, caminho: dados
        fn()
    finally:
        responder.C.gh = antiga_gh
        if antigo_issue is None:
            os.environ.pop("REPROCESSAR_ISSUE", None)
        else:
            os.environ["REPROCESSAR_ISSUE"] = antigo_issue
        if antigo_comentario is None:
            os.environ.pop("REPROCESSAR_COMMENT", None)
        else:
            os.environ["REPROCESSAR_COMMENT"] = antigo_comentario


def comentario(identificador, corpo, login=DONO):
    return {
        "action": "created",
        "issue": {"number": 42},
        "comment": {"id": identificador, "body": corpo,
                    "user": {"login": login, "type": "User"}},
    }


def teste_comentario_marcado_do_dono_ignorado():
    com_evento("issue_comment", comentario(91, MARCA + "\nresposta local"),
               lambda: assert_nulo(responder.do_evento()))


def teste_marcador_de_outro_autor_nao_suprime_pergunta():
    evento = comentario(92, "pergunta normal\n" + MARCA, login="outra-pessoa")
    def verifica():
        dado = responder.do_evento()
        assert dado and dado["texto"] == evento["comment"]["body"] and dado["marca"] == "c92"
    com_evento("issue_comment", evento, verifica)


def teste_marcador_no_meio_do_dono_nao_suprime_pergunta():
    evento = comentario(93, "pergunta normal\n" + MARCA)
    def verifica():
        dado = responder.do_evento()
        assert dado and dado["texto"] == evento["comment"]["body"] and dado["marca"] == "c93"
    com_evento("issue_comment", evento, verifica)


def teste_reprocessamento_marcado_do_dono_ignorado():
    dados = {"body": MARCA + "\nresposta local", "user": {"login": DONO}}
    com_reprocessamento(dados, lambda: assert_nulo(responder.do_evento()))


def teste_comentario_normal_preservado():
    evento = comentario(94, "pergunta normal")
    def verifica():
        dado = responder.do_evento()
        assert dado and dado["texto"] == "pergunta normal" and dado["marca"] == "c94"
    com_evento("issue_comment", evento, verifica)


def teste_abertura_preservada():
    evento = {"action": "opened", "issue": {"number": 43, "body": "primeira pergunta"}}
    def verifica():
        dado = responder.do_evento()
        assert dado and dado["texto"] == "primeira pergunta" and dado["marca"] == "a43"
    com_evento("issues", evento, verifica)


def assert_nulo(valor):
    assert valor is None


testa("comentário marcado do dono não entra na fila", teste_comentario_marcado_do_dono_ignorado)
testa("marcador de outro autor não suprime pergunta", teste_marcador_de_outro_autor_nao_suprime_pergunta)
testa("marcador no meio do texto do dono não suprime pergunta", teste_marcador_no_meio_do_dono_nao_suprime_pergunta)
testa("reprocessamento marcado do dono não entra na fila", teste_reprocessamento_marcado_do_dono_ignorado)
testa("comentário normal continua entrando na fila", teste_comentario_normal_preservado)
testa("abertura normal continua entrando na fila", teste_abertura_preservada)
print(f"{ok}/{ok + falhas} testes da ponte de emergência passaram")
raise SystemExit(1 if falhas else 0)
