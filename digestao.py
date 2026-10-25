#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Digestão: de 6 em 6 horas ela relê as lições do dia, escolhe as 3 mais
valiosas e as grava no MANUAL (que entra em TODA resposta) — o estudo vira
comportamento permanente, não só papel guardado. Com teto de 36 itens para o
system prompt nunca inflar. E poda cadernos com mais de 14 dias."""
import re

import comum as C
import estudo as E

SECAO = "## Saber destilado dos estudos (auto, o melhor do dia)"
TETO = 36


def _secao_atual(manual):
    if SECAO not in manual:
        return [], manual.rstrip("\n")
    idx = manual.find(SECAO)
    cabeca = manual[:idx].rstrip("\n")
    itens = [l for l in manual[idx:].splitlines() if l.strip().startswith("- ")]
    return itens, cabeca


def digerir():
    texto = C.ler_remoto(E.arq_estudo_hoje(), "")
    licoes = [l.strip()[2:].strip() for l in texto.splitlines() if l.strip().startswith("- ")]
    if len(licoes) < 12:
        return f"Digestão espera: só {len(licoes)} lições no caderno de hoje."
    prompt = (
        "Abaixo estão lições que aprendi hoje estudando na internet.\n\n- " + "\n- ".join(licoes[:80])
        + "\n\nEscolha EXATAMENTE as 3 mais valiosas para virarem REGRA PERMANENTE do meu "
          "trabalho (empresa solo de jogos de terror, divulgação em 6 canais, PC fraco). "
          "Responda só a lista com 3 linhas '- '."
    )
    texto_esc, motor, _erro = C.chamar_llm([{"role": "user", "content": prompt}])
    if not texto_esc:
        return "Digestão: nenhum motor respondeu; tento no próximo ciclo."
    novas = [C._limpar_pensar(texto_esc).splitlines()[i].strip()[2:].strip()[:180]
             for i in range(len(C._limpar_pensar(texto_esc).splitlines()))
             if C._limpar_pensar(texto_esc).splitlines()[i].strip().startswith(("-", "*"))][:3]
    if not novas:
        return "Digestão: a escolha veio fora do formato; tento no próximo ciclo."
    manual = C.ler("MEMORIA/manual.md")
    itens, cabeca = _secao_atual(manual)
    itens = (itens + [f"- (estudo {C.agora().strftime('%d/%m')}) {n}" for n in novas])[-TETO:]
    novo_manual = cabeca + "\n\n" + SECAO + "\n" + "\n".join(itens) + "\n"
    if novo_manual != manual:
        C.escrever_remoto("MEMORIA/manual.md", novo_manual, "digestao: o melhor dos estudos vira cerebro permanente")
    return f"🧠 Digestão feita: {len(novas)} lições do dia viraram cérebro permanente (seção com {len(itens)}/{TETO})."


def podar(dias=14):
    from datetime import timedelta
    lista = C.gh("GET", f"/repos/{C.REPO}/contents/MEMORIA") or []
    corte = (C.agora() - timedelta(days=dias)).strftime("%d-%m-%Y")
    podados = 0
    for item in lista:
        nome = item.get("name", "")
        m = re.match(r"estudos-(\d{2})-(\d{2})-(\d{4})\.md$", nome)
        if not m or m.group(3) + m.group(2) + m.group(1) >= corte[6:] + corte[3:5] + corte[:2]:
            continue
        try:
            C.gh("DELETE", f"/repos/{C.REPO}/contents/MEMORIA/{nome}",
                 {"sha": item["sha"], "message": f"poda: caderno {nome} passou de {dias} dias"})
            podados += 1
        except Exception as e:
            C.log(f"poda: {nome} falhou ({str(e)[:60]})")
    return f"🧹 Poda: {podados} caderno(s) antigo(s) removido(s) (retenção {dias} dias)."


if __name__ == "__main__":
    print(digerir())
    print(podar())
