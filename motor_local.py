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
import subprocess
import sys
import tempfile
import math

MODELO = os.environ.get(
    "MOTOR_LOCAL_MODELO",
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf")
ARQUIVO = os.environ.get("MOTOR_LOCAL_ARQUIVO", "qwen2.5-1.5b-instruct-q4_k_m.gguf")
CACHE = os.path.expanduser("~/.cache/motor-local")
MIN_BYTES = 50_000_000

_trava = threading.Lock()
_llm = None
_configuracao = None
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
    """Download atômico: arquivo parcial nunca vira cache válido."""
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    if os.path.basename(ARQUIVO) != ARQUIVO:
        return None
    destino = os.path.join(CACHE, ARQUIVO)
    if os.path.isfile(destino) and os.path.getsize(destino) > MIN_BYTES:
        return destino
    temporario = None
    try:
        req = urllib.request.Request(MODELO, headers={"User-Agent": "motor-local/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            with tempfile.NamedTemporaryFile(dir=CACHE, delete=False) as f:
                temporario = f.name
                while True:
                    bloco = r.read(1024 * 1024)
                    if not bloco:
                        break
                    f.write(bloco)
        if os.path.getsize(temporario) <= MIN_BYTES:
            return None
        os.replace(temporario, destino)
        return destino
    except Exception:
        return None
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)


def _carregar(contexto=2048):
    global _llm, _falhou, _configuracao
    config = (MODELO, ARQUIVO, contexto)
    with _trava:
        if _configuracao == config and (_llm is not None or _falhou):
            return _llm
        if _llm is not None:
            _llm.close()
        _llm, _falhou, _configuracao = None, False, config
        try:
            from llama_cpp import Llama
            caminho = baixar()
            if not caminho:
                _falhou = True
                return None
            threads = os.cpu_count() or 4
            _llm = Llama(model_path=caminho, n_ctx=contexto, n_threads=threads,
                         n_batch=256, n_threads_batch=threads, verbose=False)
        except Exception:
            _falhou = True
            _llm = None
    return _llm


def _gerar(pergunta, system, max_tokens, contexto):
    llm = _carregar(contexto)
    if llm is None:
        return None, "motor local indisponível"
    # Reserva conservadora para o template do chat. Não cortar requisitos/código.
    tokens = len(llm.tokenize((system + "\n" + pergunta).encode('utf-8')))
    if tokens + max_tokens + 256 > contexto:
        return None, "contexto local insuficiente; entrada preservada, não truncada"
    mensagens = []
    if system:
        mensagens.append({"role": "system", "content": system})
    mensagens.append({"role": "user", "content": pergunta})
    try:
        saida = llm.create_chat_completion(messages=mensagens, max_tokens=max_tokens,
                                           temperature=0.4)
        texto = (saida["choices"][0]["message"]["content"] or "").strip()
        return (texto or None), (None if texto else "motor local devolveu vazio")
    except Exception as e:
        return None, "motor local falhou: " + type(e).__name__


def _executar_limitado(comando, dados, timeout_s, env):
    # stdout em arquivo temporário evita crescimento sem limite na memória do host.
    with tempfile.TemporaryFile() as saida:
        r = subprocess.run(comando, input=dados, stdout=saida,
                           stderr=subprocess.DEVNULL, timeout=timeout_s, env=env)
        saida.seek(0)
        bruto = saida.read(200001)
    if r.returncode or len(bruto) > 200000:
        raise ValueError("saída local inválida")
    return json.loads(bruto)


def responder(pergunta, system="", max_tokens=420, timeout_s=120, contexto=2048):
    """Processo cancelável sem credenciais; timeout inclui carga e geração.

    Pesos em disco continuam em cache. O modelo é descarregado a cada chamada,
    trocando latência de carga por cancelamento real e isolamento da configuração.
    """
    if contexto not in (2048, 4096):
        return None, "contexto local não permitido"
    if (type(max_tokens) is not int or not 1 <= max_tokens <= 4096 or
            type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or
            not 0 < timeout_s <= 300):
        return None, "limites locais inválidos"
    pergunta, system = str(pergunta), str(system)
    if len(pergunta) + len(system) > 100000:
        return None, "entrada local excede limite; não truncada"
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'LD_LIBRARY_PATH') if k in os.environ}
    dados = json.dumps(dict(pergunta=pergunta, system=system, max_tokens=max_tokens,
                           contexto=contexto, modelo=MODELO, arquivo=ARQUIVO,
                           cache=CACHE)).encode('utf-8')
    try:
        resultado = _executar_limitado([sys.executable, '-I', os.path.abspath(__file__),
                                        '--gerar-isolado'], dados, timeout_s, env)
        if (not isinstance(resultado, list) or len(resultado) != 2 or
                any(x is not None and not isinstance(x, str) for x in resultado)):
            raise ValueError('recibo local inválido')
        return tuple(resultado)
    except subprocess.TimeoutExpired:
        return None, "motor local excedeu tempo limite; processo encerrado"
    except Exception as e:
        return None, "motor local indisponível: " + type(e).__name__


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



if __name__ == '__main__' and sys.argv[1:] == ['--gerar-isolado']:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE, (200000, 200000))
        pedido = json.loads(sys.stdin.buffer.read(500001))
        MODELO, ARQUIVO, CACHE = pedido['modelo'], pedido['arquivo'], pedido['cache']
        print(json.dumps(_gerar(pedido['pergunta'], pedido['system'],
                                pedido['max_tokens'], pedido['contexto'])))
    except Exception as erro:
        print(json.dumps([None, 'motor local falhou: ' + type(erro).__name__]))
