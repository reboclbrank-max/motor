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
import time

import comum as C
import responder

def comentarios_verificados(numero):
    """Consulta todas as páginas; falha não é lista vazia."""
    pagina, todos = 1, []
    while True:
        dados = C.gh("GET", f"/repos/{C.REPO}/issues/{numero}/comments?per_page=100&page={pagina}")
        if not isinstance(dados, list):
            raise RuntimeError("comentarios_nao_observaveis")
        todos.extend(dados)
        if len(dados) < 100:
            return todos
        pagina += 1


def entrega_confirmada(numero, marca):
    alvo = "<!--resp:" + marca + "-->"
    for c in comentarios_verificados(numero):
        corpo = c.get("body") or ""
        autor = (c.get("user") or {}).get("login")
        if (autor in (C.DONO_GITHUB, "github-actions[bot]")
                and corpo.startswith(C.ASSINATURA) and alvo in corpo):
            return True
    return False


# Zero significa sem teto de quantidade; limite positivo é opção explícita de operação.
MAX_POR_RODADA = int(os.environ.get("MAX_POR_RODADA", "0"))
JANELA_HORAS = int(os.environ.get("JANELA_HORAS", "0"))
POR_PAGINA = max(1, min(100, int(os.environ.get("POR_PAGINA", "100"))))
# Handover antes do teto externo do job; não é cota diária de tarefas.
ORCAMENTO_RODADA_S = float(os.environ.get("ORCAMENTO_RODADA_S", "480"))


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


def revisao_historica():
    """Pendências anteriores à migração: revisão, nunca marcar como respondidas."""
    caminho = "MEMORIA/fila-revisao-historica.json"
    if not os.path.isfile(caminho):
        if os.environ.get("FILA_EXIGE_REVISAO_HISTORICA") == "1":
            raise RuntimeError("registro_de_revisao_historica_ausente")
        return set()
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    if not isinstance(dados, dict) or not isinstance(dados.get("mensagens"), list):
        raise RuntimeError("registro_de_revisao_historica_invalido")
    return {(m["issue"], m["marca"]) for m in dados["mensagens"]
            if m.get("estado") == "revisao_historica"}


def pendentes(limite_dias=None, diagnostico=None):
    """Lista mensagens individuais do DONO sem entrega confirmada.

    `diagnostico` (dict, opcional) recebe os números do que foi descartado e por quê — é o que
    permite dizer no log "15 pendentes, 12 eram do robô" em vez de fingir uma fila enorme.
    """
    if diagnostico is not None:
        diagnostico.update({"ignoradas_do_robo": 0, "fora_da_janela": 0, "nao_do_dono": 0,
                            "ja_respondidas": 0})
    horas = JANELA_HORAS if limite_dias is None else limite_dias
    desde = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=horas)
             if horas and horas > 0 else None)
    issues, pagina = [], 1
    while True:
        dados = C.gh("GET", f"/repos/{C.REPO}/issues?state=open&sort=updated&direction=desc"
                          f"&per_page={POR_PAGINA}&page={pagina}")
        if not isinstance(dados, list):
            raise RuntimeError("lista_de_conversas_invalida")
        issues.extend(dados)
        if len(dados) < POR_PAGINA:
            break
        pagina += 1
    achados = []
    revisao = revisao_historica()
    for issue in issues:
        if issue.get("pull_request"):
            continue
        try:
            quando = issue.get("updated_at", "")
            instante = datetime.datetime.fromisoformat(quando.replace("Z", "+00:00"))
            if desde is not None and instante < desde:
                if diagnostico is not None:
                    diagnostico["fora_da_janela"] += 1
                continue
        except (ValueError, AttributeError):
            pass
        if not _do_dono(issue.get("user")):
            continue
        numero = issue.get("number")
        try:
            comentarios = comentarios_verificados(numero)
        except Exception as e:
            log(f"conversa #{numero}: comentários ilegíveis ({type(e).__name__})")
            raise RuntimeError("comentarios_nao_observaveis") from e
        respondidas = {_marca_de(c.get("body")) for c in comentarios
                       if (c.get("user") or {}).get("login") in (C.DONO_GITHUB, "github-actions[bot]")
                       and (c.get("body") or "").startswith(C.ASSINATURA)}
        mensagens = [(f"a{numero}", issue, None)] + [
            (f"c{c.get('id')}", c, c) for c in comentarios]
        for marca, mensagem, comentario in mensagens:
            if not _do_dono(mensagem.get("user")):
                if diagnostico is not None:
                    diagnostico["nao_do_dono"] += 1
                continue
            if _do_robo(mensagem.get("body")):
                if diagnostico is not None:
                    diagnostico["ignoradas_do_robo"] += 1
                continue
            if comentario is None and comentarios and not (mensagem.get("body") or "").strip():
                continue  # abertura vazia não acrescenta pedido ao histórico já existente
            if marca in respondidas:
                if diagnostico is not None:
                    diagnostico["ja_respondidas"] += 1
                continue
            if (numero, marca) in revisao:
                if diagnostico is not None:
                    diagnostico["revisao_historica"] = diagnostico.get("revisao_historica", 0) + 1
                continue  # não executar ordens antigas, nem fingir que foram atendidas
            achados.append((issue, comentario))
    achados.sort(key=lambda par: ((par[1] or par[0]).get("created_at") or "",
                                  par[0].get("number", 0),
                                  (par[1] or {}).get("id", 0)))
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


