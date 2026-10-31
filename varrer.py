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
# JANELA: uma mensagem do dono sem resposta não pode envelhecer em silêncio. Era 72 h com 30
# conversas por leitura; com 100 por página e uma semana de janela, o que ficou para trás é
# pego na rodada seguinte em vez de desaparecer.
JANELA_HORAS = int(os.environ.get("JANELA_HORAS", "168"))
POR_PAGINA = int(os.environ.get("POR_PAGINA", "100"))
# Cadeia: quando a rodada responde e SOBRA pendente, o próprio varredor acorda o chat de novo.
# Sem isso, 15 pendentes com teto de 3 por rodada esperavam o próximo cron (que na prática roda
# algumas vezes por dia, não a cada 10 min): resposta em horas em vez de minutos.
MAX_CADEIA = int(os.environ.get("MAX_CADEIA", "8"))


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


def _do_robo(corpo):
    """A fala é da própria casa (e não do dono), mesmo saindo com o login do dono?

    Medido em 31/10/2026: a automação publica com o MESMO login do dono, então
    `_do_dono(usuario)` sozinho respondia "sim" para boletins e pilotos automáticos — e a
    varredura respondia ao robô. Duas provas, nesta ordem:
      1. a marca invisível (`<!--resp:...-->` nas respostas, `<!--robo:...-->` nas demais
         falas da casa, posta por `comum.comentar`);
      2. o cabeçalho da casa (`🤖 **Assistente Rebocl**`, `🤖 **Piloto automático**`, …) para
         o que foi publicado antes da marca existir — sem apagar histórico.
    """
    texto = (corpo or "").lstrip()
    if "<!--resp:" in texto or C.MARCA_DO_ROBO in texto:
        return True
    return texto.startswith("🤖") or texto.startswith(C.ASSINATURA)


def _do_dono(usuario):
    return (usuario or {}).get("login") == C.DONO_GITHUB and (usuario or {}).get("type") != "Bot"


def pendentes(limite_dias=None, diagnostico=None):
    """Lista (issue, comentario|None) cuja última mensagem do DONO não foi respondida.

    `diagnostico` (dict, opcional) recebe os números do que foi descartado e por quê — é o que
    permite dizer no log "15 pendentes, 12 eram do robô" em vez de fingir uma fila enorme.
    """
    if diagnostico is not None:
        diagnostico.update({"ignoradas_do_robo": 0, "fora_da_janela": 0, "nao_do_dono": 0,
                            "ja_respondidas": 0})
    # utcnow (naive) para comparar com o updated_at da API, que é naive depois do slice
    desde = datetime.datetime.utcnow() - datetime.timedelta(
        hours=JANELA_HORAS if limite_dias is None else limite_dias)
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?state=open&sort=updated&direction=desc"
                             f"&per_page={POR_PAGINA}") or []
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
                if diagnostico is not None:
                    diagnostico["fora_da_janela"] += 1
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
        # Fala da casa (marca ou cabeçalho) NÃO é pergunta pendente. Desde 31/10/2026 isto vem
        # antes de qualquer outra regra: era aqui que o robô se respondia.
        if _do_robo(ultimo.get("body")):
            if diagnostico is not None:
                diagnostico["ignoradas_do_robo"] += 1
            continue
        if not _do_dono(ultimo.get("user")):
            if diagnostico is not None:
                diagnostico["nao_do_dono"] += 1
            continue  # a última fala é de outra pessoa: não é pergunta do dono
        marca = f"c{ultimo.get('id')}"
        if marca in respondidas:
            if diagnostico is not None:
                diagnostico["ja_respondidas"] += 1
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


def acordar_de_novo(motivo="fila"):
    """Pede ao GitHub outra rodada do chat. Devolve True se o pedido saiu.

    A cadeia é o que faz a fila DRENAR: cada rodada responde até MAX_POR_RODADA, então uma fila
    de 15 com teto 3 levava horas (o cron de 10 min na prática roda poucas vezes por dia). Aqui,
    terminada a rodada com progresso e ainda com gente esperando, a próxima já entra na fila.
    TRAVA: só encadeia quando ESTA rodada respondeu alguém. Sem progresso, sem cadeia — foi
    assim que se evita laço infinito quando um motor está fora do ar.
    """
    try:
        C.gh("POST", f"/repos/{C.REPO_ROBO}/actions/workflows/chat.yml/dispatches", {"ref": "main"})
        log(f"cadeia: outra rodada pedida ({motivo})")
        return True
    except Exception as e:  # noqa: BLE001
        log(f"cadeia: não consegui pedir outra rodada ({type(e).__name__}: {str(e)[:120]})")
        return False


def main(processar_um=None, disparar=None):
    if not C.GH_TOKEN:
        log("sem token de conversas — nada a fazer")
        return 1
    processar_um = processar_um or processar
    disparar = disparar or acordar_de_novo
    diagnostico = {}
    lista = pendentes(diagnostico=diagnostico)
    if diagnostico.get("ignoradas_do_robo"):
        log(f"{diagnostico['ignoradas_do_robo']} conversa(s) só com fala da casa — não é pergunta")
    if not lista:
        log("nenhuma mensagem pendente do dono")
        return 0
    log(f"{len(lista)} pendente(s) do dono; processando até {MAX_POR_RODADA}")
    feitas = 0
    for issue, comentario in lista[:MAX_POR_RODADA]:
        if processar_um(issue, comentario):
            feitas += 1
    restantes = len(lista) - feitas
    log(f"respondidas {feitas} de {len(lista)}")
    if restantes > 0 and feitas > 0:
        disparar(f"faltam {restantes}")
    elif restantes > 0:
        log(f"{restantes} seguem na fila: nenhuma resposta saiu nesta rodada, cadeia NÃO pedida")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
