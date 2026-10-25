#!/usr/bin/env python3
"""Testa se é possível rodar um motor LOCAL no runner — sem chave, sem cota, sem API.

POR QUE
-------
Hoje dependemos de 6 motores sem chave (llm7, g4f, Pollinations). Eles funcionam, mas
todos são limites compartilhados: 429 aparece sem aviso e o modelo é pequeno. A pergunta
certa não é "como conseguir mais cota", é "como não depender de cota".

Um modelo roda dentro do próprio runner se couber em CPU e memória. O runner padrão tem
4 vCPU e 16 GB. Isto mede, de verdade, se um modelo pequeno responde em tempo aceitável.

O que NÃO espero: qualidade de modelo grande. Um 0.5B não escreve como um 70B. O objetivo
é ter o último recurso que nunca dá 429 — e que, alimentado com os dados da casa, responde
o que é da casa.

Roda: python3 testar-local.py
"""
import json
import os
import sys
import time
import urllib.request

MODELOS = [
    ("Qwen2.5-0.5B-Instruct Q4_K_M",
     "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
     "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    ("Qwen2.5-1.5B-Instruct Q4_K_M",
     "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
     "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
]

CACHE = os.path.expanduser("~/.cache/motor-local")


def baixar(url, nome):
    os.makedirs(CACHE, exist_ok=True)
    destino = os.path.join(CACHE, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 50_000_000:
        return destino, 0.0
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "motor-local/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(destino, "wb") as f:
        f.write(r.read())
    return destino, round(time.time() - t0, 1)


def testar(nome, url, arquivo):
    try:
        from llama_cpp import Llama
    except ImportError:
        print("❌ llama-cpp-python não instalado")
        return None
    caminho, seg = baixar(url, arquivo)
    mb = os.path.getsize(caminho) / 1e6
    print(f"\n{nome}: {mb:.0f} MB (download {seg}s)")
    t0 = time.time()
    llm = Llama(model_path=caminho, n_ctx=1024, n_threads=os.cpu_count() or 4, verbose=False)
    print(f"  carregou em {time.time() - t0:.1f}s")

    # desafio de raciocínio: mesma prova que uso nos motores remotos
    pergunta = ("Uma caixa tem 17 pacotes com 6 unidades cada. Saem 23 unidades. "
                "Quantas unidades ficam? Responda só com o número.")
    t0 = time.time()
    saida = llm(f"Pergunta: {pergunta}\nResposta:", max_tokens=32, temperature=0.0, stop=["\n"])
    dur = time.time() - t0
    texto = saida["choices"][0]["text"].strip()
    tokens = saida["usage"]["completion_tokens"]
    tok_s = tokens / dur if dur else 0
    acertou = "79" in texto  # 17*6-23 = 79
    print(f"  resposta: {texto[:80]!r}")
    print(f"  {tokens} tokens em {dur:.1f}s = {tok_s:.1f} tok/s · desafio: "
          f"{'ACERTOU' if acertou else 'ERROU'} (esperado 79)")

    # pergunta aberta, para ver se escreve texto utilizável
    t0 = time.time()
    out = llm("Pergunta: em duas frases, por que o ceu e azul?\nResposta:",
              max_tokens=80, temperature=0.3)
    dur2 = time.time() - t0
    print(f"  texto aberto ({dur2:.1f}s): {out['choices'][0]['text'].strip()[:160]!r}")
    return {"nome": nome, "mb": round(mb), "tok_s": round(tok_s, 1),
            "acertou": acertou, "seg_200_tokens": round(200 / tok_s, 1) if tok_s else None}


def main():
    print("=" * 70)
    print("MOTOR LOCAL — sem chave, sem cota, sem API")
    print(f"CPUs: {os.cpu_count()} | memória: livre é o que o runner der")
    print("=" * 70)
    resultados = []
    for nome, url, arq in MODELOS:
        try:
            r = testar(nome, url, arq)
            if r:
                resultados.append(r)
        except Exception as e:
            print(f"❌ {nome}: {type(e).__name__}: {str(e)[:160]}")
    print("\n" + "=" * 70)
    if resultados:
        for r in resultados:
            print(f"{r['nome']}: {r['tok_s']} tok/s · resposta de 200 tokens em "
                  f"~{r['seg_200_tokens']}s · desafio {'ok' if r['acertou'] else 'falhou'}")
        with open("resultado-local.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)
        print("\nCÓDIGO DE SAÍDA 0 — há motor local viável")
    else:
        print("Nenhum modelo local rodou. Sem resultado inventado.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