def _processar(issue, comentario):
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
        marca = f"c{comentario.get('id')}" if comentario else f"a{numero}"
        if entrega_confirmada(numero, marca):
            return True
        try:
            codigo = responder.principal()
        except SystemExit as e:
            codigo = e.code
        if codigo not in (None, 0):
            return False
        return entrega_confirmada(numero, marca)
    except Exception as e:
        log(f"conversa #{numero}: falhou ({type(e).__name__}: {str(e)[:120]})")
        return False


def processar(issue, comentario):
    nomes = ("REPROCESSAR_ISSUE", "REPROCESSAR_COMMENT", "GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH")
    antes = {nome: os.environ.get(nome) for nome in nomes}
    try:
        return _processar(issue, comentario)
    finally:
        evento = os.environ.get("GITHUB_EVENT_PATH")
        if not comentario and evento and evento != antes["GITHUB_EVENT_PATH"]:
            try:
                os.unlink(evento)
                os.rmdir(os.path.dirname(evento))
            except OSError:
                pass
        for nome, valor in antes.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor


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
    try:
        lista = pendentes(diagnostico=diagnostico)
    except Exception as e:
        log(f"fila não observável: {type(e).__name__}")
        return 2
    if diagnostico.get("ignoradas_do_robo"):
        log(f"{diagnostico['ignoradas_do_robo']} conversa(s) só com fala da casa — não é pergunta")
    if diagnostico.get("revisao_historica"):
        log(f"{diagnostico['revisao_historica']} mensagem(ns) antiga(s) aguardam revisão, não execução")
    if not lista:
        log("nenhuma mensagem executável pendente do dono")
        return 0
    limite = MAX_POR_RODADA if MAX_POR_RODADA > 0 else len(lista)
    lote = lista[:limite]
    log(f"{len(lista)} pendente(s); lote disponível: {len(lote)}")
    feitas, tentadas = 0, 0
    inicio = time.monotonic()
    for issue, comentario in lote:
        if tentadas and time.monotonic() - inicio >= ORCAMENTO_RODADA_S:
            log("orçamento da execução atingido; pendências permanecem no canal")
            break
        tentadas += 1
        if processar_um(issue, comentario):
            feitas += 1
    restantes = len(lista) - feitas
    log(f"entregas confirmadas {feitas}; tentadas {tentadas}; pendentes {restantes}")
    if restantes > 0 and feitas > 0:
        if not disparar(f"faltam {restantes}"):
            return 2
    elif restantes > 0:
        log("sem progresso confirmado: não criar laço de execuções")
    return 1 if feitas < tentadas else 0



if __name__ == "__main__":
    raise SystemExit(main())
