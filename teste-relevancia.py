#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A resposta responde à pergunta? — prova com o caso real que falhou, sem rede.

Medido em 31/10/2026: pedi ao chat "quantos jogos a casa tem publicados e qual é o próximo passo
do roadmap?" e voltou um relatório de retorno por tipo de post. Verdadeiro, bonito e fora da
pergunta. Este teste fixa o caso: a resposta real que voltou TEM de ser marcada como fora do
assunto, e uma resposta que responde TEM de passar. Também prova que o responder usa a medida e
que a segunda tentativa só é adotada quando cobre mais.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import relevancia as R

CERTOS, FALHAS = [], []


def ok(nome, condicao, detalhe=""):
    CERTOS.append(nome) if condicao else FALHAS.append(nome)
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome
          + ("" if condicao else "  <" + str(detalhe)[:160] + ">"))


# ---------------------------------------------------------------- o caso real, palavra por palavra
PERGUNTA = "quantos jogos a casa tem publicados e qual é o próximo passo do roadmap?"
RESPOSTA_REAL = (
    "🤖 **Assistente Rebocl**\n\n**Decisão a partir do que foi medido** (não é opinião de "
    "marketing genérico):\n\n**Retorno por tipo de post (Bluesky, medição real):**\n"
    "- conteúdo dos jogos: média **1.9**, sem retorno em 16 (17.8%)\n"
    "- comentário em post alheio: média **0.88**, sem retorno em 87 (41.4%)\n\n"
    "→ **conteúdo dos jogos rende 2.2× mais por post que comentário em post alheio.**")
RESPOSTA_BOA = ("A casa tem 2 jogos publicados: CEIFALUME 0.1 e PRANCHETA. O próximo passo do "
                "roadmap é fechar a 0.2 do Ceifalume (plantio e colheita no navegador).")

print("== 1. o defeito que foi medido")
_ruim = R.cobre(PERGUNTA, RESPOSTA_REAL)
_boa = R.cobre(PERGUNTA, RESPOSTA_BOA)
ok("a resposta que mudou de assunto é detectada", R.fora_do_assunto(PERGUNTA, RESPOSTA_REAL),
   _ruim)
ok("a nota dela é baixa (< 0.5)", _ruim["nota"] < 0.5, _ruim["nota"])
ok("os termos que ficaram de fora são os da pergunta (roadmap, passo, próximo)",
   {"roadmap", "proximo", "passo"}.issubset(set(_ruim["faltando"])), _ruim["faltando"])
ok("a resposta que responde NÃO é marcada", not R.fora_do_assunto(PERGUNTA, RESPOSTA_BOA), _boa)
ok("a nota da resposta boa é alta (>= 0.8)", _boa["nota"] >= 0.8, _boa["nota"])

print("== 2. a medida é explicável e estável")
ok("os termos da pergunta são só os de assunto",
   R.termos(PERGUNTA) == ["jogos", "publicados", "proximo", "passo", "roadmap"], R.termos(PERGUNTA))
ok("palavra vazia não vira assunto", "qual" not in R.termos(PERGUNTA))
ok("acento não muda a conta",
   R.termos("qual é o próximo passo") == R.termos("qual e o proximo passo"),
   (R.termos("qual é o próximo passo"), R.termos("qual e o proximo passo")))
ok("plural casa com singular (radical)",
   R.cobre("quantos jogos publicados", "o jogo publicado")["nota"] >= 0.5)
ok("saudação sem assunto não é julgada (nota 1)",
   R.cobre("oi, bom dia", "oi! em que posso ajudar?")["nota"] == 1.0)
ok("resposta vazia não é tratada como fora do assunto",
   R.fora_do_assunto(PERGUNTA, "   ") is False)

print("== 3. escolher a melhor candidata")
_escolhida, _rotulo, _aval = R.melhor(PERGUNTA, [(RESPOSTA_REAL, "primeira"),
                                                (RESPOSTA_BOA, "reforçada")])
ok("a melhor candidata é a que responde", _escolhida == RESPOSTA_BOA, _rotulo)
ok("o rótulo diz qual foi adotada", _rotulo == "reforçada")
ok("a avaliação traz as duas notas", len(_aval["avaliados"]) == 2, _aval)
ok("candidata vazia é ignorada",
   R.melhor(PERGUNTA, [("", "x"), (RESPOSTA_BOA, "y")])[1] == "y")
ok("sem candidata nenhuma, não inventa",
   R.melhor(PERGUNTA, [("", "x")])[0] is None)

print("== 4. o reforço diz o que fazer")
_reforco = R.reforco(PERGUNTA)
ok("o reforço manda responder exatamente o que foi perguntado",
   "EXATAMENTE" in _reforco, _reforco[:80])
ok("o reforço repete a pergunta", "roadmap" in _reforco)
ok("o reforço lista os assuntos tratados", "jogos" in _reforco and "passo" in _reforco)
ok("o reforço proíbe trocar de assunto", "Não troque de assunto" in _reforco)
ok("o reforço permite dizer que o dado não existe, em vez de inventar",
   "não há esse dado" in _reforco or "nao ha esse dado" in _reforco.lower())

print("== 5. o responder USA a medida (e não é só um módulo bonito ao lado)")
_fonte = open(Path(__file__).resolve().parent / "responder.py", encoding="utf-8").read()
ok("o responder importa a relevância", "import relevancia as _rel" in _fonte)
ok("o responder mede antes de publicar", "_rel.cobre(texto, resposta)" in _fonte)
ok("o responder pede uma segunda tentativa só quando está fora do assunto",
   "_rel.fora_do_assunto(texto, resposta)" in _fonte)
ok("o responder adota a segunda tentativa só se cobrir mais",
   "_rel.melhor(" in _fonte and "_escolhida == _outra" in _fonte)
ok("a relevância pode ser desligada por ambiente (para não travar nada)",
   'REFORCO_RELEVANCIA' in _fonte)
ok("a medida fica registrada no log",
   "relevância: resposta cobriu" in _fonte)

print()
if FALHAS:
    print("%d de %d verificações da relevância FALHARAM" % (len(FALHAS), len(CERTOS) + len(FALHAS)))
    sys.exit(1)
print("%d/%d verificações da relevância passaram" % (len(CERTOS), len(CERTOS)))
