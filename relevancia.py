#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A resposta responde à pergunta? — medido, não sentido.

POR QUE EXISTE (31/10/2026): foi pedido ao chat, com todas as letras:
"quantos jogos a casa tem publicados e qual é o próximo passo do roadmap?".
A resposta que voltou foi um relatório de **retorno por tipo de post** (Bluesky, média 1.9 etc.)
— números verdadeiros, bonitos e fora da pergunta. O motor escolheu um assunto que ele tem
pronto em vez de responder o que foi perguntado, e nada no caminho percebeu isso.

Aqui a cobertura é medida de forma explicável, sem modelo nenhum:

  * tira as palavras vazias ("qual", "para", "que"...), normaliza acento e caixa;
  * fica com os termos que carregam assunto (len ≥ 4);
  * conta quantos desses termos aparecem na resposta (radical: "publicados" casa "publicado");
  * `nota` = fração coberta, e `faltando` = os termos que ficaram de fora.

Não é juiz de qualidade — é detector de "mudou de assunto", que é o defeito medido. Quem decide
se a resposta é boa continua sendo o dono e o juiz de confiança da casa.
"""
import re
import unicodedata

VAZIAS = {
    "qual", "quais", "quando", "quanto", "quantos", "quantas", "onde", "porque", "porquê",
    "para", "pelo", "pela", "sobre", "entre", "depois", "antes", "agora", "hoje", "amanha",
    "voce", "você", "pode", "poderia", "fazer", "feito", "esta", "está", "estao", "estão",
    "isso", "isto", "aquilo", "esse", "essa", "este", "esta", "aquele", "aquela", "como",
    "mais", "menos", "muito", "pouco", "todo", "toda", "todos", "todas", "outro", "outra",
    "sera", "será", "tem", "ter", "tinha", "vai", "vou", "quer", "quero", "saber", "dizer",
    "fala", "falar", "coisa", "coisas", "gente", "aqui", "ali", "la", "lá", "sim", "nao",
    "não", "uma", "umas", "uns", "com", "sem", "dos", "das", "nos", "nas", "por", "que",
    "the", "and", "you", "your", "what", "when", "how", "why", "which", "there", "this",
    "that", "with", "from", "have", "does", "did", "can", "could", "would", "should",
}
# Radicais que a casa usa o tempo todo e que, sozinhos, não dizem sobre o que se perguntou.
GENERICOS = {"casa", "rebocl", "assistente", "sistema", "coisa", "melhor", "grande", "muito"}


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn")


def normalizar(texto):
    return _sem_acento((texto or "").lower())


def termos(texto, minimo=4, incluir_genericos=False):
    """Termos de assunto da frase, na ordem em que aparecem, sem repetir."""
    vistos, saida = set(), []
    for bruto in re.findall(r"[a-z0-9]+", normalizar(texto)):
        if len(bruto) < minimo or bruto in VAZIAS:
            continue
        if not incluir_genericos and bruto in GENERICOS:
            continue
        if bruto in vistos:
            continue
        vistos.add(bruto)
        saida.append(bruto)
    return saida


def _radical(termo):
    """Corte simples de plural/flexão para 'publicados' casar com 'publicado'."""
    for sufixo in ("acoes", "acao", "mente", "ndo", "dos", "das", "ais", "eis", "es", "s"):
        if len(termo) > len(sufixo) + 3 and termo.endswith(sufixo):
            return termo[:-len(sufixo)]
    return termo


def _contem(resposta_normalizada, termo):
    return _radical(termo) in _radical(resposta_normalizada) or termo in resposta_normalizada


def cobre(pergunta, resposta, limite_termos=12):
    """Quanto da pergunta aparece na resposta. Devolve dict explicável."""
    pedidos = termos(pergunta)[:limite_termos]
    alvo = normalizar(resposta)
    if not pedidos:
        return {"nota": 1.0, "pedidos": [], "citados": [], "faltando": [],
                "motivo": "a pergunta não tem termo de assunto (saudação, comando)"}
    citados = [t for t in pedidos if _contem(alvo, t)]
    faltando = [t for t in pedidos if t not in citados]
    return {"nota": round(len(citados) / float(len(pedidos)), 3),
            "pedidos": pedidos, "citados": citados, "faltando": faltando,
            "motivo": "cobertura dos termos da pergunta"}


LIMITE = 0.5   # abaixo disto a resposta mudou de assunto (medido no caso real: 0.0)


def fora_do_assunto(pergunta, resposta, limite=None):
    """Verdadeiro quando a resposta quase não toca no que foi perguntado."""
    if not (resposta or "").strip():
        return False
    return cobre(pergunta, resposta)["nota"] < (LIMITE if limite is None else limite)


def reforco(pergunta):
    """Instrução para uma segunda tentativa: responder a pergunta, não um assunto vizinho."""
    assuntos = termos(pergunta)[:6]
    return ("Responda EXATAMENTE o que foi perguntado, e comece pela resposta direta.\n"
            "A pergunta é: %r\n"
            "Ela toca nestes assuntos: %s\n"
            "Não troque de assunto. Se algum desses pontos não estiver nos dados que você tem, "
            "diga em uma linha que não há esse dado medido — não responda sobre outro tema no "
            "lugar." % (pergunta.strip()[:400], ", ".join(assuntos) or "(sem termos)"))


def melhor(pergunta, candidatos):
    """Escolhe o candidato que mais cobre a pergunta. `candidatos`: lista de (texto, rótulo)."""
    avaliados = []
    for texto, rotulo in candidatos:
        if not (texto or "").strip():
            continue
        avaliados.append((cobre(pergunta, texto)["nota"], texto, rotulo))
    if not avaliados:
        return None, None, {"nota": 0.0}
    avaliados.sort(key=lambda x: -x[0])
    nota, texto, rotulo = avaliados[0]
    return texto, rotulo, {"nota": nota, "avaliados": [(r, n) for n, _t, r in avaliados]}
