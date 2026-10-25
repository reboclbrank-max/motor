#!/usr/bin/env python3
"""Prova do limite: faz N perguntas seguidas e mede quantas caem no limite.

POR QUE
-------
"Motor sem limite" não existe, mas limite é POR MOTOR. Este teste responde com número a
uma pergunta só: com rodízio entre os motores aprovados, quantas perguntas seguidas o Chat
aguenta antes de alguma ficar sem resposta?

Mede e reporta:
  - quantas responderam
  - quantos motores DIFERENTES serviram (é o tamanho real do "balde somado")
  - quantas tentativas bateram em 429
  - o tempo de cada uma

Nada é estimado: se der 0, escreve 0.
"""
import json
import sys
import time

import comum as C

# Perguntas de tipos diferentes, para exercitar categorias distintas.
PERGUNTAS = [
    "uma caixa tem 7 pacotes com 8 unidades cada; saem 9 unidades. quantas ficam?",
    "qual o proximo numero: 1, 4, 9, 16, 25?",
    "17*23",
    "responda apenas: quantos lados tem um hexagono?",
    "quantos minutos tem duas horas e meia?",
    "se 3 operarios fazem uma obra em 12 dias, quantos dias levam 4 operarios?",
    "qual a capital da Australia? responda so o nome",
    "quanto e 144 dividido por 12?",
    "um trem sai as 14h e leva 2h40; que horas chega? responda so a hora",
    "responda apenas: 9 ao quadrado",
]


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    print("=" * 70)
    print(f"PROVA DE LIMITE — {total} perguntas seguidas com rodízio")
    print("=" * 70)

    servidos = {}
    ok = falhou = bateu_429 = 0
    tempos = []
    inicio = time.time()

    for i in range(total):
        pergunta = PERGUNTAS[i % len(PERGUNTAS)]
        t0 = time.time()
        texto, motor, erro = C.chamar_llm(
            [{"role": "user", "content": pergunta}],
            "Responda de forma curta e direta, em português.")
        dur = time.time() - t0
        if texto:
            ok += 1
            servidos[motor] = servidos.get(motor, 0) + 1
            tempos.append(dur)
            print(f"  #{i + 1:02d} ok   {dur:5.1f}s  {motor[:38]:<38} {(texto or '')[:40]!r}")
        else:
            falhou += 1
            if "429" in str(erro):
                bateu_429 += 1
            print(f"  #{i + 1:02d} FALHOU {dur:5.1f}s  {str(erro)[:70]}")

    total_s = time.time() - inicio
    print("\n" + "=" * 70)
    print(f"respondidas:   {ok}/{total}")
    print(f"falharam:      {falhou}")
    print(f"tentativas que bateram em 429: {bateu_429}")
    print(f"motores diferentes que serviram: {len(servidos)}")
    for m, n in sorted(servidos.items(), key=lambda kv: -kv[1]):
        print(f"   {n:3d}× {m}")
    if tempos:
        print(f"tempo médio por resposta: {sum(tempos) / len(tempos):.1f}s")
    print(f"tempo total: {total_s:.0f}s")
    print("=" * 70)

    resumo = {
        "quando": C.agora().isoformat(),
        "perguntas": total, "respondidas": ok, "falharam": falhou,
        "bateu_429": bateu_429, "motores_distintos": len(servidos),
        "por_motor": servidos,
        "tempo_medio_s": round(sum(tempos) / len(tempos), 1) if tempos else None,
    }
    try:
        C.escrever_remoto("MEMORIA/prova-limite.json",
                          json.dumps(resumo, ensure_ascii=False, indent=1),
                          "prova de limite: rodízio entre motores")
        print("resultado guardado em MEMORIA/prova-limite.json")
    except Exception as e:
        print(f"não guardei: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
