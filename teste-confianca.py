#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste da confiança: motor fraco pode responder, mas não pode passar batido.

Cobre o que importa para o dono:
* promessa de ação que não foi feita é o pior erro → confiança baixa, sempre;
* motor de nota baixa gera aviso honesto;
* segunda opinião discordante rebaixa a resposta e mostra a alternativa;
* motor bom sem sinal de risco NÃO gasta segunda opinião (custo controlado);
* resposta melhor (de motor com nota maior) é a escolhida.
"""
import sys

import comum as C
import confianca as F

ok = True
chamadas = {"n": 0}


def checar(nome, condicao):
    global ok
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome)
    ok = ok and condicao


NOTAS = {"Motor Forte": 8, "Motor Fraco": 0, "Motor Médio": 4}
C._ranking_exatidao = lambda: dict(NOTAS)


def falso_llm(resposta, motor):
    def _chamar(mensagens, system=None, **kw):
        chamadas["n"] += 1
        return resposta, motor, None
    return _chamar


# ---- sinais de risco --------------------------------------------------------------------
checar("promessa de publicação é risco grave",
       any("promete uma ação" in m for m in F.sinais_de_risco("oi", "Já publiquei no Instagram!", "Motor Forte")))
checar("promessa de apagar também",
       any("promete uma ação" in m for m in F.sinais_de_risco("oi", "Apaguei os posts.", "Motor Forte")))
checar("resposta vazia é risco", F.sinais_de_risco("oi", "", "Motor Forte") == ["resposta vazia"])
checar("motor com nota baixa aparece no motivo",
       any("nota baixa" in m for m in F.sinais_de_risco("oi", "Tudo bem, vamos conversar.", "Motor Fraco")))
checar("motor forte sem risco não gera motivo",
       F.sinais_de_risco("oi", "Tudo bem, vamos conversar sobre o jogo.", "Motor Forte") == [])

# ---- verificação ------------------------------------------------------------------------
C.chamar_llm = falso_llm("Vermelho, porque aquece o ambiente da sala.", "Motor Médio")
r = F.verificar("qual a melhor cor?", "Vermelho, porque aquece o ambiente.", "Motor Fraco")
checar("motor fraco é marcado como confiança média", r["confianca"] == "media")
checar("aviso é escrito em português claro", "Não tratei isto como certo" in F.aviso(r))

r = F.verificar("oi", "Já publiquei em todos os canais.", "Motor Forte")
checar("promessa de ação é confiança baixa", r["confianca"] == "baixa")

chamadas["n"] = 0
C.chamar_llm = falso_llm("Resposta qualquer.", "Motor Forte")
r = F.verificar("fale sobre jogos", "Jogos precisam de ritmo e resposta rápida ao toque.", "Motor Forte")
checar("motor forte sem risco não gasta segunda opinião", chamadas["n"] == 0 and r["confianca"] == "alta")

chamadas["n"] = 0
C.chamar_llm = falso_llm(
    "A capital do Brasil é o Rio de Janeiro e fica no litoral.", "Motor Médio")
r = F.verificar("qual a capital do Brasil?", "Brasília foi planejada e inaugurada em 1960.", "Motor Fraco")
checar("segunda opinião discordante rebaixa para baixa", r["confianca"] == "baixa")
checar("discordância vem escrita no motivo", any("segunda opinião" in m for m in r["motivos"]))
checar("resposta alternativa é mostrada ao dono", "Rio de Janeiro" in F.aviso(r))

C.chamar_llm = falso_llm("Brasília foi planejada e inaugurada em 1960, no planalto.", "Motor Médio")
r = F.verificar("qual a capital do Brasil?", "Brasília foi planejada e inaugurada em 1960.", "Motor Fraco")
checar("segunda opinião concordante mantém média", r["confianca"] == "media")
checar("similaridade é registrada", isinstance(r["concordancia"], float))

# ---- escolha da melhor resposta ---------------------------------------------------------
C.chamar_llm = falso_llm("Resposta do motor médio, mais confiável.", "Motor Médio")
resposta, motor, aval = F.melhor_resposta("pergunta", "Resposta do fraco.", "Motor Fraco")
checar("troca para motor de nota maior quando a confiança é baixa",
       motor == "Motor Médio" and "médio" in resposta)
C.chamar_llm = falso_llm("Resposta do fraco.", "Motor Fraco")
resposta2, motor2, _ = F.melhor_resposta("oi", "Já publiquei tudo.", "Motor Forte")
checar("não troca para motor de nota menor", motor2 == "Motor Forte")

# ---- integração na conversa e ordem da cadeia -------------------------------------------
fonte = open("responder.py", encoding="utf-8").read()
checar("responder audita a resposta aberta", "import confianca as _cf" in fonte)
checar("auditoria acontece antes do envio",
       fonte.index("confianca as _cf") < fonte.index("usos_extras = executar_comandos_soltos(resposta)"))
fonte_comum = open("comum.py", encoding="utf-8").read()
checar("a nota vale sempre, não só em pergunta precisa",
       "_notas = _ranking_exatidao()" in fonte_comum)
checar("nota é aplicada depois do rodízio", fonte_comum.index("rodizio") < fonte_comum.index("_notas = _ranking_exatidao()"))

print("\nteste-confianca:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
