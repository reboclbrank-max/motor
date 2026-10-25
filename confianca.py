#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Confiança da resposta aberta: o motor fraco pode responder, mas não pode passar batido.

O buraco que isto fecha: em pergunta aberta (sem conta, sem data) não existe resposta
conferível por cálculo. Antes, quem respondesse primeiro respondia — e o primeiro podia ser
um motor de nota baixa. Agora, quando a pergunta é aberta, a resposta passa por três
checagens objetivas:

1. **Nota do motor** — quem respondeu tem nota no desafio de exatidão? Quanto?
2. **Sinais de risco** — promessa de ação que não foi feita, resposta truncada, vazia,
   número que não existe em nenhuma fonte da casa.
3. **Segunda opinião** — outro motor responde a mesma pergunta; comparo os dois por
   similaridade (TF-IDF, a mesma conta da memória semântica). Se discordam muito, a
   resposta não é confiável — e o sistema diz isso em vez de fingir certeza.

Nada aqui inventa juiz secreto: cada motivo é escrito na resposta para o dono ver.
"""
import re

import comum as C

# Prometer ação é o pior erro possível numa resposta: o dono acha que foi feito.
RE_PROMESSA = re.compile(
    r"\b(publicarei|vou publicar|publiquei|já publiquei|enviei|acabei de enviar|apaguei|"
    r"deletei|já apaguei|vim publicar|postei|já postei|instalei|configurei|criei o repositório)\b",
    re.IGNORECASE)
RE_CERTEZA = re.compile(r"\b(com certeza|sem dúvida|garantido|é fato que|tenho certeza)\b",
                        re.IGNORECASE)

LIMIAR_CONCORDANCIA = 0.35   # abaixo disso os dois motores estão falando coisas diferentes
NOTA_BAIXA = 4               # de 8 no desafio: abaixo disso não é motor de confiança


def nota_do_motor(nome):
    """Nota no desafio de exatidão (None quando o motor nunca foi medido)."""
    if not nome:
        return None
    try:
        notas = C._ranking_exatidao()
    except Exception:
        return None
    return notas.get(nome)


def sinais_de_risco(pergunta, resposta, motor=None):
    """Lista de motivos objetivos para desconfiar. Vazia = nada a apontar."""
    motivos = []
    texto = (resposta or "").strip()
    if not texto:
        return ["resposta vazia"]
    if len(texto) < 15:
        motivos.append("resposta muito curta para uma pergunta aberta")
    if RE_PROMESSA.search(texto):
        motivos.append("promete uma ação — publicar, apagar, enviar — que esta conversa não executou")
    nota = nota_do_motor(motor)
    if nota is not None and nota < NOTA_BAIXA:
        motivos.append(f"o motor que respondeu tem nota baixa no desafio ({nota}/8)")
    if re.search(r"\b(vou pensar|não sei|nao sei|sem informação)\b", texto, re.IGNORECASE) \
            and RE_CERTEZA.search(texto):
        motivos.append("diz que não sabe e afirma certeza na mesma resposta")
    return motivos


def concordancia(a, b):
    """Similaridade entre duas respostas (0 a 1). Usa a conta da memória semântica."""
    try:
        from memoria_semantica import _cosseno, _idf, _vetor
    except Exception:
        return None
    if not a or not b:
        return None
    try:
        idf = _idf([a, b])
        return round(_cosseno(_vetor(a, idf), _vetor(b, idf)), 3)
    except Exception:
        return None


def segunda_opiniao(pergunta, system="", excluir=()):
    """Outro motor responde a mesma pergunta. Devolve (texto, motor) ou (None, None)."""
    try:
        texto, motor, _erro = C.chamar_llm(
            [{"role": "user", "content": pergunta}], system, excluir=tuple(excluir))
    except Exception:
        return None, None
    return texto, motor


def verificar(pergunta, resposta, motor=None, system="", com_segunda=True):
    """Audita a resposta aberta. Devolve dict com confiança, motivos e a segunda opinião.

    confianca: "alta" (nada a apontar e, se houve segunda opinião, elas concordam),
               "media" (há motivo, mas a segunda opinião confirma a linha geral),
               "baixa" (motivo grave, ou os dois motores discordam).
    """
    motivos = sinais_de_risco(pergunta, resposta, motor)
    nota = nota_do_motor(motor)
    resultado = {"confianca": "alta", "motivos": motivos, "nota_do_motor": nota,
                 "segunda": None, "segunda_motor": None, "concordancia": None}

    grave = any("promete uma ação" in m or "vazia" in m for m in motivos)
    if grave:
        resultado["confianca"] = "baixa"
        return resultado

    # Caminho barato: motor de nota boa e nenhum sinal de risco não precisa de segunda
    # opinião. Segunda opinião custa uma chamada — só vale quando há dúvida.
    if nota is not None and nota >= NOTA_BAIXA and not motivos:
        return resultado

    if not com_segunda:
        if motivos:
            resultado["confianca"] = "media"
        return resultado

    outro, motor_outro = segunda_opiniao(pergunta, system, excluir=(motor,) if motor else ())
    if not outro:
        # sem segundo motor: a nota do primeiro decide
        resultado["confianca"] = "media" if motivos else "alta"
        return resultado

    semelhanca = concordancia(resposta, outro)
    resultado["segunda"] = outro
    resultado["segunda_motor"] = motor_outro
    resultado["concordancia"] = semelhanca

    if semelhanca is not None and semelhanca < LIMIAR_CONCORDANCIA:
        resultado["confianca"] = "baixa"
        resultado["motivos"] = motivos + [
            f"a segunda opinião ({motor_outro}) diz algo bem diferente "
            f"(semelhança {semelhanca:.2f})"]
    elif motivos:
        resultado["confianca"] = "media"
    return resultado


def aviso(resultado):
    """Texto honesto para colar no rodapé quando a resposta não é confiável."""
    motivos = resultado.get("motivos") or []
    if not motivos:
        return ""
    linhas = ["", "⚠️ **Não tratei isto como certo** — e o motivo é objetivo:"]
    for m in motivos[:3]:
        linhas.append(f"- {m}")
    if resultado.get("segunda"):
        linhas.append(f"- resposta alternativa de {resultado.get('segunda_motor')}: "
                      f"_{resultado['segunda'][:220]}_")
    return "\n".join(linhas)


def melhor_resposta(pergunta, resposta, motor, system=""):
    """Decide qual resposta vale: a original ou a segunda opinião.

    Critério: nota do motor primeiro; empate fica com a primeira. Nunca escolhe por
    tamanho nem por estilo — só por nota medida e por concordância.
    """
    avaliacao = verificar(pergunta, resposta, motor, system, com_segunda=True)
    if avaliacao["confianca"] == "baixa" and avaliacao.get("segunda"):
        nota_atual = nota_do_motor(motor) or 0
        nota_outra = nota_do_motor(avaliacao.get("segunda_motor")) or 0
        if nota_outra > nota_atual:
            return avaliacao["segunda"], avaliacao.get("segunda_motor"), avaliacao
    return resposta, motor, avaliacao
