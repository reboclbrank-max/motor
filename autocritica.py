#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autocrítica diária: ela lê o próprio diário e os feedbacks "ruim" do dono
e escreve (no máximo) 3 lições de correção de comportamento — assinadas (auto).
Assim ela se melhora sozinha, todos os dias, sem ninguém mandar."""
import json
import re

import comum as C


def autocriticar():
    diario = C.ler_remoto(C.ARQ_DIARIO, "")
    ultimas = [l for l in diario.splitlines() if l.strip().startswith("-")][-25:]
    try:
        respostas = json.loads(C.ler_remoto(C.ARQ_RESPOSTAS, "[]") or "[]")
    except Exception:
        respostas = []
    ruins = [str(r.get("pergunta", ""))[:120] for r in respostas if r.get("ruim")][-5:]
    if not ultimas and not ruins:
        return "Sem material para autocrítica hoje (diário vazio e nenhum feedback negativo)."
    prompt = (
        "Você é a Assistente Rebocl, fazendo sua AUTOCRÍTICA noturna.\n\n"
        "Seu diário de hoje (últimos acontecimentos):\n" + "\n".join(ultimas)[:2500]
        + "\n\nPerguntas que o dono marcou como resposta ruim:\n"
        + ("\n".join("- " + r for r in ruins) if ruins else "(nenhuma)")
        + "\n\nEscreva NO MÁXIMO 3 lições curtas e CONCRETAS de correção de comportamento "
          "para amanhã (só a lista, cada linha começando com '- '; se estiver tudo bem, "
          "escreva apenas '- manter o rumo')."
    )
    texto, motor, _erro = C.chamar_llm([{"role": "user", "content": prompt}])
    if not texto:
        return "Nenhum motor respondeu para a autocrítica; tento amanhã."
    texto = C._limpar_pensar(texto)
    licoes = ["- (auto) " + re.sub(r"^[-*\s\d.]*", "", l).strip()[:180]
              for l in texto.splitlines() if l.strip().startswith(("-", "*", "1.", "2.", "3."))]
    licoes = licoes[:3] or ["- (auto) manter o rumo"]
    C.acrescentar_memoria(C.ARQ_LICOES, "\n".join(licoes),
                          titulo="# Lições que o dono ensinou (obediência obrigatória)\n")
    return f"🪞 Autocrítica gravada ({len(licoes)} lição/ões) via {motor}."


if __name__ == "__main__":
    print(autocriticar())
