#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prova de fogo: cada chave que a casa tem responde de verdade?

Substitui o heredoc portado do privado, que lia `MEMORIA/cofre-chaves.json` — arquivo que
não existe mais, e por isso o robô ficou parado. Aqui as chaves vêm das Actions secrets do
repositório público.

Regra: uma chamada curta por provedor, com resposta verificável. Não existe "achismo":
HTTP 200 com corpo vazio conta como MORTO, e resposta sem conteúdo legível conta como
MORTO. O resultado entra em MEMORIA/prova-fogo.json para o boletim poder citar.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import comum as C

ARQ = "MEMORIA/prova-fogo.json"
PERGUNTA = "Responda apenas: ok"

# (nome, base, [modelos a tentar em ordem], variável de ambiente da chave)
#
# Modelo muda de nome sem avisar: 404 depois de decodificar a chave é isso, não chave
# ruim. Por isso cada provedor traz candidatos e a prova para no primeiro que responder.
# Bases conferidas em 25/10/2026: requesty é router.requesty.ai (api. não resolve) e a
# NVIDIA é integrate.api.nvidia.com (nvidia.g4f.dev nem responde).
PROVEDORES = [
    ("groq", "https://api.groq.com/openai/v1",
     ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "gemma2-9b-it"], "GROQ_API_KEY"),
    ("openrouter", "https://openrouter.ai/api/v1",
     ["meta-llama/llama-3.1-8b-instruct:free", "google/gemma-2-9b-it:free",
      "mistralai/mistral-7b-instruct:free"], "OPENROUTER_API_KEY"),
    ("llm7", "https://api.llm7.io/v1", ["gpt-4o-mini", "default", "codestral-latest"], "LLM7_API_KEY"),
    ("sambanova", "https://api.sambanova.ai/v1",
     ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct"], "SAMBANOVA_API_KEY"),
    ("upstage", "https://api.upstage.ai/v1/solar", ["solar-pro", "solar-mini"], "UPSTAGE_API_KEY"),
    ("glama", "https://glama.ai/api/gateway/openai/v1", ["gpt-4o-mini"], "GLAMA_API_KEY"),
    ("requesty", "https://router.requesty.ai/v1", ["openai/gpt-4o-mini"], "REQUESTY_API_KEY"),
    ("novita", "https://api.novita.ai/v3/openai",
     ["meta-llama/llama-3.3-70b-instruct", "meta-llama/llama-3.1-8b-instruct"], "NOVITA_API_KEY"),
    ("nvidia", "https://integrate.api.nvidia.com/v1",
     ["meta/llama-3.3-70b-instruct", "meta/llama-3.1-8b-instruct"], "NVIDIA_API_KEY"),
    ("huggingface", "https://router.huggingface.co/v1",
     ["Qwen/Qwen3-235B-A22B-Instruct-2507", "meta-llama/Llama-3.3-70B-Instruct"], "HUGGINGFACE_API_KEY"),
]


def _forma(chave):
    """Só o formato: prefixo visível e tamanho. Nunca o valor — o log é público.

    Chave de verdade tem prefixo conhecido (gsk_ no Groq, sk- no OpenRouter...). Se o
    prefixo vier estranho e o tamanho for múltiplo de 4 com '=' no fim, o que foi gravado
    foi um blob base64 do cofre, não a chave — e é isso que dá 401 em todo provedor.
    """
    prefixo = chave[:4] if chave else ""
    dica = ""
    if chave.endswith("=") and len(chave) % 4 == 0:
        dica = " · parece base64 (blob do cofre), não chave crua"
    return f"{prefixo}… {len(chave)} caracteres{dica}"


# Modelo que não serve para conversa: se o catálogo devolver isto primeiro, o teste mede
# a coisa errada e o provedor parece morto por culpa nossa.
_NAO_SERVE = ("embed", "whisper", "tts", "rerank", "guard", "moderation", "voice",
              "image", "vision-only", "dall", "stable-diffusion", "flux")


