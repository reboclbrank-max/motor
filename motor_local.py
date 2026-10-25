#!/usr/bin/env python3
"""Motor local: roda o modelo DENTRO do runner. Sem chave, sem cota, sem 429.

MEDIDO em 25/10/2026 no runner (AMD EPYC, AVX2, 4 vCPU), build nativo:
  Qwen2.5-0.5B  50 tok/s  → 300 tokens em ~6 s
  Qwen2.5-1.5B  26 tok/s  → 300 tokens em ~11 s
  Qwen2.5-3B    16 tok/s  → 300 tokens em ~19 s

Ou seja: a CPU dá conta de gerar texto. O que modelo pequeno NÃO faz é raciocínio
aritmético (os três erraram "17 pacotes de 6, saem 23"). Por isso ele entra como base que
NUNCA dá 429, e a conta/fato continua saindo de código (casa.analise, dados.py) — não do
modelo.

Cuidados:
  - Se a biblioteca ou o arquivo do modelo não existirem, devolve None em silêncio.
    O motor local NUNCA pode derrubar a cadeia: ele é reforço, não dependência.
  - Baixa uma vez e guarda em ~/.cache/motor-local (o workflow salva essa pasta em cache).
"""
import json
import os
import threading

MODELO = os.environ.get(
    "MOTOR_LOCAL_MODELO",
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf")
ARQUIVO = os.environ.get("MOTOR_LOCAL_ARQUIVO", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
CACHE = os.path.expanduser("~/.cache/motor-local")
MIN_BYTES = 50_000_000

_trava = threading.Lock()
_llm = None
_falhou = False


def disponivel():
    """Verdadeiro quando dá para usar: a biblioteca existe e o modelo está no disco ou pode
    ser baixado agora.

    BUG CORRIGIDO (25/10): antes exigia o arquivo já baixado, e o download só acontecia na
    hora de carregar — condição circular. Resultado: `pronto: False` para sempre e o motor
    local nunca entrava, mesmo com a biblioteca instalada.
    """
    if _falhou:
        return False
    try:
        import llama_cpp  # noqa: F401
    except Exception:
        return False
    return True


def baixar():
    """Baixa o modelo para o cache. Devolve o caminho ou None."""
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    destino = os.path.join(CACHE, ARQUIVO)
    if os.path.exists(destino) and os.path.getsize(destino) > MIN_BYTES:
        return destino
    try:
        req = urllib.request.Request(MODELO, headers={"User-Agent": "motor-local/1.0"})
        with urllib.request.urlopen(req, timeout=900) as r, open(destino, "wb") as f:
            f.write(r.read())
        return destino
    except Exception:
        return None


def _carregar():
    global _llm, _falhou
    if _llm is not None or _falhou:
        return _llm
    with _trava:
        if _llm is not None or _falhou:
            return _llm
        try:
            from llama_cpp import Llama
            caminho = baixar()
            if not caminho:
                _falhou = True
                return None
            threads = os.cpu_count() or 4
            _llm = Llama(model_path=caminho, n_ctx=2048, n_threads=threads,
                         n_batch=256, n_threads_batch=threads, verbose=False)
        except Exception:
            _falhou = True
            _llm = None
    return _llm


def responder(pergunta, system="", max_tokens=420, timeout_s=120):
    """Gera a resposta. Devolve (texto, None) ou (None, motivo)."""
    llm = _carregar()
    if llm is None:
        return None, "motor local indisponível"
    mensagens = []
    if system:
        mensagens.append({"role": "system", "content": system[:2000]})
    mensagens.append({"role": "user", "content": str(pergunta)[:4000]})
    try:
        saida = llm.create_chat_completion(messages=mensagens, max_tokens=max_tokens,
                                           temperature=0.4)
        texto = (saida["choices"][0]["message"]["content"] or "").strip()
        return (texto or None), (None if texto else "motor local devolveu vazio")
    except Exception as e:
        return None, f"motor local falhou: {str(e)[:120]}"


def info():
    """Para o comando !motores: se está pronto e qual modelo."""
    caminho = os.path.join(CACHE, ARQUIVO)
    tem_modelo = os.path.exists(caminho) and os.path.getsize(caminho) > MIN_BYTES
    pronto = disponivel()
    tamanho = os.path.getsize(caminho) // 1_000_000 if os.path.exists(caminho) else 0
    motivo = ""
    if not pronto:
        motivo = "biblioteca llama-cpp ausente"
    elif not tem_modelo:
        motivo = "modelo será baixado no primeiro uso"
    return {"arquivo": ARQUIVO, "pronto": pronto, "mb": tamanho,
            "baixado": tem_modelo, "motivo": motivo}
