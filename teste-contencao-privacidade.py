#!/usr/bin/env python3
"""Contratos offline da contenção: nenhum provedor ou repositório real é chamado."""
import inspect
import json
import os
from pathlib import Path

os.environ.pop("REBOCL_LLM7_AUTORIZADO", None)
import comum as C
import importlib.util
import urllib.request


def carregar(nome, arquivo):
    spec = importlib.util.spec_from_file_location(nome, arquivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


COLHER = carregar("colher_catalogo_teste", "colher-catalogo.py")
VARREDURA = carregar("varredura_teste", "varredura.py")
PROVA = carregar("prova_fogo_teste", "prova_fogo.py")

resultados = []


def checar(nome, condicao):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome)


def bloqueia(chamada, *args):
    try:
        chamada(*args)
    except RuntimeError as exc:
        return "bloqueado" in str(exc).lower() or "desativado" in str(exc).lower()
    return False


def rede_proibida(*args, **kwargs):
    raise AssertionError("tentativa de rede em contrato offline")


C.LLM7_AUTORIZADO = False
C.urllib.request.urlopen = rede_proibida
C._buscar_bytes = rede_proibida
C.ler_remoto = lambda *args, **kwargs: None

provedores = C.montar_provedores()
checar("LLM7 fora da fila por padrão", not any(str(p.get("id", "")).startswith("llm7") for p in provedores))
checar("fallback Pollinations GET fora da fila", not any(p.get("tipo") == "pollinations-get" for p in provedores))
checar("chamada LLM7 direta bloqueada", bloqueia(C._chamar_llm7, {"modelos": ["default"]}, [], ""))
checar("chamada de modelo LLM7 bloqueada", bloqueia(C._chamar_llm7_modelo, {"base": "https://api.llm7.io/v1", "chave": "x"}, [], "", "default"))
checar("rota OpenAI-compatible para LLM7 bloqueada", bloqueia(C._chamar_openai, {"base": "https://api.llm7.io/v1", "chave": "x"}, [], ""))
checar("subdomínio LLM7 também bloqueado", bloqueia(C._chamar_openai, {"base": "https://seguro.llm7.io/v1", "chave": "x"}, [], ""))
checar("GET que expunha mensagem está inerte", bloqueia(C._chamar_pollinations_get, {}, [{"role": "user", "content": "dado-sintetico"}], ""))
fonte_get = inspect.getsource(C._chamar_pollinations_get)
checar("GET removido não monta URL nem busca bytes", "_buscar_bytes" not in fonte_get and "urllib.parse.quote" not in fonte_get)
checar("ferramenta manual TESTAR não chama LLM7", C._ferramenta_testar("https://api.llm7.io/v1 | default").startswith("BLOQUEADO"))
checar("ferramenta PLANTAR não cadastra LLM7", C._ferramenta_plantar("https://api.llm7.io/v1 | default").startswith("BLOQUEADO"))

VARREDURA._catalogo = rede_proibida
VARREDURA.C.ler_remoto = rede_proibida
VARREDURA.C.escrever_remoto = rede_proibida
checar("varredura não consulta nem altera memória", "bloqueada" in VARREDURA.varrer().lower())
checar("coletor não oferece modelos LLM7", not any(p.get("familia") == "llm7" for p in COLHER.poços_sem_chave()))

PROVA.PROVEDORES = [("llm7", "https://api.llm7.io/v1", ["default"], "LLM7_API_KEY")]
PROVA.PROVEDORES_SEM_CHAVE = []
PROVA.C._k = lambda _: "valor-sintetico"
PROVA._bater = rede_proibida
gravacoes = []
PROVA.C.escrever_remoto = lambda *args: gravacoes.append(args) or True
PROVA.disparar()
estado = json.loads(gravacoes[0][1])["provedores"]["llm7"]["estado"]
checar("prova de fogo registra bloqueio sem sondar LLM7", estado == "bloqueado_por_politica")

workflow = Path(".github/workflows/piloto.yml").read_text(encoding="utf-8")
checar("piloto legado sem agenda", "schedule:" not in workflow and "cron:" not in workflow)
checar("piloto exige confirmação humana explícita", "inputs.confirmacao == 'PUBLICAR'" in workflow)
testes_workflow = Path(".github/workflows/testes.yml").read_text(encoding="utf-8")
checar("barreira de contratos também roda em pull requests", "  pull_request:\n" in testes_workflow)

# O opt-in é apenas compatibilidade controlada; o teste não faz chamada real.
C.LLM7_AUTORIZADO = True
optin = C.montar_provedores()
checar("opt-in explícito preserva compatibilidade da fila", any(p.get("id") == "llm7" for p in optin))
C.LLM7_AUTORIZADO = False

falhas = [nome for nome, ok in resultados if not ok]
print(f"\n{len(resultados) - len(falhas)}/{len(resultados)} contratos PASS")
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