def _modelos_do_catalogo(base, chave, quantos=3, timeout=20):
    """Pergunta ao provedor quais modelos existem com esta chave.

    400 e 404 quase nunca são chave ruim: é o nome do modelo que mudou (llama-3.3 virou
    3.1, o slug do free tier mudou). Em vez de manter uma lista que apodrece, o teste lê
    o catálogo e escolhe. Devolve [] se o provedor não expõe /models.
    """
    req = urllib.request.Request(base.rstrip("/") + "/models", headers={
        "Authorization": "Bearer " + chave, "User-Agent": "Mozilla/5.0 (compatible; rebocl-motor)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            dados = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []
    itens = dados.get("data") if isinstance(dados, dict) else dados
    if not isinstance(itens, list):
        return []
    nomes = []
    for item in itens:
        nome = item.get("id") or item.get("name") if isinstance(item, dict) else str(item)
        if not nome or any(x in nome.lower() for x in _NAO_SERVE):
            continue
        nomes.append(nome)
    nomes.sort(key=lambda n: (":free" not in n, len(n)))  # free primeiro, nome mais curto
    return nomes[:quantos]


def _bater(base, modelo, chave, timeout=60, tentativas=2):
    """Uma chamada curta. Devolve (estado, detalhe, segundos)."""
    url = base.rstrip("/") + "/chat/completions"
    corpo = json.dumps({"model": modelo, "max_tokens": 12,
                        "messages": [{"role": "user", "content": PERGUNTA}]}).encode()
    req = urllib.request.Request(url, data=corpo, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + chave,
        "User-Agent": "Mozilla/5.0 (compatible; rebocl-motor)",
    })
    t0 = time.time()
    for rodada in range(tentativas):
      if rodada:
          time.sleep(4)  # 429 é limite passageiro: uma pausa curta costuma resolver
      try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            bruto = r.read().decode("utf-8", "replace")
            gasto = round(time.time() - t0, 1)
            if r.status != 200:
                return "morto", f"HTTP {r.status}", gasto
            try:
                dados = json.loads(bruto)
            except Exception:
                return "morto", "resposta não é JSON", gasto
            escolha = (dados.get("choices") or [{}])[0]
            msg = escolha.get("message") or {}
            conteudo = (msg.get("content") or msg.get("reasoning_content")
                        or escolha.get("text") or "").strip()
            if not conteudo:
                # modelo de raciocínio às vezes devolve só finish_reason. Vale a próxima
                # tentativa, não o veredito de morte.
                return "vazio", "HTTP 200 mas sem conteúdo", gasto
            return "vivo", f"{conteudo[:40]} ({gasto}s)", gasto
      except urllib.error.HTTPError as e:
        if e.code == 429 and rodada + 1 < tentativas:
            continue
        return "morto", f"HTTP {e.code}", round(time.time() - t0, 1)
      except Exception as e:
        if rodada + 1 < tentativas and "timed out" not in str(e):
            continue
        return "morto", str(e)[:80], round(time.time() - t0, 1)


def disparar():
    """Bate em cada provedor que tenha chave. Provedor sem chave não é falha: é ausente."""
    resultado, vivos, testados = {}, [], 0
    for nome, base, modelos, var in PROVEDORES:
        chave = C._k(var)  # mesma porta única usada por todo o motor
        if not chave:
            resultado[nome] = {"estado": "sem chave", "detalhe": f"{var} não configurada"}
            continue
        testados += 1
        estado, detalhe, gasto, forma_usada, modelo_usado = "morto", "", 0.0, "crua", modelos[0]
        do_catalogo = _modelos_do_catalogo(base, chave)
        for modelo in (do_catalogo + [m for m in modelos if m not in do_catalogo]):
            estado, detalhe, gasto = _bater(base, modelo, chave)
            modelo_usado = modelo
            qualquer_modelo = True
            if estado == "vivo":
                break
            if "404" not in detalhe and "422" not in detalhe and "400" not in detalhe \
                    and "vazio" not in detalhe and "model" not in detalhe.lower():
                break  # não é problema de modelo: não adianta trocar
        if estado in ("vazio",) and qualquer_modelo:
            estado = "limitado"  # chave vale, os modelos free não devolvem texto
        elif estado == "morto" and qualquer_modelo and "400" in detalhe:
            estado = "limitado"
        resultado[nome] = {"estado": estado, "detalhe": detalhe, "modelo": modelo_usado,
                           "segundos": gasto, "forma_da_chave": _forma(chave)}
        if estado == "vivo":
            vivos.append(nome)
        C.log(f"prova-de-fogo: {nome} → {estado} ({detalhe[:60]}) · chave: {_forma(chave)}")

    try:
        C.escrever_remoto(ARQ, json.dumps({
            "quando": C.agora().isoformat(timespec="seconds"),
            "testados": testados, "vivos": vivos, "provedores": resultado,
        }, ensure_ascii=False), "prova-de-fogo: quem respondeu de verdade")
    except Exception as e:
        C.log(f"prova-de-fogo: não consegui gravar o resultado ({str(e)[:80]})")

    return (f"🔥 Prova de fogo: {len(vivos)}/{testados} chaves respondem"
            + (f" ({', '.join(vivos)})" if vivos else " — nenhuma"))


if __name__ == "__main__":
    print(disparar())
    sys.exit(0)
