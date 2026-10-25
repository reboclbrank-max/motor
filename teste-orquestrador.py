#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa o orquestrador (v3.9): categorias, cache exato, placar, /ruim, pensar:, chamar_llm."""
import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C

store = {}
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)


def fake_escrever(caminho, conteudo, mensagem=""):
    store[caminho] = conteudo
    return True


C.escrever_remoto = fake_escrever

ok = True


def check(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


# ---- categoria ----
check("categoria codigo", C.categoria_da_pergunta("meu código python deu erro de sintaxe, ajuda") == "codigo")
check("categoria longa", C.categoria_da_pergunta("explique detalhadamente " + "x" * 250) == "longa")
check("categoria rapida", C.categoria_da_pergunta("oi, tudo bem?") == "rapida")
check("categoria criativa", C.categoria_da_pergunta("escreva uma história sobre um dragão com medo de fogo no espaço") == "criativa")

# ---- hash + cache exato ----
check("hash determinista", C.hash_pergunta("  Olá,   Mundo! ") == C.hash_pergunta("olá, mundo!"))
C.registrar_resposta_cache("como faço backup do meu jogo?", "Compacte a pasta e suba no itch.")
check("cache exato acha", C.cache_exato("Como faço backup do meu jogo?") == "Compacte a pasta e suba no itch.")
check("cache exato não acha outra", C.cache_exato("qual a capital da frança?") is None)
dados = json.loads(store[C.ARQ_RESPOSTAS])
check("entrada guarda hash", any(e.get("h") == C.hash_pergunta("como faço backup do meu jogo?") for e in dados))

# ---- placar ----
check("nota sem dados = 50", C.nota_motor("Pollinations (sem chave)", "rapida") == 50.0)
for _ in range(3):
    C.registrar_placar("Motor A", "codigo", ok=True, tempo_s=5)
C.registrar_placar("Motor B", "codigo", ok=False, ruim=True)
check("nota A > nota B", C.nota_motor("Motor A", "codigo") > C.nota_motor("Motor B", "codigo"))
check("nota A = 100", C.nota_motor("Motor A", "codigo") == 100.0)
check("escolher_motor devolve nome", isinstance(C.escolher_motor("codigo"), str))
check("escolher_motor exclui tudo → None",
      C.escolher_motor("codigo", excluir=tuple(p["nome"] for p in C.montar_provedores())) is None)

# ---- /ruim ----
comentarios_fake = [
    {"user": {"login": "reboclbrank-max", "type": "User"}, "body": "escreve uma função python pra ordenar lista"},
    {"user": {"login": "github-actions[bot]", "type": "Bot"},
     "body": "🤖 **Assistente Rebocl**\n\nAqui está…\n\n---\n_(⏱ 8 s · Pollinations (sem chave))_\n\n<!--resp:c1-->"},
]
C.gh = lambda metodo, caminho, dados=None: comentarios_fake if "comments" in caminho else {}
msg = C.marcar_ultima_resposta_ruim(5)
check("/ruim encontra motor", "Pollinations (sem chave)" in msg and "codigo" in msg)
placar = json.loads(store[C.ARQ_PLACAR])
check("placar tem ruim registrado", placar["Pollinations (sem chave)"]["codigo"]["ruim"] == 1)

# ---- pensar_bem (chamar_llm fake) ----
chamadas = []


def fake_chamar(mensagens, system=None, forcar_teste=False, preferir=None, excluir=()):
    chamadas.append((preferir, tuple(excluir)))
    if any("juiz" in (m.get("content") or "").lower() for m in mensagens):
        return "RESPOSTA FINAL DO JUIZ", "Juiz (rápido)", None
    return f"resposta de {len(chamadas)}", f"Motor {len(chamadas)}", None


C.chamar_llm = fake_chamar
tf, info = C.pensar_bem("explique quantum", "sys")
# Regra nova (25/10/2026): o juiz às vezes devolve o VEREDICTO ("Resposta A venceu") em vez
# da resposta — aconteceu na issue #30. Parece_veredicto() descarta e usa a melhor original.
check("juiz com resposta legítima passa direto", tf == "RESPOSTA FINAL DO JUIZ")

# juiz que vaza bastidor: a resposta final tem de ser a original, e o rótulo avisar
def fake_juiz_ruim(mensagens, system=None, forcar_teste=False, preferir=None, excluir=()):
    if any("juiz" in (m.get("content") or "").lower() for m in mensagens):
        return ("**Veredicto**\n- **Resposta A**: correta\n- **Resposta B**: parcialmente", "Juiz", None)
    return "resposta original util", "Motor", None


C.chamar_llm = fake_juiz_ruim
tf2, info2 = C.pensar_bem("explique quantum", "sys")
check("juiz que vaza veredicto é descartado", tf2 == "resposta original util")
check("o rótulo avisa que o juiz foi descartado", "juiz descartado" in (info2 or ""))

# devolve o dublê original: os testes seguintes dependem dele, e a contagem recomeça
C.chamar_llm = fake_chamar
chamadas.clear()
C.pensar_bem("explique quantum", "sys")
check("pensar_bem chamou 3x (2 motores + juiz)", len(chamadas) == 3)
check("pensar_bem exclui o 1º motor no 2º", chamadas[1][1] == ("Motor 1",))

# ---- chamar_llm real: preferir/excluir (fakes internos) ----
importlib.reload(C)
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)
C.escrever_remoto = fake_escrever
C.montar_provedores = lambda: [
    {"nome": "M1", "id": "m1", "tipo": "openai", "base": "x", "chave": "", "modelo": "m"},
    {"nome": "M2", "id": "m2", "tipo": "openai", "base": "x", "chave": "", "modelo": "m"},
    {"nome": "M3", "id": "m3", "tipo": "openai", "base": "x", "chave": "", "modelo": "m"},
]
ordem = []


