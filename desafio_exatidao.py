#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Desafio de exatidão: qual motor acerta o que tem resposta conferível?

Motivo: o dono não quer depender de um motor só, e "veio resposta" não quer dizer "veio
resposta certa". Aqui cada motor é medido em 8 perguntas com resposta conhecida — conta,
data, conversão, instrução e honestidade ("não sei" quando não há dado).

O resultado vira ranking em MEMORIA/exatidao-motores.json. Quem vai para tarefa que exige
exatidão é quem acerta, na ordem medida. Nada de achismo sobre qual modelo é "grande".
"""
import json
import re
import sys
import time

import comum as C

ARQ = "MEMORIA/exatidao-motores.json"

# (pergunta, resposta esperada, tipo). A comparação é tolerante a formato: aceita
# "33.033", "33033", "33 033" — mas não aceita outro número.
DESAFIO = [
    ("Quanto é 847 * 39? Responda só o número.", "33033", "conta"),
    ("Quanto é 15% de 240? Responda só o número.", "36", "conta"),
    ("Quantos dias há entre 01/10/2026 e 25/10/2026? Responda só o número.", "24", "data"),
    ("Que dia da semana foi 25/10/2026? Responda só o dia.", "domingo", "data"),
    ("Quantos dias tem fevereiro de 2028? Responda só o número.", "29", "data"),
    ("Converta 120 km para milhas. Responda só o número aproximado.", "74", "conversão"),
    ("Escreva exatamente esta palavra, sem mais nada: CEIFALUME", "CEIFALUME", "instrução"),
    # "Camberra" é o nome em português e estava sendo contado como erro — verificador
    # rígido demais reprova motor bom, e foi o que aconteceu com o OpenRouter.
    ("Qual é a capital da Austrália? Responda só o nome.", ("canberra", "camberra"), "fato"),
]

# Quando não há dado na casa, o certo é dizer que não sabe — inventar é o pior erro.
HONESTIDADE = ("Quantos usuários pagantes o aplicativo tem hoje? Se não souber, "
               "responda apenas NAO_SEI.", ("nao_sei", "não sei", "nao sei"))


def _limpar(texto):
    return re.sub(r"\s+", " ", (texto or "")).strip().lower()


def _acertou(resposta, esperado, tipo):
    """esperado pode ser uma lista: mais de uma grafia é uma resposta certa só."""
    if isinstance(esperado, (list, tuple)):
        return any(_acertou(resposta, um, tipo) for um in esperado)
    t = _limpar(resposta)
    if not t:
        return False
    if tipo == "conta":
        # o número tem que estar lá, com qualquer pontuação
        return esperado in re.sub(r"[.,\s]", "", t)
    if tipo == "data" and esperado.isdigit():
        return esperado in re.sub(r"[.,\s]", "", t)
    if tipo == "conversão":
        # 74,56 pode vir como 74,5 / 74.56 / 75 arredondado
        achados = re.findall(r"\d+(?:[.,]\d+)?", t)
        return any(abs(float(a.replace(",", ".")) - 74.56) < 1.0 for a in achados)
    return esperado.lower() in t


AMOSTRA_MINIMA = 4   # abaixo disso a nota não vale: pouca resposta é sorte, não medida


def nota_relativa(acertos, respondidas):
    """Nota de 0 a 8 sobre o que o motor REALMENTE respondeu.

    Defeito medido: o nemotron nano-omni acertou 5 de 5 perguntas que respondeu e levava
    0/8 — porque a cota o calou nas outras. Isso não mede inteligência, mede cota alheia.
    Nota = acertos / respondidas (escalada para 8), e só vale com amostra suficiente.
    Devolve (nota, valida).
    """
    if respondidas < AMOSTRA_MINIMA:
        return 0, False
    return int(round(8.0 * acertos / respondidas)), True


def _mediana(valores):
    v = sorted(valores)
    if not v:
        return 0
    meio = len(v) // 2
    return v[meio] if len(v) % 2 else round((v[meio - 1] + v[meio]) / 2)


# Erro de PORTARIA: não é limite passageiro, é porta fechada (chave morta, conta sem
# crédito, domínio que não existe). Insistir custa tempo de quem responde de verdade.
PORTARIA = ("401", "403", "402", "Name or service not known", "TLSV1_ALERT",
            "certificate verify failed", "No address associated")


def erro_de_portaria(msg):
    """True quando o erro diz 'você não entra', e não 'espere um pouco'."""
    m = str(msg or "")
    return any(x in m for x in PORTARIA)


def nota_cobertura(respondidas, total):
    """Presença em escala 8: quantas das perguntas o motor realmente respondeu."""
    if not total:
        return 0
    return int(round(8.0 * respondidas / total))


def nota_plantao(acertos, respondidas, total):
    """A nota que o dono cobra: acerto E presença, vale a pior das duas.

    Defeito medido: o Gemini tirou 8/8 acertando 4 de 4 — e ficou calado nas outras 4.
    Nota de acerto sozinha premia quem fala pouco: um motor que responde 2 perguntas
    certas e desaparece tirava nota cheia. Disponibilidade não é desculpa no rodapé,
    é parte da conta. Devolve (nota, acerto, cobertura, valida).
    """
    acerto, valida = nota_relativa(acertos, respondidas)
    cobertura = nota_cobertura(respondidas, total)
    if not valida:
        return 0, acerto, cobertura, False
    return min(acerto, cobertura), acerto, cobertura, True


def _perguntar(p, pergunta, tentativas=3):
    """Pergunta com paciência: 429/5xx ganham espera, porque limite passageiro não é burrice.

    Sem isso, uma rajada de 429 num provedor grátis vira 0/8 na nota — e o piso de nota
    manda o motor para a reserva por um motivo que era só o relógio.

    Devolve (texto, erro). O erro importa: silêncio sem causa é achismo, e é o que faz o
    dono ouvir "caiu" quando a verdade é "não tem mais crédito".
    """
    erro = None
    for tentativa in range(tentativas):
        if tentativa:
            time.sleep(4 + 2 * tentativa)
        try:
            texto = C._chamar_provedor(p, [{"role": "user", "content": pergunta}],
                                       "Responda de forma curta e direta.")
            if isinstance(texto, str) and texto.strip():
                return texto, None
            erro = "resposta vazia"
        except Exception as e:
            erro = str(e)[:90]
            if not any(x in erro for x in ("429", "502", "503", "504", "timed out", "Timeout")):
                C.log(f"exatidão: {p.get('nome')} falhou ({erro[:60]})")
                return None, erro
    return None, erro


def _com_historico(nome, acertos, anterior):
    """Nota final = MEDIANA das últimas 3 medições.

    Motivo medido: o g4f auto fez 8/8 numa rodada e 3/8 na seguinte, e o OpenRouter foi de
    8/8 para 5/8. Uma medição só derruba motor bom por azar de cota e promove motor ruim por
    sorte. Mediana de três corta os dois extremos.
    """
    hist = list((anterior.get(nome) or {}).get("notas") or [])
    hist = (hist + [acertos])[-3:]
    return _mediana(hist), hist


PRAZO_MINUTOS = 70        # o job tem 90 min; parar antes e declarar é melhor que ser cortado
ESPERA_SEGUNDA = 20       # cota grátis enche por minuto: esperar é o que devolve a resposta
_INICIO = time.time()


def _estourou_prazo():
    return (time.time() - _INICIO) / 60.0 > PRAZO_MINUTOS


def _medir_motor(p):
    """Roda as 8 perguntas num motor e devolve o retrato dele.

    Três defesas aprendidas na marra:
    1. porta de entrada — erro de acesso (401/403/402/DNS) sai na primeira pergunta em vez
       de gastar as 8 (era isso que comia metade da rodada com motor morto);
    2. segunda passada — quem calou no meio ganha outra chance depois de uma espera longa,
       porque silêncio de cota de minuto não é o mesmo que motor sem resposta;
    3. erro guardado por pergunta — sem causa declarada, "caiu" é achismo.
    """
    perguntas = list(DESAFIO)
    respostas, erros, tempos = {}, [], []
    porta = None
    for indice, (pergunta, _esperado, _tipo) in enumerate(perguntas):
        t0 = time.time()
        texto, erro = _perguntar(p, pergunta)
        tempos.append(round(time.time() - t0, 1))
        if texto:
            respostas[indice] = texto
        elif erro:
            erros.append(erro)
        if not texto and indice == 0 and erro and erro_de_portaria(erro):
            porta = erro
            break
        if not texto and not respostas and indice >= 1:
            break  # nada em duas perguntas: está fora do ar agora, não adianta insistir
        time.sleep(1.2)

    faltando = [k for k in range(len(perguntas)) if k not in respostas]
    if faltando and respostas and not _estourou_prazo():
        C.log(f"exatidão: {p.get('nome')} calou em {len(faltando)} — segunda passada "
              f"depois de {ESPERA_SEGUNDA}s (cota de minuto não é motor morto)")
        time.sleep(ESPERA_SEGUNDA)
        for k in faltando:
            if _estourou_prazo():
                break
            texto, erro = _perguntar(p, perguntas[k][0], tentativas=2)
            if texto:
                respostas[k] = texto
            elif erro:
                erros.append(erro)
            time.sleep(1.2)

    acertos = 0
    detalhe_respostas = {}
    for indice, (pergunta, esperado, tipo) in enumerate(perguntas):
        texto = respostas.get(indice)
        ok = bool(texto) and _acertou(texto, esperado, tipo)
        acertos += 1 if ok else 0
        detalhe_respostas[pergunta[:40]] = {"ok": ok, "veio": (texto or "")[:60]}
    return acertos, len(respostas), detalhe_respostas, erros, tempos, porta


def medir():
    """Passa o desafio em cada motor vivo, na ordem da cadeia."""
    global _INICIO
    _INICIO = time.time()
    try:
        anterior = json.loads(C.ler_remoto(ARQ, "{}") or "{}").get("motores") or {}
    except Exception:
        anterior = {}
    try:
        # TODA a cadeia, inclusive os que hoje são reserva: motor sem nota fica de reserva
        # para sempre, então a medição precisa alcançar todos.
        provedores = C.montar_provedores()
    except Exception as e:
        C.log(f"exatidão: não consegui montar a cadeia ({str(e)[:80]})")
        return "exatidão: cadeia indisponível"
    total = len(DESAFIO)
    vistos, ranking, detalhes = set(), [], {}
    for p in provedores:
        nome = p.get("nome") or p.get("id") or "?"
        if nome in vistos:
            continue
        vistos.add(nome)
        if _estourou_prazo():
            C.log(f"exatidão: prazo de {PRAZO_MINUTOS} min estourado — {nome} em diante "
                  "fica para a próxima rodada (declarado, não escondido)")
            break
        acertos, respondidas, respostas, erros, tempos, porta = _medir_motor(p)
        motivo = ""
        if erros:
            contagem = {}
            for e in erros:
                chave = e[:40]
                contagem[chave] = contagem.get(chave, 0) + 1
            motivo = "; ".join(f"{k} (x{v})" for k, v in
                               sorted(contagem.items(), key=lambda kv: -kv[1])[:2])
        nota, acerto, cobertura, valida = nota_plantao(acertos, respondidas, total)
        detalhes[nome] = {"acertos": acertos, "respondidas": respondidas, "total": total,
                          "nota_agora": nota, "acerto": acerto, "cobertura": cobertura,
                          "amostra_valida": valida, "honesto": None,
                          "fora_do_ar": bool(porta), "motivo": motivo,
                          "segundos_medios": round(sum(tempos) / len(tempos), 1) if tempos else None,
                          "respostas": respostas}
        if porta:
            detalhes[nome]["motivo"] = f"porta fechada: {porta[:60]}"
            C.log(f"exatidão: {nome} fora do ar — {porta[:60]} (não gasta as 8 perguntas)")
            continue
        # honestidade: só faz sentido para quem respondeu algo
        honesto = None
        if respostas:
            pergunta, esperado = HONESTIDADE
            try:
                texto = C._chamar_provedor(p, [{"role": "user", "content": pergunta}],
                                           "Responda de forma curta e direta.")
                if not isinstance(texto, str):
                    texto = None
            except Exception:
                texto = None
            honesto = bool(texto) and _acertou(texto, esperado, "fato")
        detalhes[nome]["honesto"] = honesto
        if not valida:
            C.log(f"exatidão: {nome} respondeu só {respondidas}/{total} — sem amostra, "
                  f"fica de reserva" + (f" ({motivo[:60]})" if motivo else ""))
            continue
        nota_final, hist = _com_historico(nome, nota, anterior)
        detalhes[nome]["nota_final"] = nota_final
        detalhes[nome]["notas"] = hist
        ranking.append({"motor": nome, "id": p.get("id"), "acertos": nota_final,
                        "nota_plantao": nota_final, "acerto": acerto,
                        "cobertura": cobertura, "respondidas": respondidas,
                        "notas": hist, "total": total, "honesto": honesto,
                        "motivo": motivo})
        C.log(f"exatidão: {nome} → {nota}/8 de plantão (acerto {acerto}/8 em "
              f"{respondidas} respostas, presença {cobertura}/8, histórico {hist})"
              + (" · honesto" if honesto else ""))

    ranking.sort(key=lambda r: (-r["acertos"], r["motor"]))
    try:
        C.escrever_remoto(ARQ, json.dumps({
            "quando": C.agora().isoformat(timespec="seconds"),
            "ranking": ranking, "detalhes": detalhes,
            "motores": {n: {"notas": d.get("notas"), "nota_final": d.get("nota_final"),
                            "honesto": d.get("honesto"), "motivo": d.get("motivo"),
                            "fora_do_ar": d.get("fora_do_ar")}
                        for n, d in detalhes.items()},
            "criterio": ("8 perguntas com resposta conferível + 1 de honestidade (dizer que não "
                         "sabe). Nota = a pior entre acerto (acertos/respondidas) e presença "
                         "(respondidas/8): falar pouco não é falar certo."),
        }, ensure_ascii=False), "exatidão: ranking medido dos motores")
    except Exception as e:
        C.log(f"exatidão: não consegui gravar o ranking ({str(e)[:80]})")

    if not ranking:
        return "🎯 Exatidão: nenhum motor acertou nada agora."
    melhor = ranking[0]
    acima = [r for r in ranking if (r.get("acertos") or 0) >= 4]
    mortos = sum(1 for d in detalhes.values() if d.get("fora_do_ar"))
    return (f"🎯 Exatidão: melhor motor é **{melhor['motor']}** "
            f"(nota de plantão {melhor['acertos']}/{melhor['total']}: acerto "
            f"{melhor['acerto']}/8, presença {melhor['cobertura']}/8). "
            f"{len(acima)} acima do piso, {mortos} fora do ar.")


if __name__ == "__main__":
    print(medir())
    sys.exit(0)
