#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Oficina dela: uma vez por dia ela olha as próprias pendências (melhorias.md,
diário, fila de respostas) e PROPÕE uma ferramenta nova em Python pra si mesma.
O código NÃO roda sozinho — fica em MEMORIA/oficina/ como proposta; o engenheiro
(a dupla dono+Arena) revisa na sessão seguinte e pluga as boas. É assim que ela
'cria a própria inteligência' com segurança: ela projeta, o humano aprova."""
import re

import comum as C

ARQ_OFICINA = "MEMORIA/oficina/index.md"


def propor_ferramenta():
    melhorias = C.ler_remoto("MEMORIA/melhorias.md", "")
    pendencias = "\n".join(melhorias.splitlines()[-15:])
    diario = "\n".join([l for l in C.ler_remoto(C.ARQ_DIARIO, "").splitlines() if l.strip()][-15:])
    fila = C.ler_remoto(C.ARQ_FILA_RESPOSTAS, "[]")[:400]
    prompt = (
        "Você é a Assistente Rebocl, na sua OFICINA: o momento em que você melhora a si mesma.\n\n"
        "Pendências anotadas pelo vigia:\n" + (pendencias or "(vazio)") +
        "\n\nSeu diário recente:\n" + (diario or "(vazio)") +
        "\n\nPerguntas do dono sem resposta (fila): " + (fila or "[]") +
        "\n\nProponha UMA ferramenta pequena (1 função Python, sem dependências novas) que faria VOCÊ "
        "melhor no seu trabalho (responder, divulgar, vigiar, estudar). Responda EXATAMENTE neste formato:\n"
        "NOME: nome-da-ferramenta\n"
        "POR QUÊ: uma linha com a dor que resolve\n"
        "CODIGO:\n```python\n# código completo da função\n```\n"
        "Seja específica para a empresa Rebocl Brank (jogos de terror, 6 canais, PC fraco)."
    )
    texto, motor, _erro = C.chamar_llm([{"role": "user", "content": prompt}])
    if not texto:
        return "Nenhum motor respondeu para a oficina hoje; tento amanhã."
    texto = C._limpar_pensar(texto)
    m_nome = re.search(r"NOME:\s*(.+)", texto)
    m_cod = re.search(r"```python\n(.*?)```", texto, re.DOTALL)
    if not (m_nome and m_cod):
        return "A proposta de hoje veio fora do formato; tento amanhã."
    nome = re.sub(r"[^a-z0-9-]", "-", m_nome.group(1).strip().lower())[:40].strip("-")
    codigo = m_cod.group(1).strip()
    por_que = (re.search(r"POR QUÊ:\s*(.+)", texto) or [None, "(sem descrição)"])[1].strip()
    try:
        compile(codigo, nome + ".py", "exec")  # só valida a sintaxe; NÃO executa
    except SyntaxError as e:
        return f"A proposta de hoje não compila ({str(e)[:60]}); arquivada sem aprovação."
    data = C.agora().strftime("%d-%m-%Y")
    C.acrescentar_memoria(
        f"MEMORIA/oficina/proposta-{data}-{nome}.py", codigo,
        titulo=f"# Proposta da oficina ({data}) — {nome}\n# Por quê: {por_que}\n# Status: AGUARDANDO REVISÃO\n")
    C.acrescentar_memoria(
        ARQ_OFICINA, f"- {data} — **{nome}**: {por_que} (aguardando revisão da dupla)",
        titulo="# Oficina dela — ferramentas propostas por ela mesma\n")
    return f"🔧 Proposta nova na oficina: **{nome}** — {por_que} (aguardando a dupla revisar e plugar)"


if __name__ == "__main__":
    print(propor_ferramenta())
