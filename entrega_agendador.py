#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quanto do relógio prometido a casa realmente recebe — medido, não suposto.

POR QUE EXISTE (04/11/2026): o canal de e-mail pedia um turno a cada 30 min (104 em 48 h) e
recebeu 12. O `batente` do `banco` pedia 24 por dia e recebeu 7. O agendador do GitHub entrega
uma fração dos crons curtos — e ninguém na casa sabia disso, porque ninguém comparava o que o
cron promete com o que o Actions entrega.

Este script faz a conta: para cada workflow com `cron:`, lê a agenda, conta as execuções
agendadas no período e diz a taxa. Uso:

    GITHUB_TOKEN=... python3 entrega_agendador.py --horas 48

Sem `--repos`, usa os repositórios públicos da casa. Não escreve nada em disco.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
REPOS_PADRAO = ("chat", "site", "motor", "rele", "midia")
DONO = "reboclbrank-max"


def conta_campo(campo, total):
    """Quantos valores do relógio um campo do cron aceita. None quando não é simples."""
    campo = (campo or "").strip()
    if not campo:
        return None
    if campo == "*":
        return total
    if re.fullmatch(r"\*/\d+", campo):
        passo = int(campo[2:])
        return len(range(0, total, passo)) if passo > 0 else None
    if "," in campo:
        partes = campo.split(",")
        if all(p.isdigit() for p in partes) and all(int(p) < total for p in partes):
            return len(set(partes))
        return None
    if re.fullmatch(r"\d+-\d+", campo):
        a, b = (int(x) for x in campo.split("-"))
        if a > b or b >= total:
            return None
        return b - a + 1
    if campo.isdigit() and int(campo) < total:
        return 1
    return None


def esperado_por_dia(cron):
    """Execuções por dia que um cron pede. Fração quando é semanal. None se não souber ler."""
    partes = (cron or "").split()
    if len(partes) != 5:
        return None
    minuto, hora, dia_mes, mes, dia_semana = partes
    m = conta_campo(minuto, 60)
    h = conta_campo(hora, 24)
    if not m or not h or dia_mes != "*" or mes != "*":
        return None
    por_dia = m * h
    if dia_semana != "*":
        dias = conta_campo(dia_semana, 7)
        if not dias:
            return None
        por_dia = por_dia * dias / 7.0
    return por_dia


def julgar(esperado, entregue, horas, total=None):
    """(taxa, veredito). Veredito é do mais grave para o menos grave.

    `total` (qualquer evento) importa: cron faminto com serviço alimentado por dispatch não é
    a mesma emergência que cron faminto e nada rodando. Medido em 04/11: `motor/chat` entrega
    2% do cron e recebe dezenas de dispatch por dia — o serviço está vivo, a promessa do cron é
    que é ficção. Sem essa coluna, o painel mandava consertar o que não estava quebrado.
    """
    previsto = esperado * horas / 24.0
    if previsto <= 0:
        return None, "sem cron"
    if entregue == 0 and previsto < 1:
        # Semanais/mensais: numa janela menor que uma execução esperada, zero execuções
        # não distingue "morto" de "ainda não chegou a vez". Chamar isso de morto foi
        # erro medido em 04/11/2026 (`relatorio-semanal` roda todo domingo e apareceu
        # como 0% morto numa janela de 48 h).
        return None, "sem amostra"
    taxa = entregue / previsto
    if entregue == 0:
        if total is not None and total > 0:
            return taxa, "cron mudo; serviço alimentado por dispatch"
        return taxa, "morto"
    if taxa < 0.5:
        if total is not None and total >= previsto:
            return taxa, "cron faminto; serviço coberto por dispatch"
        return taxa, "faminto"
    if taxa < 0.9:
        return taxa, "atrasado"
    return taxa, "no prazo"


def _get(caminho, token):
    req = urllib.request.Request(API + caminho)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "entrega-agendador")
    with urllib.request.urlopen(req, timeout=60) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def crons_do_workflow(repo, nome_arquivo, token):
    try:
        dados = _get(f"/repos/{DONO}/{repo}/contents/.github/workflows/{nome_arquivo}", token)
        import base64
        texto = base64.b64decode(dados["content"]).decode("utf-8", "replace")
        return re.findall(r"cron:\s*['\"]([^'\"]+)['\"]", texto)
    except Exception:
        return []


