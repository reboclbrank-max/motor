#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Varredura de motores: ela mesma caça modelos keyless novos no catálogo do LLM7,
testa um por um, tira os que morreram e PLUGA os vivos na fila (MEMORIA/motores-extras.json).
Semana que vem o catálogo pode ter músculo novo — e ela adota sem ninguém fazer nada."""
import json
import time
import urllib.request

import comum as C

ARQ_EXTRAS = "MEMORIA/motores-extras.json"
CONHECIDOS = {"GLM-5.3-Flash", "gemma4:31b", "codestral-latest", "DeepSeek-V4-Flash-0731"}
MAX_EXTRAS = 10
MAX_TESTES = 40


def _catalogo():
    bruto, _, _ = C._buscar_bytes("https://api.llm7.io/v1/models",
                                  {"Authorization": "Bearer unused", "User-Agent": C.UA_BOT},
                                  limite=200000, timeout=30)
    return [m.get("id") for m in json.loads(bruto.decode("utf-8", "replace")).get("data", []) if m.get("id")]


def _modelo_vivo(modelo):
    corpo = json.dumps({"model": modelo, "messages": [{"role": "user", "content": "diga ok"}],
                        "max_tokens": 8}).encode("utf-8")
    req = urllib.request.Request("https://api.llm7.io/v1/chat/completions", data=corpo,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer unused", "User-Agent": C.UA_BOT})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace"))
    return bool((d.get("choices") or [{}])[0].get("message", {}).get("content"))


def varrer():
    try:
        extras = json.loads(C.ler_remoto(ARQ_EXTRAS, "[]") or "[]")
    except Exception:
        extras = []
    extras = [x for x in extras if isinstance(x, str) and x.strip()]

    # autofecundação/autocura: re-testa os extras atuais, remove os mortos
    extras_vivos = []
    for modelo in extras:
        try:
            if _modelo_vivo(modelo):
                extras_vivos.append(modelo)
            else:
                C.log(f"varredura: extra {modelo} morreu — removendo da fila")
        except Exception:
            extras_vivos.append(modelo)  # em dúvida (rate limit etc.), mantém
        time.sleep(1.0)

    ja = CONHECIDOS | set(extras_vivos)
    vivos, testados = [], 0
    for modelo in _catalogo():
        if modelo in ja or len(vivos) >= 4 or testados >= MAX_TESTES:
            continue
        testados += 1
        try:
            if _modelo_vivo(modelo):
                vivos.append(modelo)
                C.log(f"varredura: motor novo vivo → {modelo}")
        except Exception as e:
            C.log(f"varredura: {modelo} sem resposta ({str(e)[:50]})")
        time.sleep(1.5)

    if not vivos and extras_vivos == extras:
        return "Varredura concluída: nada novo hoje, fila como está."
    novos = (extras_vivos + vivos)[:MAX_EXTRAS]
    C.escrever_remoto(ARQ_EXTRAS, json.dumps(novos, ensure_ascii=False),
                      "varredura: fila de motores atualizada sozinha")
    if vivos:
        try:
            C.notificar("🧠 Ela encontrou motores novos",
                        "A varredura de hoje achou e PLUGOU sozinha na fila: " + ", ".join(vivos),
                        tipo="aviso")
        except Exception as e:
            C.log(f"varredura: aviso falhou ({str(e)[:70]})")
    partes = [f"✅ Varredura: {len(vivos)} motor(es) novo(s) plugado(s): {', '.join(vivos)}" if vivos
              else "✅ Varredura: nenhum motor novo hoje."]
    if extras_vivos != extras:
        partes.append(f"Fila de extras ajustada ({len(extras_vivos)} vivos).")
    return " ".join(partes)


if __name__ == "__main__":
    print(varrer())
