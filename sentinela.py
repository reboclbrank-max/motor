#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vigia do Assistente Rebocl — roda de hora em hora e cuida da saúde do sistema.

O que faz:
  1. Testa os motores (sem atrapalhar os lentos) e os sites públicos.
  2. Procura mensagens SEM RESPOSTA e dispara o reprocessamento delas.
  3. Procura execuções FALHADAS do chat e manda rodar de novo (auto-cura).
  4. Confere os avisos e lembretes do dono e entrega (v3.7).
  5. Mantém o histórico em MEMORIA/saude.md e avisa a você na conversa "🩺 Saúde"
     apenas quando o estado MUDA (ok → problema, problema → ok).
"""
import os
import sys

import banco
import comum as C

TITULO_SAUDE = "🩺 Saúde do assistente"
MAX_REPROCESSAR = 4
MAX_RERUN = 3
TENTATIVAS_POR_ITEM = 2
LIMITE_IDADE_MIN = 20          # espera 20 min antes de considerar "sem resposta"
LIMITE_IDADE_MAX_H = 24        # ignora mensagens antigas demais

SITES = [
    ("Site oficial", "https://reboclbrank-max.github.io/site/"),
    ("Prancheta (itch.io)", "https://rebocl-brank.itch.io/prancheta"),
    ("Ceifalume (itch.io)", "https://rebocl-brank.itch.io/ceifalume"),
    ("Chat", "https://reboclbrank-max.github.io/chat/"),
]


def testar_motores():
    """Testa os motores, pulando os muito lentos (llm7 fica de reserva)."""
    return C.testar_provedores(pular=("llm7",))


def testar_sites():
    falhas = []
    for nome, url in SITES:
        resultado = C.ferramenta_verificar(url)
        if "✓ no ar" not in resultado:
            falhas.append(f"{nome}: {resultado.split('→ ')[-1]}")
    return falhas


def achar_conversa_saude():
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?state=all&labels=saude&per_page=5") or []
        for i in issues:
            if i.get("title") == TITULO_SAUDE:
                return i["number"]
    except Exception as e:
        C.log(f"saúde: procura falhou ({e})")
    # criar se não existir
    try:
        C.gh("POST", f"/repos/{C.REPO}/labels",
             {"name": "saude", "color": "3ddc84", "description": "Avisos do vigia do assistente"})
    except Exception:
        pass
    try:
        issue = C.gh("POST", f"/repos/{C.REPO}/issues", {
            "title": TITULO_SAUDE,
            "body": ("Esta conversa recebe os avisos automáticos do **vigia** (roda de hora em hora).\n\n"
                     "Ele só escreve aqui quando algo **muda de estado** — problema ou recuperação. "
                     "Silêncio = tudo em ordem. 🌿"),
            "labels": ["saude"],
        })
        return issue.get("number")
    except Exception as e:
        C.log(f"saúde: criação falhou ({e})")
        return None


ARQ_MELHORIAS = "MEMORIA/melhorias.md"


def registrar_melhoria(linha):
    """Anota no diário de melhorias (sem repetir o mesmo aviso). Fica para o dono/agente melhorar."""
    try:
        atual = C.ler_remoto(ARQ_MELHORIAS, "# Diário de melhorias\n\n> O vigia anota aqui o que precisa de conserto. Nada é apagado.\n")
        if linha in atual:
            return False
        novas = (atual.rstrip() + "\n- " + linha).splitlines()
        texto = "\n".join(novas[:4] + novas[-120:]) + "\n" if len(novas) > 124 else "\n".join(novas) + "\n"
        C.escrever_remoto(ARQ_MELHORIAS, texto, f"melhorias: {linha[:50]}")
        return True
    except Exception as e:
        C.log(f"melhorias: não consegui anotar ({e})")
        return False


def perguntas_sem_resposta(diag):
    """Encontra comentários do dono sem resposta do bot (mais velhos que 20 min)."""
    pendentes = []
    tentativas = diag.setdefault("reprocessados", {})
    agora = C.agora()
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?state=open&per_page=25&sort=updated&direction=desc") or []
    except Exception as e:
        C.log(f"pendentes: listagem falhou ({e})")
        return pendentes
    for issue in issues:
        numero = issue["number"]
        try:
            comentarios = C.gh("GET", f"/repos/{C.REPO}/issues/{numero}/comments?per_page=100") or []
        except Exception:
            continue
        for comentario in comentarios:
            corpo = (comentario.get("body") or "").strip()
            if not corpo:
                continue
            login = (comentario.get("user") or {}).get("login", "")
            if login == "github-actions[bot]":
                continue
            criado = C.datetime.fromisoformat(comentario["created_at"].replace("Z", "+00:00"))
            idade_min = (agora - criado).total_seconds() / 60
            if idade_min < LIMITE_IDADE_MIN or idade_min > LIMITE_IDADE_MAX_H * 60:
                continue
            # alguma resposta do bot depois desta mensagem?
            respondeu = any(
                (c.get("user") or {}).get("login") == "github-actions[bot]"
                and c.get("created_at", "") > comentario.get("created_at", "")
                for c in comentarios
            )
            if respondeu:
                continue
            cid = str(comentario["id"])
            if tentativas.get(cid, 0) >= TENTATIVAS_POR_ITEM:
                continue
            pendentes.append({"numero": numero, "comentario_id": cid})
    return pendentes


def disparar_reprocessamento(item, diag):
    """Pede ao robô outra rodada de varredura.

    DEFEITO MEDIDO (31/10/2026): este dispatch mirava `C.REPO` (o repositório das CONVERSAS),
    onde o chat.yml não existe — e mandava `inputs` que o chat.yml não declara, o que devolve
    422 e não roda nada. Dois erros somados: o "reprocessamento" do sentinela nunca aconteceu.
    Agora vai para o repositório do CÓDIGO, sem inputs: a varredura pega a fila inteira
    (inclusive o item que o sentinela viu).
    """
    try:
        C.gh("POST", f"/repos/{C.REPO_ROBO}/actions/workflows/chat.yml/dispatches", {"ref": "main"})
        diag.setdefault("reprocessados", {})[item["comentario_id"]] = \
            diag["reprocessados"].get(item["comentario_id"], 0) + 1
        C.log(f"reprocessamento disparado: conversa #{item['numero']} comentário {item['comentario_id']}")
        return True
    except Exception as e:
        C.log(f"reprocessamento falhou: {e}")
        return False


def reruns_de_falhas(diag):
    """Reexecuta runs do chat que falharam recentemente (auto-cura)."""
    feitos = 0
    tentativas = diag.setdefault("reruns", {})
    try:
        runs = C.gh("GET", f"/repos/{C.REPO}/actions/runs?per_page=20") or {}
    except Exception as e:
        C.log(f"runs: listagem falhou ({e})")
        return 0
    agora = C.agora()
    for run in runs.get("workflow_runs", []):
        if feitos >= MAX_RERUN:
            break
        # só reexecuta FALHAS reais (cancelado costuma ser intencional; reexecutar
        # run antigo pode responder de novo perguntas já respondidas antes da era das marcas)
        if run.get("conclusion") != "failure":
            continue
        if "Assistente Rebocl (chat)" not in (run.get("name") or ""):
            continue
        criado = C.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if (agora - criado).total_seconds() > 60 * 60:
            continue
        rid = str(run["id"])
        if tentativas.get(rid, 0) >= 1:
            continue
        try:
            C.gh("POST", f"/repos/{C.REPO}/actions/runs/{rid}/rerun", {})
            tentativas[rid] = tentativas.get(rid, 0) + 1
            feitos += 1
            C.log(f"rerun disparado para o run {rid}")
        except Exception as e:
            C.log(f"rerun falhou ({rid}): {e}")
            tentativas[rid] = 99
    # limpeza de registros antigos
    diag["reruns"] = {k: v for k, v in tentativas.items() if v < 99} if len(tentativas) > 500 else tentativas
    return feitos


def runs_no_mes():
    """Quantas execuções o repositório já teve neste mês (a conta grátis dá 2.000 min/mês)."""
    total = 0
    try:
        for pagina in (1, 2):
            d = C.gh("GET", f"/repos/{C.REPO}/actions/runs?per_page=100&page={pagina}") or {}
            lista = d.get("workflow_runs", [])
            if not lista:
                break
            mes = C.agora().strftime("%Y-%m")
            total += sum(1 for r in lista if str(r.get("created_at", "")).startswith(mes))
    except Exception as e:
        C.log(f"orçamento: não consegui contar ({e})")
        return None
    return total


def principal():
    diag = C.ler_diagnostico()

    # guarda de orçamento: se o mês estiver pesado, o vigia espaça sozinho (1x a cada 3 h / 6 h)
    usados = runs_no_mes()
    if usados is not None:
        hora = C.agora().hour
        if usados > 1850 and hora % 6 != 0:
            C.log(f"orçamento: {usados} execuções no mês — vigia em modo econômico (1x/6h); pulando agora")
            return 0
        if usados > 1650 and hora % 3 != 0:
            C.log(f"orçamento: {usados} execuções no mês — vigia em modo econômico (1x/3h); pulando agora")
            return 0
        if usados > 1650:
            C.log(f"orçamento: {usados} execuções no mês — modo econômico ativo")
    linhas_motores = testar_motores()
    motores_ok = any(l.startswith("✅") for l in linhas_motores)
    falhas_sites = testar_sites()

    # motor que caiu vira anotação no diário de melhorias (uma vez por dia por motor)
    try:
        prov_est = C.ler_diagnostico().get("provedores", {})
        for p in C.montar_provedores():
            if prov_est.get(p["id"], {}).get("ok") is False:
                registrar_melhoria(f"({C.agora().strftime('%d/%m')}) motor fora do ar: {p['nome']}")
    except Exception as e:
        C.log(f"melhorias (motores): {e}")

    # banco de dados: mantém atualizado de hora em hora (clima, cotações, sites, números)
    banco_ok = True
    try:
        banco.atualizar(origem="vigia")
    except Exception as e:
        banco_ok = False
        C.log(f"banco: falhou na atualização do vigia ({e})")

    # avisos e lembretes: confere tudo e entrega ao dono (v3.7)
    avisos_disparados, lembretes_avisados, avisos_erros = [], [], []
    try:
        resultado_avisos = C.checar_avisos()
        avisos_disparados = resultado_avisos.get("disparados", [])
        avisos_erros = resultado_avisos.get("erros", [])
        lembretes_avisados = C.checar_lembretes()
        C.limpar_travas_antigas()
    except Exception as e:
        C.log(f"avisos: falha na checagem do vigia ({e})")
    for erro_aviso in avisos_erros:
        registrar_melhoria(f"({C.agora().strftime('%d/%m')}) aviso com erro: {erro_aviso}")

    # backup diário da memória (de madrugada) e panorama semanal (domingo)
    extra = []
    hora = C.agora().hour
    dia_semana = C.agora().isoweekday()   # 7 = domingo
    if hora == 4:
        if C.backup_memoria():
            extra.append("backup diário ok")
    if dia_semana == 7 and hora >= 12:
        try:
            C.resumir_memoria()
            extra.append("panorama semanal atualizado")
        except Exception as e:
            C.log(f"resumo semanal falhou: {e}")

    # pendências
    pendentes = perguntas_sem_resposta(diag)
    reprocessados = 0
    for item in pendentes[:MAX_REPROCESSAR]:
        if disparar_reprocessamento(item, diag):
            reprocessados += 1

    reruns = reruns_de_falhas(diag)

    # estado
    problemas = []
    if not motores_ok:
        problemas.append("nenhum motor respondendo")
        registrar_melhoria(f"({C.agora().strftime('%d/%m %H:%M')}) nenhum motor respondendo — conferir os motores gratuitos")
    problemas += [f"sites: {f}" for f in falhas_sites]
    for f in falhas_sites:
        registrar_melhoria(f"({C.agora().strftime('%d/%m %H:%M')}) site fora do ar: {f}")
    if not banco_ok:
        problemas.append("banco de dados não atualizou")
        registrar_melhoria(f"({C.agora().strftime('%d/%m %H:%M')}) o banco de dados falhou ao atualizar")
    if avisos_erros:
        problemas.append(f"{len(avisos_erros)} aviso(s) com erro de checagem")
    if pendentes:
        problemas.append(f"{len(pendentes)} mensagem(ns) sem resposta")
        registrar_melhoria(f"({C.agora().strftime('%d/%m %H:%M')}) {len(pendentes)} mensagem(ns) ficaram sem resposta — reprocessando")
    novo_estado = "falha" if problemas else "ok"
    anterior = diag.get("saude", {})
    mudou = anterior.get("estado") != novo_estado
    if mudou:
        diag["saude"] = {"estado": novo_estado, "desde": C.agora().strftime("%d/%m/%Y %H:%M")}

    # histórico
    resumo = f"{C.agora().strftime('%d/%m %H:%M')} — motores: {'ok' if motores_ok else 'FALHA'} · " \
             f"sites: {'ok' if not falhas_sites else 'FALHA (' + '; '.join(falhas_sites) + ')'} · " \
             f"banco: {'ok' if banco_ok else 'FALHA'} · " \
             f"pendentes: {len(pendentes)} · reprocessados: {reprocessados} · reruns: {reruns} · " \
             f"avisos: {len(avisos_disparados)} · lembretes: {len(lembretes_avisados)}" \
             + (f" · execuções no mês: {usados}" if usados is not None else "") \
             + ((" · " + "; ".join(extra)) if extra else "")
    try:
        atual = C.ler_remoto("MEMORIA/saude.md", "# Histórico de saúde do assistente\n")
        linhas = atual.splitlines()
        novas = (atual.rstrip() + "\n- " + resumo).splitlines()[-70:]
        C.escrever_remoto("MEMORIA/saude.md", "\n".join(novas) + "\n", "saude: histórico atualizado")
    except Exception as e:
        C.log(f"saude.md: {e}")

    # aviso só quando muda
    cid = None
    if mudou:
        cid = achar_conversa_saude()
    if cid:
        if novo_estado == "falha":
            detalhe = "\n".join("- " + p for p in problemas)
            linhas_m = "\n".join("- " + l for l in linhas_motores)
            C.comentar(cid, f"{C.ASSINATURA}\n\n🚨 **Encontrei um problema (e já estou tentando resolver):**\n\n"
                            f"{detalhe}\n\n**Motores:**\n{linhas_m}\n\n"
                            f"_Reprocessamentos disparados: {reprocessados} · reexecuções: {reruns}_")
        else:
            C.comentar(cid, f"{C.ASSINATURA}\n\n💚 **Tudo em ordem de novo!** Motores e sites respondendo.\n\n"
                            f"_Mensagens reprocessadas: {reprocessados} · reexecuções: {reruns}_")

    diag["ultima_verificacao"] = C.agora().isoformat()
    C.salvar_diagnostico(diag)
    C.log(f"vigia: estado={novo_estado} | exigências: motores_ok={motores_ok} sites_ok={not falhas_sites} "
          f"pendentes={len(pendentes)} reproc={reprocessados} reruns={reruns}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
