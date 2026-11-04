#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quanto tempo a mensagem do dono espera até a casa responder — medido, não sentido.

POR QUE EXISTE (04/11/2026): a casa descobriu que o cron entrega 2% do que pede. Faltava a
pergunta que importa para quem escreve: **quanto isso custa em espera?** A taxa do agendador é
meio, não fim. Este script lê os comentários das conversas do dono no repositório privado,
encontra cada par "mensagem do dono → primeira resposta da casa" e devolve mediana, média e pior
caso. Não lê conteúdo de mensagem para decidir nada e não imprime texto de conversa.

Uso:
    GITHUB_TOKEN=... python3 tempo_resposta.py --horas 72
"""
import argparse
import datetime
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
DONO = "reboclbrank-max"
REPO = "agente"
MARCA_RESPOSTA = "<!--resp:"


def _instante(texto):
    return datetime.datetime.fromisoformat(str(texto).replace("Z", "+00:00"))


def eh_resposta(comentario):
    """Resposta da casa é a que carrega a marca invisível; 🤖 sozinho não basta."""
    corpo = comentario.get("body") or ""
    return MARCA_RESPOSTA in corpo or corpo.lstrip().startswith("🤖")


def da_casa(corpo):
    """A fala saiu com o login do dono, mas foi a casa que escreveu?

    O PAT da automação é do próprio dono: `user.login` **não** separa os dois — foi assim que
    a primeira versão deste instrumento contou 21 "perguntas do dono" em 7 dias, sendo que
    várias eram boletins e turnos automáticos da casa, e a mediana de espera saiu errada.

    Este predicado é um SUBCONJUNTO de `varrer._do_robo` (que é a autoridade da casa); o
    contrato em `teste-tempo-resposta.py` garante que nada aqui fica mais frouxo que lá.
    """
    texto = (corpo or "").lstrip()
    if MARCA_RESPOSTA in texto or "<!--robo:" in texto:
        return True
    if texto.startswith(("🤖", "🌅 **Turno autônomo", "🌙 **Sonho da noite")):
        return True
    # Formato do notificador anterior à marca do robô (histórico preservado, não apagado).
    if texto.startswith(f"@{DONO} — aviso automático do assistente.\n\n") and texto.endswith(
            "Para receber também no Telegram (grátis), veja o passo a passo no COMECE-AQUI._"):
        return True
    return False


def pareamentos(comentarios):
    """[(segundos, numero, quando_perguntou, quando_respondeu)] por mensagem do dono.

    Regra: cada mensagem do dono espera a PRIMEIRA resposta **da mesma conversa** posterior a
    ela. Parear entre conversas foi erro medido (04/11/2026): a resposta da agenda no #116
    "respondia" uma pergunta feita no #17 e a espera saía 10× menor do que a real. Mensagem
    depois da última resposta da conversa fica de fora — ainda está esperando.
    """
    por_conversa = {}
    for c in comentarios:
        por_conversa.setdefault(c.get("_numero"), []).append(c)
    pares = []
    for numero, lista in por_conversa.items():
        eventos = sorted(lista, key=lambda c: _instante(c["created_at"]))
        perguntas = [_instante(c["created_at"]) for c in eventos
                     if (c.get("user") or {}).get("login") == DONO
                     and not eh_resposta(c) and not da_casa(c.get("body"))]
        respostas = [_instante(c["created_at"]) for c in eventos if eh_resposta(c)]
        for quando in perguntas:
            seguinte = next((r for r in respostas if r > quando), None)
            if seguinte is not None:
                pares.append(((seguinte - quando).total_seconds(), numero, quando, seguinte))
    return sorted(pares, key=lambda p: p[2])


def resumo(pares):
    """Mediana, média, pior caso e quantos pares — sem inventar quando não há dado."""
    segundos = sorted(p[0] for p in pares)
    if not segundos:
        return {"pares": 0, "mediana_s": None, "media_s": None, "pior_s": None,
                "dentro_de_10min": None}
    meio = len(segundos) // 2
    mediana = segundos[meio] if len(segundos) % 2 else (segundos[meio - 1] + segundos[meio]) / 2
    return {"pares": len(segundos), "mediana_s": mediana,
            "media_s": sum(segundos) / len(segundos), "pior_s": segundos[-1],
            "dentro_de_10min": sum(1 for s in segundos if s <= 600)}


def _get(caminho, token):
    req = urllib.request.Request(API + caminho)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "tempo-resposta")
    with urllib.request.urlopen(req, timeout=60) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def coletar(horas, token):
    corte = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=horas)
    issues = _get(f"/repos/{DONO}/{REPO}/issues?state=all&sort=updated&direction=desc&per_page=60", token)
    comentarios = []
    for issue in issues or []:
        if issue.get("pull_request"):
            continue
        try:
            if _instante(issue["updated_at"]) < corte:
                continue
        except (KeyError, ValueError):
            continue
        try:
            lista = _get(f"/repos/{DONO}/{REPO}/issues/{issue['number']}/comments?per_page=100", token)
        except Exception:
            continue
        for c in lista or []:
            # A janela é da MENSAGEM, não da conversa. Filtrar só por `updated_at` da issue
            # puxa comentário de uma semana atrás numa conversa que mexeu hoje — e o pior caso
            # de 52 h aparecia em qualquer janela, o que é o mesmo que não ter janela.
            try:
                if _instante(c.get("created_at")) < corte:
                    continue
            except (TypeError, ValueError):
                continue
            c["_numero"] = issue["number"]
            comentarios.append(c)
    return comentarios


def imprimir(s):
    if not s["pares"]:
        print("sem par pergunta/resposta na janela: nada a dizer sobre espera")
        return 0
    print(f"espera do dono até a primeira resposta ({s['pares']} pares)")
    print(f"  mediana: {s['mediana_s'] / 60:.0f} min")
    print(f"  média:   {s['media_s'] / 60:.0f} min")
    print(f"  pior:    {s['pior_s'] / 60:.0f} min")
    print(f"  em até 10 min: {s['dentro_de_10min']} de {s['pares']}")
    print()
    print("A taxa do agendador é meio, não fim: o que o dono sente é esta espera.")
    return 0


def principal(argv=None):
    p = argparse.ArgumentParser(description="Mede a espera entre a mensagem do dono e a resposta")
    p.add_argument("--horas", type=int, default=72)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        print("sem GITHUB_TOKEN: nada a medir")
        return 2
    s = resumo(pareamentos(coletar(args.horas, token)))
    if args.json:
        print(json.dumps({"horas": args.horas, **s}, ensure_ascii=False))
        return 0
    return imprimir(s)


if __name__ == "__main__":
    sys.exit(principal())
