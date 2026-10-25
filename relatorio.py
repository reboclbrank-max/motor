#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Relatório semanal: todo domingo ela escreve para o dono um resumo do que
aprendeu, como se corrigiu e como estão os motores — e envia por e-mail."""
import comum as C


def _cauda(texto, linhas):
    itens = [l for l in (texto or "").splitlines() if l.strip()]
    return itens[-linhas:]


def montar_relatorio(curto=False):
    manual = C.ler_remoto("MEMORIA/manual.md", "")
    estudos = []
    if "## Saber destilado" in manual:
        estudos = [l for l in manual.splitlines() if l.strip().startswith("- ")][-12:]
    licoes = _cauda(C.ler_remoto(C.ARQ_LICOES, ""), 20)
    licoes_auto = [l for l in licoes if "(auto)" in l]
    diag = C.ler_diagnostico()
    motores = []
    for pid, est in (diag.get("provedores") or {}).items():
        if est.get("ok") is not False:
            motores.append(f"- {pid}: {est.get('ms_medio', est.get('ms_ultimo', '?'))} ms")
    if curto:
        partes = ["Bom dia, dono! ☀️", ""]
        primeira_aula = next((l for l in estudos if l.strip().startswith("-")), "")
        if primeira_aula:
            partes.append("📚 Último estudo: " + primeira_aula.strip().lstrip("- ")[:180])
        if licoes_auto:
            partes.append("🪞 Última autocorreção: " + licoes_auto[-1].strip().lstrip("- ")[:180])
        partes.append(f"⚡ Motores vivos agora: {len(motores)}")
        partes.append("")
        partes.append("— bom dia da Assistente Rebocl (e-mail dela, sozinho)")
        return "\n".join(partes)[:3000]
    partes = ["Saudações, dono! Relatório da semana:"]
    if estudos:
        partes.append("\n📚 Últimos estudos (caderno):")
        partes.extend(estudos[-8:])
    if licoes_auto:
        partes.append("\n🪞 Correções que eu mesma escrevi:")
        partes.extend(licoes_auto[-5:])
    if motores:
        partes.append("\n⚡ Motores vivos (tempo médio):")
        partes.extend(motores[:6])
    partes.append("\n— Assistente Rebocl (e-mail dela, escrito sozinho)")
    return "\n".join(partes)[:15000]


def enviar_relatorio(curto=False):
    corpo = montar_relatorio(curto=curto)
    assunto = ("Bom dia! Resumo rápido da Assistente Rebocl" if curto
               else "Relatório semanal da Assistente Rebocl")
    resultado = C.ferramenta_email(f"{assunto} | {corpo}")
    C.log("relatorio semanal: " + resultado[:100])
    return resultado


if __name__ == "__main__":
    print(enviar_relatorio())
