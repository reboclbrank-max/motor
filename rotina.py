#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rotinas do Assistente Rebocl — ele acorda sozinho e te procura.

Manhã (09h de Brasília) e noite (20h de Brasília), direto no repositório:
  - confere se os sites estão no ar (site, itch.io, página do chat)
  - mostra o clima da sua cidade
  - resume o que rolou nas conversas (diário)
  - pede um comentário curto ao motor, quando disponível
"""
import os
import sys

import comum as C

LINKS_MONITORADOS = [
    ("Site oficial", "https://reboclbrank-max.github.io/site/"),
    ("Página do Prancheta (itch.io)", "https://rebocl-brank.itch.io/prancheta"),
    ("Página do Ceifalume (itch.io)", "https://rebocl-brank.itch.io/ceifalume"),
    ("Chat do assistente", "https://reboclbrank-max.github.io/chat/"),
]


def verificar_links():
    linhas = []
    for nome, url in LINKS_MONITORADOS:
        resultado = C.ferramenta_verificar(url)
        ok = "✓ no ar" in resultado
        linhas.append(f"- {'✅' if ok else '⚠️'} **{nome}** — {resultado.replace(url + ' → ', '')}")
    return linhas


def ultimas_do_diario(quantas=8):
    diario = C.ler_remoto(C.ARQ_DIARIO, "")
    linhas = [l for l in diario.splitlines() if l.strip().startswith("- **")]
    return linhas[-quantas:]


def montar_rotina(modo):
    agora = C.agora()
    try:
        from zoneinfo import ZoneInfo
        hora_local = agora.astimezone(ZoneInfo(C.FUSO_PADRAO))
    except Exception:
        hora_local = agora
    saudacao = "Bom dia" if modo == "manha" else "Boa noite"
    titulo = f"📋 Rotina da {'manhã' if modo == 'manha' else 'noite'} — {hora_local.strftime('%d/%m/%Y')}"

    partes = [""]

    partes.append("### 🌐 Tudo no ar?")
    partes += verificar_links()
    partes.append("")

    partes.append("### 🌤 Clima")
    try:
        partes.append(C.ferramenta_clima(""))
    except Exception as e:
        partes.append(f"(não consegui ver o clima agora: {str(e)[:80]})")
    partes.append("")

    try:
        melhorias = C.ler_remoto("MEMORIA/melhorias.md", "")
        itens = [l for l in melhorias.splitlines() if l.strip().startswith("- ")]
        if itens:
            partes.append(f"### 💡 Melhorias registradas: {len(itens)}")
            partes += itens[-3:]
            partes.append("")
    except Exception as e:
        C.log(f"melhorias na rotina: {e}")

    partes.append("### 🔔 Avisos e lembretes")
    try:
        partes.append(C.ferramenta_avisos(""))
    except Exception as e:
        partes.append(f"(não consegui ler os avisos agora: {str(e)[:80]})")
    partes.append("")

    partes.append("### 🗄 Banco de dados")
    try:
        partes.append(C.banco_resumo(completo=True))
    except Exception as e:
        partes.append(f"(não consegui ler o banco agora: {str(e)[:80]})")
    partes.append("")

    recentes = ultimas_do_diario()
    if recentes:
        partes.append("### 💬 O que rolou nas conversas")
        partes += recentes
        partes.append("")

    # comentário do motor, quando disponível
    try:
        contexto = "\n".join(partes)
        texto, motor, _erro = C.chamar_llm(
            [{"role": "user", "content": (
                f"Você é o Assistente Rebocl. Escreva a abertura e o fechamento de uma rotina "
                f"{'de manhã' if modo == 'manha' else 'de noite'} para o dono, em no máximo 4 linhas, "
                f"com base nestes dados reais (não invente nada):\n\n{contexto[:4000]}\n\n"
                "Comece cumprimentando e resumindo em 1-2 frases; termine com UMA sugestão prática para hoje "
                "ligada aos jogos e à empresa (ex.: testar o Prancheta no celular, responder feedback no itch.io, "
                "postar uma captura, ajustar algo do jogo). NUNCA fale de 'sprint', 'backlog' ou papo corporativo "
                "genérico. Escreva apenas o texto, sem repetir os dados.")}],
            "Você é o Assistente Rebocl, a IA própria da Rebocl Brank. Português do Brasil, direto e simpático.")
        if texto:
            partes.insert(1, texto.strip())
            partes.insert(2, "")
    except Exception as e:
        C.log(f"motor da rotina: {e}")
    if not partes[1]:
        partes[1] = f"{saudacao}, dono! ☕" if modo == "manha" else f"{saudacao}, dono! 🌙"

    partes.append("---")
    partes.append("_Responda nesta conversa para falar comigo — ou use os comandos: "
                  "`pesquisar:`, `clima:`, `imagem:`, `lembrete:`, `avise quando:`, `avisos:` · `/ajuda` para tudo._")
    return titulo, "\n".join(partes)


def principal():
    # rede de segurança: se o vigia estiver em modo econômico, os avisos saem aqui
    try:
        resumo_avisos = C.checar_avisos_rapido()
        if resumo_avisos.get("disparados") or resumo_avisos.get("lembretes"):
            C.log(f"rotina: avisos disparados antes da rotina: {resumo_avisos}")
    except Exception as e:
        C.log(f"rotina: checagem de avisos falhou ({e})")
    modo = (os.environ.get("ROTINA") or "").strip().lower()
    if modo not in ("manha", "noite"):
        modo = "manha" if C.agora().hour < 15 else "noite"
    titulo, corpo = montar_rotina(modo)
    C.log(f"rotina {modo}:\n{titulo}")
    try:
        issue = C.gh("POST", f"/repos/{C.REPO}/issues",
                     {"title": titulo, "body": corpo, "labels": ["rotina"]})
        C.log("conversa criada:", issue.get("number"), issue.get("html_url"))
    except Exception as e:
        C.log(f"falha ao criar a conversa da rotina (talvez falte a etiqueta 'rotina'): {e}")
        issue = C.gh("POST", f"/repos/{C.REPO}/issues", {"title": titulo, "body": corpo})
        C.log("criada sem etiqueta:", issue.get("number"))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