def conta_runs(repo, workflow_id, horas, token):
    """(agendadas, total) na janela. `total` inclui dispatch: distingue cron-ficção de serviço morto."""
    corte = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=horas)
    agendadas, total, pagina = 0, 0, 1
    while pagina <= 5:
        try:
            dados = _get(f"/repos/{DONO}/{repo}/actions/workflows/{workflow_id}/runs?per_page=100&page={pagina}", token)
        except urllib.error.HTTPError:
            return None
        runs = dados.get("workflow_runs") or []
        if not runs:
            break
        for run in runs:
            quando = datetime.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
            if quando >= corte:
                total += 1
                if run.get("event") == "schedule":
                    agendadas += 1
        mais_antigo = datetime.datetime.fromisoformat(runs[-1]["created_at"].replace("Z", "+00:00"))
        if mais_antigo < corte:
            break
        pagina += 1
    return agendadas, total


def medir(repos, horas, token):
    linhas = []
    for repo in repos:
        try:
            workflows = _get(f"/repos/{DONO}/{repo}/actions/workflows?per_page=100", token).get("workflows") or []
        except urllib.error.HTTPError:
            continue
        for wf in workflows:
            if wf.get("state") != "active":
                continue
            nome_arquivo = wf["path"].split("/")[-1]
            crons = crons_do_workflow(repo, nome_arquivo, token)
            if not crons:
                continue
            esperado = sum(e for e in (esperado_por_dia(c) for c in crons) if e)
            if not esperado:
                continue
            contagem = conta_runs(repo, wf["id"], horas, token)
            if contagem is None:
                continue
            entregue, total = contagem
            taxa, veredito = julgar(esperado, entregue, horas, total=total)
            linhas.append({"repo": repo, "workflow": wf["name"], "crons": crons,
                           "esperado": esperado, "entregue": entregue, "total": total,
                           "taxa": taxa, "veredito": veredito})
    return sorted(linhas, key=lambda x: (x["taxa"] if x["taxa"] is not None else 9))


def imprimir(linhas, horas):
    print(f"entrega do agendador nas últimas {horas} h")
    print(f"{'repo':<8}{'workflow':<34}{'pede/dia':>9}{'previsto':>9}{'agendado':>9}{'total':>7}{'taxa':>7}  veredito")
    for l in linhas:
        previsto = l["esperado"] * horas / 24.0
        taxa = "?" if l["taxa"] is None else f"{100 * l['taxa']:.0f}%"
        print(f"{l['repo']:<8}{l['workflow'][:33]:<34}{l['esperado']:>9.1f}{previsto:>9.1f}{l['entregue']:>9}{l.get('total', 0):>7}{taxa:>7}  {l['veredito']}")
    famintos = [l for l in linhas if l["veredito"] in ("faminto", "morto")]
    cobertos = [l for l in linhas if l["veredito"].endswith("por dispatch")]
    julgaveis = [l for l in linhas if l["veredito"] != "sem amostra"]
    print()
    print(f"{len(famintos)} de {len(julgaveis)} workflows agendados com janela suficiente recebem menos da metade do que pedem.")
    if cobertos:
        print(f"{len(cobertos)} desses são só ficção de cron: o serviço roda por dispatch e está alimentado.")
    sem_amostra = len(linhas) - len(julgaveis)
    if sem_amostra:
        print(f"sem amostra: {sem_amostra} (cron semanal/mensal numa janela curta) — fora da conta.")
    if famintos:
        print("Regra da casa: cron curto não é promessa. Quem precisa de cadência abaixo de 1 h "
              "depende de encadeamento ou de dispatch, não do relógio do GitHub.")
    return 0


def principal(argv=None):
    p = argparse.ArgumentParser(description="Mede a entrega real do agendador do GitHub")
    p.add_argument("--horas", type=int, default=48)
    p.add_argument("--repos", default=",".join(REPOS_PADRAO))
    p.add_argument("--json", action="store_true", help="saída em JSON em vez de tabela")
    args = p.parse_args(argv)
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        print("sem GITHUB_TOKEN: nada a medir")
        return 2
    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    linhas = medir(repos, args.horas, token)
    if args.json:
        print(json.dumps({"horas": args.horas, "linhas": linhas}, ensure_ascii=False, indent=1))
        return 0
    return imprimir(linhas, args.horas)


if __name__ == "__main__":
    sys.exit(principal())
