#!/usr/bin/env python3
"""Rodízio: espalha as chamadas entre os motores para o limite de um não virar o limite de todos.

POR QUE EXISTE
--------------
A pergunta do dono foi "não tem como ter motor sem limite?". Limite individual não tem como
remover — mas limite é POR MOTOR. Com 11 motores que funcionam, existem 11 baldes
separados. A cadeia antiga tentava sempre o primeiro até ele dar 429, então o balde de um
motor virava o gargalo de todos.

O rodízio faz três coisas:
  1. Escolhe o motor usado há mais tempo (least recently used) — espalha a carga.
  2. Põe em quarentena quem deu 429, com prazo conforme o provedor (janela de cota).
  3. Recoloca na fila quando a quarentena vence — nada fica de fora para sempre.

Não inventa motor: só reordena os que o teste de desafio já aprovou.
"""
import json
import os
import time

ARQ = "MEMORIA/rodizio.json"

# Quanto tempo um motor fica fora depois de 429. Provedor grátis costuma ter janela de
# 1 minuto (por minuto) ou até o dia virar; 90s é o meio-termo que não desperdiça a fila.
QUARENTENA_429 = 90
QUARENTENA_ERRO = 30      # 401/403/400: provavelmente configuração, volta rápido
QUARENTENA_FALHA = 15     # erro de rede: volta logo


def _carregar():
    try:
        with open(ARQ, encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _salvar(d):
    try:
        os.makedirs(os.path.dirname(ARQ) or ".", exist_ok=True)
        with open(ARQ, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def em_quarentena(d, motor_id, agora=None):
    agora = agora or time.time()
    return float((d.get(motor_id) or {}).get("livre_em") or 0) > agora


def marcar_uso(motor_id, erro=None):
    """Registra a tentativa. Sem erro = serviu; com erro = quarentena proporcional."""
    d = _carregar()
    reg = d.setdefault(motor_id, {})
    agora = time.time()
    reg["ultimo_uso"] = agora
    if erro is None:
        reg["ok"] = int(reg.get("ok") or 0) + 1
        reg.pop("quarentena_motivo", None)
    else:
        texto = str(erro)[:160]
        reg["falhas"] = int(reg.get("falhas") or 0) + 1
        reg["quarentena_motivo"] = texto
        if "429" in texto:
            espera = QUARENTENA_429
        elif any(c in texto for c in ("401", "403", "400", "404")):
            espera = QUARENTENA_ERRO
        else:
            espera = QUARENTENA_FALHA
        reg["livre_em"] = agora + espera
    _salvar(d)
    return d


def ordenar(provedores):
    """Reordena: disponíveis primeiro (usados há mais tempo no topo), quarentena no fim."""
    d = _carregar()
    agora = time.time()

    def chave(p):
        reg = d.get(p.get("id"), {})
        em_q = float(reg.get("livre_em") or 0) - agora
        ultimo = float(reg.get("ultimo_uso") or 0)
        return (0 if em_q <= 0 else 1, ultimo)

    return sorted(provedores, key=chave)


def resumo():
    """Quadro para o comando !motores: quem está livre, quem está em quarentena e por quê."""
    d = _carregar()
    agora = time.time()
    livres, presos = [], []
    for motor_id, reg in d.items():
        falta = float(reg.get("livre_em") or 0) - agora
        linha = {"id": motor_id, "ok": reg.get("ok") or 0, "falhas": reg.get("falhas") or 0}
        if falta > 0:
            linha["falta_s"] = int(falta)
            linha["motivo"] = reg.get("quarentena_motivo")
            presos.append(linha)
        else:
            livres.append(linha)
    livres.sort(key=lambda x: x["ok"], reverse=True)
    presos.sort(key=lambda x: x["falta_s"])
    return livres, presos