def fake_provedor(p, mensagens, system):
    ordem.append(p["nome"])
    return f"ok de {p['nome']}"


C._chamar_provedor = fake_provedor
C.ler_diagnostico = lambda: {}
C.salvar_diagnostico = lambda d: True
C.marcar_uso = lambda d, p: None

t, m, e = C.chamar_llm([{"role": "user", "content": "oi"}], preferir="M3")
check("preferir coloca no topo", ordem[0] == "M3" and m == "M3")
ordem.clear()
t, m, e = C.chamar_llm([{"role": "user", "content": "oi"}], excluir=("M1", "M2"))
check("excluir tira da fila", m == "M3" and "M1" not in ordem and "M2" not in ordem)
ordem.clear()
t, m, e = C.chamar_llm([{"role": "user", "content": "oi"}], excluir=("M1", "M2", "M3"))
check("excluir tudo → erro limpo", t is None and "nenhum motor" in (e or ""))

# ---- anti-recusa: motor que se recusa é pulado sozinho ----
import types as _types
C.time = _types.SimpleNamespace(sleep=lambda s: None, time=lambda: __import__("time").time())
C.ler_diagnostico = lambda: {}
C.salvar_diagnostico = lambda d: True

ordem.clear()
C.montar_provedores = lambda: [
    {"nome": "M1", "id": "m1", "tipo": "openai", "base": "x", "chave": "", "modelo": "m"},
    {"nome": "M2", "id": "m2", "tipo": "openai", "base": "x", "chave": "", "modelo": "m"},
]


def fake_com_recusa(p, mensagens, system):
    ordem.append(p["nome"])
    if p["nome"] == "M1":
        return "Não posso ajudar com isso."
    return f"resposta livre de {p['nome']}"


# Desde 25/10/2026 a cadeia aplica RODÍZIO: quem foi usado por último vai para o fim.
# Estes testes verificam ordem e recusa, então o rodízio é zerado (fixture), senão a ordem
# depende do histórico de execuções anteriores.
import rodizio as _R
_R._carregar = lambda: {}
_R._salvar = lambda d: None

C._chamar_provedor = fake_com_recusa
t, m, e = C.chamar_llm([{"role": "user", "content": "oi"}])
check("recusa do M1 é pulada e M2 responde na mesma", m == "M2" and t == "resposta livre de M2" and ordem == ["M1", "M2"])


def fake_todos_recusam(p, mensagens, system):
    return "I'm unable to help with that request."


C._chamar_provedor = fake_todos_recusam
t, m, e = C.chamar_llm([{"role": "user", "content": "oi"}])
check("todos recusam → devolve a menos bloqueada em vez de vazio",
      t == "I'm unable to help with that request." and m == "M1")

# ---- gênio: raciocínio silencioso sai da resposta final ----
def fake_pensador(p, mensagens, system):
    return "<pensar>Passo 1: entender. Passo 2: calcular.</pensar>A resposta final é 42."


C._chamar_provedor = fake_pensador
t, m, e = C.chamar_llm([{"role": "user", "content": "quanto é 2+2?"}])
check("raciocínio <pensar> sai da resposta final", t == "A resposta final é 42.")

print("\nTESTE ORQUESTRADOR:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
