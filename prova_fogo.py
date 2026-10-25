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
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

import comum as C

ARQ = "MEMORIA/prova-fogo.json"
PERGUNTA = "Responda apenas: ok"

# (nome, base, modelo, variável de ambiente da chave)
PROVEDORES = [
    ("groq", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    ("openrouter", "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY"),
    ("llm7", "https://api.llm7.io/v1", "gpt-4o-mini", "LLM7_API_KEY"),
    ("sambanova", "https://api.sambanova.ai/v1", "Meta-Llama-3.3-70B-Instruct", "SAMBANOVA_API_KEY"),
    ("upstage", "https://api.upstage.ai/v1/solar", "solar-pro", "UPSTAGE_API_KEY"),
    ("glama", "https://glama.ai/api/gateway/openai/v1", "gpt-4o-mini", "GLAMA_API_KEY"),
    ("requesty", "https://api.requesty.ai/v1", "openai/gpt-4o-mini", "REQUESTY_API_KEY"),
    ("novita", "https://api.novita.ai/v3/openai", "meta-llama/llama-3.3-70b-instruct", "NOVITA_API_KEY"),
    ("nvidia", "https://nvidia.g4f.dev/v1", "meta/llama-3.3-70b-instruct", "NVIDIA_API_KEY"),
    ("huggingface", "https://router.huggingface.co/v1", "meta-llama/Llama-3.3-70B-Instruct", "HUGGINGFACE_API_KEY"),
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


def _variantes(chave):
    """Formas possíveis da chave: crua, e decodificada 1× e 2× de base64.

    O cofre gravava as chaves em base64 duplo. Ao injetar nos secrets do público, o blob
    foi copiado como estava — e todo provedor devolvia 401 com 'chave' de 104-268
    caracteres e '=' no fim. Decodificar antes de usar é o que faz a chave voltar a valer.
    """
    formas, vistas = [], set()

    def juntar(rotulo, valor):
        if valor and valor not in vistas:
            vistas.add(valor)
            formas.append((rotulo, valor))

    juntar("crua", chave)
    atual = chave
    for rotulo in ("base64", "base64×2"):
        try:
            bruto = base64.b64decode(atual, validate=True)
            atual = bruto.decode("utf-8")
        except Exception:
            break
        # chave de verdade é imprimível e não termina em '=' (isso é padding de blob)
        if atual and atual.isprintable() and not atual.endswith("="):
            juntar(rotulo, atual)
    return formas


def _bater(base, modelo, chave, timeout=40):
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
            conteudo = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if not conteudo:
                return "morto", "HTTP 200 mas sem conteúdo", gasto
            return "vivo", f"{conteudo[:40]} ({gasto}s)", gasto
    except urllib.error.HTTPError as e:
        return "morto", f"HTTP {e.code}", round(time.time() - t0, 1)
    except Exception as e:
        return "morto", str(e)[:80], round(time.time() - t0, 1)


def disparar():
    """Bate em cada provedor que tenha chave. Provedor sem chave não é falha: é ausente."""
    resultado, vivos, testados = {}, [], 0
    for nome, base, modelo, var in PROVEDORES:
        chave = os.environ.get(var, "").strip()
        if not chave:
            resultado[nome] = {"estado": "sem chave", "detalhe": f"{var} não configurada"}
            continue
        testados += 1
        estado, detalhe, gasto, forma_usada = "morto", "", 0.0, "crua"
        for rotulo, candidata in _variantes(chave):
            estado, detalhe, gasto = _bater(base, modelo, candidata)
            forma_usada = rotulo
            if estado == "vivo":
                break
        resultado[nome] = {"estado": estado, "detalhe": detalhe, "modelo": modelo,
                           "segundos": gasto, "forma_da_chave": _forma(chave),
                           "forma_que_funcionou": forma_usada if estado == "vivo" else None}
        if estado == "vivo":
            vivos.append(nome)
        C.log(f"prova-de-fogo: {nome} → {estado} ({detalhe[:60]}) · chave: {_forma(chave)}"
              + (f" · funcionou como {forma_usada}" if estado == "vivo" else ""))

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
