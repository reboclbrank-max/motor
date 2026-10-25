#!/usr/bin/env python3
"""Colhe motores do censo que já está na casa — sem chave, sem cadastro.

O PROBLEMA QUE ISTO RESOLVE
---------------------------
`MEMORIA/motores-catalogo.json` tem 1.991 nomes de motores levantados pela caçada da casa.
O código citava 12 (0,6%). Os outros 1.979 estavam parados no disco.

Boa parte desses nomes aponta para POÇOS SEM CHAVE:
  polli-gen: 351 modelos  · Pollinations (grátis, sem cadastro)
  llm7       59 modelos   · api.llm7.io (grátis, sem cadastro)
  ollama     18 modelos   · precisa de servidor local (não usado aqui)
  hf-provider / or-todos / cf-playground · precisam de chave que está morta (401/403)

Este script pega os poços sem chave, testa cada modelo com o DESAFIO (conta verificável +
etiqueta anti-eco) e promove os que acertam para MEMORIA/motores-openai.json, que é o arquivo
que a cadeia lê para montar a fila. Nada é dado como vivo sem ter acertado a conta.

Rodar em lotes: o progresso fica em MEMORIA/catalogo-testado.json, então cada execução
continua de onde a anterior parou — 48 por dia já viram 1.700 em cinco semanas.
"""
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import comum as C

ARQ_CENSO = "MEMORIA/motores-catalogo.json"
ARQ_PROGRESSO = "MEMORIA/catalogo-testado.json"
ARQ_APROVADOS = "MEMORIA/motores-openai.json"

BASE_POLLI = "https://text.pollinations.ai/openai"
BASE_LLM7 = os.environ.get("RELE_LLM7") or "https://api.llm7.io/v1"

LOTE = int(os.environ.get("LOTE_CATALOGO", "48"))
WORKERS = int(os.environ.get("WORKERS_CATALOGO", "6"))
TIMEOUT = int(os.environ.get("TIMEOUT_CATALOGO", "40"))

_trava = threading.Lock()


def _carregar(caminho, padrao):
    try:
        bruto = C.ler_remoto(caminho, json.dumps(padrao))
        return json.loads(bruto) if bruto else padrao
    except Exception:
        return padrao


def _salvar(caminho, dados, msg):
    try:
        C.escrever_remoto(caminho, json.dumps(dados, ensure_ascii=False, indent=1), msg)
        return True
    except Exception as e:
        print(f"  ⚠️ não salvei {caminho}: {str(e)[:100]}")
        return False


def poços_sem_chave():
    """Candidatos que não precisam de chave, a partir do censo."""
    censo = _carregar(ARQ_CENSO, [])
    saida = []
    for nome in censo:
        if not isinstance(nome, str):
            continue
        if nome.startswith("polli-gen:"):
            modelo = nome.split(":", 1)[1].strip("/")
            saida.append({"id": "polli-" + modelo.replace("/", "-")[:40], "base": BASE_POLLI,
                          "modelo": modelo, "chave": "unused", "tipo": "openai",
                          "familia": "pollinations"})
        elif ":" not in nome:
            saida.append({"id": "llm7-" + nome.replace("/", "-")[:40], "base": BASE_LLM7,
                          "modelo": nome, "chave": os.environ.get("LLM7_API_KEY") or "unused",
                          "tipo": "openai", "familia": "llm7"})
    return saida


def provar(cand):
    """Manda o desafio ao candidato. Devolve (cand, passou, ms, motivo)."""
    p = {"nome": f"{cand['familia']}:{cand['modelo']}", "id": cand["id"],
         "tipo": "openai", "base": cand["base"], "chave": cand["chave"],
         "modelos": [cand["modelo"]], "modelo": cand["modelo"], "timeout": TIMEOUT}
    t0 = time.time()
    try:
        passou, _ms, motivo = C.provar_motor(p, tentativas=1)
        return cand, passou, int((time.time() - t0) * 1000), motivo
    except Exception as e:
        return cand, False, int((time.time() - t0) * 1000), str(e)[:90]


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else LOTE
    print("=" * 70)
    print(f"COLHEITA DO CENSO — até {limite} motores, {WORKERS} em paralelo")
    print("Só entra quem ACERTAR o desafio (conta verificável + etiqueta anti-eco).")
    print("=" * 70)

    censo = poços_sem_chave()
    testados = set(_carregar(ARQ_PROGRESSO, {}).get("testados", []))
    pendentes = [c for c in censo if c["id"] not in testados][:limite]
    print(f"poços sem chave no censo: {len(censo)}")
    print(f"já testados: {len(testados)}")
    print(f"neste lote: {len(pendentes)}\n")

    if not pendentes:
        print("Nada pendente: o censo sem chave já foi todo testado.")
        return 0

    aprovados = _carregar(ARQ_APROVADOS, [])
    aprovados = aprovados if isinstance(aprovados, list) else []
    ja_aprovados = {(a.get("base"), a.get("modelo")) for a in aprovados if isinstance(a, dict)}

    vivos, novos, falhas = 0, 0, 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futuros = {pool.submit(provar, c): c for c in pendentes}
        for i, fut in enumerate(as_completed(futuros), 1):
            cand, passou, ms, motivo = fut.result()
            with _trava:
                testados.add(cand["id"])
            if passou:
                vivos += 1
                print(f"  ✅ {i:02d}/{len(pendentes)} {cand['familia']:12s} "
                      f"{cand['modelo'][:40]:40s} {ms} ms")
                chave = (cand["base"], cand["modelo"])
                if chave not in ja_aprovados:
                    ja_aprovados.add(chave)
                    novos += 1
                    aprovados.append({"nome": f"{cand['familia']} ({cand['modelo']})",
                                      "base": cand["base"], "modelo": cand["modelo"],
                                      "tipo": "openai", "timeout": TIMEOUT,
                                      "chave": "propria" if cand["familia"] == "llm7" else "unused",
                                      "verificado": C.agora().date().isoformat(),
                                      "origem": "censo"})
            else:
                falhas += 1
                print(f"  ❌ {i:02d}/{len(pendentes)} {cand['familia']:12s} "
                      f"{cand['modelo'][:40]:40s} {str(motivo)[:44]}")

    _salvar(ARQ_APROVADOS, aprovados, "censo: motores aprovados no desafio")
    _salvar(ARQ_PROGRESSO, {"testados": sorted(testados), "quando": C.agora().isoformat()},
            "censo: progresso da colheita")

    restam = len(censo) - len(testados)
    print("\n" + "=" * 70)
    print(f"acertaram o desafio: {vivos} de {len(pendentes)}")
    print(f"novos motores na cadeia: {novos} (total aprovado: {len(aprovados)})")
    print(f"reprovados: {falhas}")
    print(f"ainda não testados no censo sem chave: {restam}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
