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
    ("Qwen2.5-0.5B Q4",
     "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
     "qwen2.5-0.5b-instruct-q4_k_m.gguf"),
    ("Qwen2.5-1.5B Q4",
     "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
     "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    ("Qwen2.5-3B Q4",
     "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
     "qwen2.5-3b-instruct-q4_k_m.gguf"),
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
    _threads = os.cpu_count() or 4
    llm = Llama(model_path=caminho, n_ctx=2048, n_threads=_threads, n_batch=512,
                n_threads_batch=_threads, verbose=False)
    print(f"  carregou em {time.time() - t0:.1f}s")

    # desafio de raciocínio: mesma prova que uso nos motores remotos
    pergunta = ("Uma caixa tem 17 pacotes com 6 unidades cada. Saem 23 unidades. "
                "Quantas unidades ficam? Responda só com o número.")
    # MEDIÇÃO DA VELOCIDADE À PARTE DA QUALIDADE.
    # Erro da medição anterior: resposta de 2 tokens dividida pelo tempo total dá "3 tok/s",
    # mas isso mede o custo de acordar o modelo, não a velocidade. Aqui sai uma resposta de
    # tamanho fixo e tiro a média de 2 rodadas, descartando a primeira (que carrega o cache).
    llm.create_chat_completion(messages=[{"role": "user", "content": "aqueca"}], max_tokens=8)
    medicoes = []
    for _ in range(2):
        t0 = time.time()
        saida_v = llm.create_chat_completion(
            messages=[{"role": "user", "content": "Escreva um paragrafo curto sobre jogos indie."}],
            max_tokens=150, temperature=0.7)
        d = time.time() - t0
        n = saida_v["usage"]["completion_tokens"]
        if d > 0 and n > 5:
            medicoes.append(n / d)
    tok_s = sum(medicoes) / len(medicoes) if medicoes else 0.0
    print(f"  velocidade: {tok_s:.1f} tok/s (media de {len(medicoes)} rodadas de 150 tokens)")

    # AGORA a qualidade, com o template de chat correto
    saida = llm.create_chat_completion(
        messages=[{"role": "system", "content": "Responda só com o número, sem explicação."},
                  {"role": "user", "content": pergunta}],
        max_tokens=48, temperature=0.0)
    texto = (saida["choices"][0]["message"]["content"] or "").strip()
    acertou = "79" in texto  # 17*6-23 = 79
    print(f"  resposta: {texto[:80]!r}")
    print(f"  desafio: {'ACERTOU' if acertou else 'ERROU'} (esperado 79) → {texto[:60]!r}")
    print(f"  resposta de 300 tokens levaria ~{300 / tok_s:.0f}s" if tok_s else "  sem medição")

    # pergunta aberta, para ver se escreve texto utilizável
    t0 = time.time()
    out = llm.create_chat_completion(
        messages=[{"role": "user", "content": "Em duas frases, por que o céu é azul?"}],
        max_tokens=90, temperature=0.3)
    dur2 = time.time() - t0
    print(f"  qualidade do texto ({dur2:.1f}s): {(out['choices'][0]['message']['content'] or '').strip()[:220]!r}")
    return {"nome": nome, "mb": round(mb), "tok_s": round(tok_s, 1),
            "acertou": acertou, "seg_200_tokens": round(200 / tok_s, 1) if tok_s else None}


def main():
    print("=" * 70)
    print("MOTOR LOCAL — sem chave, sem cota, sem API")
    print(f"CPUs: {os.cpu_count()} | memória: livre é o que o runner der")
    print("=" * 70)
    # A CPU do runner é compartilhada: medir o modelo sem medir a máquina engana.
    try:
        with open("/proc/cpuinfo") as f:
            modelo_cpu = [l.split(":", 1)[1].strip() for l in f if l.startswith("model name")][0]
        print(f"CPU: {modelo_cpu}")
        with open("/proc/cpuinfo") as f:
            flags = [l for l in f if l.startswith("flags")][0]
        print(f"AVX2: {'avx2' in flags} | AVX512: {'avx512f' in flags}")
        with open("/proc/loadavg") as f:
            print(f"carga no momento: {f.read().strip()}")
    except Exception:
        pass
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
            print(f"{r['nome']}: {r['tok_s']} tok/s · 300 tokens em ~{r['seg_300_tokens']}s · "
                  f"desafio {'ACERTOU' if r['acertou'] else 'falhou'}")
        with open("resultado-local.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=1)
        print("\nCÓDIGO DE SAÍDA 0 — há motor local viável")
    else:
        print("Nenhum modelo local rodou. Sem resultado inventado.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
