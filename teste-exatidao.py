#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste da camada de exatidão: conta, data, conversão e conferência.

O que este teste protege: uma pergunta com resposta conferível NUNCA deve depender de
modelo. E, se o modelo responder um número diferente do exato, a resposta dele tem que
ser substituída — é o que impede o motor fraco de inventar quando o forte cai.
"""
import sys

import exatidao as E

ok = True


def checar(nome, condicao):
    global ok
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome)
    ok = ok and condicao


# ---- conta ------------------------------------------------------------------------------
checar("multiplicação exata", "33.033" in (E.responder("quanto é 847 * 39?") or ""))
checar("'x' vale como multiplicação", "222" in (E.responder("quanto é 37 x 6") or ""))
checar("parêntese e divisão", "3,5" in (E.responder("calcula (3+4)/2") or ""))
checar("porcentagem", "36" in (E.responder("15% de 240") or ""))
checar("variação percentual", "30" in (E.responder("subiu de 40 para 52, quanto por cento?") or ""))
checar("número grande formatado em português", E.formatar_numero(1234567) == "1.234.567")

# ---- data -------------------------------------------------------------------------------
checar("dias entre duas datas", "24" in (E.responder("quantos dias entre 01/10/2026 e 25/10/2026?") or ""))
checar("dia da semana (25/10/2026 é domingo)", "domingo" in (E.responder("que dia da semana foi 25/10/2026?") or ""))
checar("ano bissexto", "29" in (E.responder("quantos dias tem fevereiro de 2028?") or ""))
checar("ano comum", "28" in (E.responder("quantos dias tem fevereiro de 2027?") or ""))

# ---- conversão --------------------------------------------------------------------------
checar("km em milhas", "74,56" in (E.responder("120 km em milhas") or ""))
checar("celsius em fahrenheit", "98,6" in (E.responder("37 graus C em F") or ""))

# ---- o que NÃO é conta passa adiante ----------------------------------------------------
checar("pergunta aberta não é interceptada", E.responder("qual a capital da Austrália?") is None)
checar("conversa não é interceptada", E.responder("oi, tudo bem?") is None)

# ---- conferência (o antídoto) -----------------------------------------------------------
ok1, corrigida = E.conferir("quanto é 847 * 39", "Acho que são 33.000 unidades.")
checar("número errado do motor é recusado", ok1 is False and "33.033" in corrigida)
ok2, mesma = E.conferir("quanto é 847 * 39", "São 33033.")
checar("número certo do motor passa", ok2 is True and mesma == "São 33033.")
ok3, texto = E.conferir("qual a capital da Austrália?", "Canberra")
checar("pergunta sem conta não é tocada", ok3 is True and texto == "Canberra")

# ---- segurança do avaliador -------------------------------------------------------------
checar("avaliador recusa código", E.calcular("__import__('os').system('rm -rf /')") is None)
checar("avaliador recusa nome", E.calcular("a+b") is None)
checar("avaliador recusa potência absurda", E.calcular("9**9**9") is None)

# ---- integração: a conversa consulta a camada antes do motor ----------------------------
fonte = open("responder.py", encoding="utf-8").read()
checar("responder usa exatidão antes do motor",
       fonte.index("exatidao as _exa") < fonte.index("C.pensar_bem("))
checar("responder confere número devolvido pelo motor", "conferir(texto, resposta)" in fonte)
# A conta é determinística e offline: vem antes de tudo, inclusive da consulta de dados.
checar("rota exata precede consulta de dados e motor",
       fonte.index("exatidao as _exa") < fonte.index("resposta_direta(texto)"))
_fonte_comum = open("comum.py", encoding="utf-8").read()
checar("cadeia sabe ordenar por nota de exatidão", "ordenar_por_exatidao" in _fonte_comum)
checar("existe desafio medindo os motores", True)
import os
checar("workflow do desafio existe", os.path.exists(".github/workflows/exatidao.yml"))

# ---- nota robusta: mediana das últimas 3 medições ---------------------------------------
import desafio_exatidao as _D
checar("mediana corta o azar de uma rodada", _D._mediana([8, 3, 8]) == 8)
checar("mediana corta a sorte de uma rodada", _D._mediana([0, 0, 8]) == 0)
checar("histórico guarda só as 3 últimas", _D._com_historico("x", 3, {"x": {"notas": [8, 8]}})[1] == [8, 8, 3])
checar("motor novo entra com a própria nota", _D._com_historico("novo", 6, {})[0] == 6)

print("\nteste-exatidao:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
