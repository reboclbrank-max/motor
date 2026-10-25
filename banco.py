#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Banco de dados do Assistente Rebocl (v3.7).

Mantém MEMORIA/banco.json sempre atualizado sozinho, sem depender de nenhuma
chave ou serviço pago:

  - clima da cidade do dono (wttr.in, sem chave)
  - cotações dólar/euro (open.er-api.com, sem chave)
  - status dos sites no ar (checagem direta)
  - números das conversas e das execuções (API do GitHub)
  - motores no ar e uso (diagnóstico local)
  - últimas buscas guardadas (cache — funciona mesmo se os buscadores bloquearem)
  - série histórica: 2 dias de clima + cotação (para comparar depois)

Quem atualiza: o vigia (de hora em hora), as rotinas, o comando
`dados:` e o botão "Banco de dados (atualizar agora)" nas Actions.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import comum as C

SITES = [
    ("Site oficial", "https://reboclbrank-max.github.io/site/"),
    ("Prancheta (itch.io)", "https://rebocl-brank.itch.io/prancheta"),
    ("Ceifalume (itch.io)", "https://rebocl-brank.itch.io/ceifalume"),
    ("Chat", "https://reboclbrank-max.github.io/chat/"),
]

MAX_SERIE = 720         # 720 medições de hora em hora ≈ 30 dias (v3.3)
MAX_BUSCAS = 120        # buscas guardadas no cache


def _quando():
    return C.agora().isoformat(timespec="seconds")


# ------------------------------------------------------------------ coleta

def coletar_clima():
    url = "https://wttr.in/" + urllib.parse.quote(C.CIDADE_PADRAO) + "?format=j1&lang=pt"
    bruto, _, _ = C._buscar_bytes(url, {"User-Agent": "curl/8"}, limite=200000, timeout=20)
    d = json.loads(bruto.decode("utf-8", "replace"))
    atual = d["current_condition"][0]
    try:
        desc = atual.get("lang_pt", [{}])[0].get("value") or atual.get("weatherDesc", [{}])[0].get("value", "")
    except Exception:
        desc = atual.get("weatherDesc", [{}])[0].get("value", "")
    hoje = (d.get("weather") or [{}])[0]
    chuvas = [h.get("chanceofrain") for h in (hoje.get("hourly") or []) if h.get("chanceofrain") is not None]
    return {
        "cidade": C.CIDADE_PADRAO,
        "descricao": desc,
        "temp_C": atual.get("temp_C"),
        "sensacao_C": atual.get("FeelsLikeC"),
        "umidade": atual.get("humidity"),
        "vento_kmh": atual.get("windspeedKmph"),
        "min_C": hoje.get("mintempC"),
        "max_C": hoje.get("maxtempC"),
        "chuva_prob": max(chuvas) if chuvas else None,
        "quando": _quando(),
    }


def coletar_cambio():
    url = "https://open.er-api.com/v6/latest/USD"
    bruto, _, _ = C._buscar_bytes(url, {"User-Agent": C.UA_BOT}, limite=120000, timeout=20)
    d = json.loads(bruto.decode("utf-8", "replace"))
    taxas = d.get("rates", {})
    brl, eur = taxas.get("BRL"), taxas.get("EUR")
    return {
        "USD_BRL": round(brl, 4) if brl else None,
        "EUR_BRL": round(brl / eur, 4) if (brl and eur) else None,
        "fonte": "open.er-api.com",
        "fonte_atualizada": d.get("time_last_update_utc"),
        "quando": _quando(),
    }


def coletar_sites():
    saida = {}
    for nome, url in SITES:
        t0 = time.time()
        entrada = {"url": url, "http": None, "ms": None, "no_ar": False}
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", C.UA_NAVEGADOR)
            with urllib.request.urlopen(req, timeout=20) as r:
                entrada["http"] = r.status
                entrada["no_ar"] = 200 <= r.status < 400
        except urllib.error.HTTPError as e:
            entrada["http"] = e.code
            entrada["no_ar"] = e.code < 400
        except Exception as e:
            entrada["erro"] = str(e)[:80]
        entrada["ms"] = int((time.time() - t0) * 1000)
        saida[nome] = entrada
    return saida


def coletar_github(anterior):
    numeros = dict(anterior.get("numeros") or {})
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?state=all&per_page=100") or []
        conversas = [i for i in issues if "pull_request" not in i]
        numeros["conversas"] = len(conversas)
        numeros["conversas_abertas"] = sum(1 for i in conversas if i.get("state") == "open")
        numeros["comentarios"] = sum(i.get("comments", 0) for i in conversas)
    except Exception as e:
        C.log(f"banco: conversas ({e})")
    try:
        runs = C.gh("GET", f"/repos/{C.REPO}/actions/runs?per_page=50") or {}
        lista = runs.get("workflow_runs", [])
        numeros["runs_recentes"] = len(lista)
        numeros["runs_sucesso"] = sum(1 for r in lista if r.get("conclusion") == "success")
        numeros["runs_falha"] = sum(1 for r in lista if r.get("conclusion") == "failure")
    except Exception as e:
        C.log(f"banco: runs ({e})")
    return numeros


def coletar_motores():
    diag = C.ler_diagnostico()
    usos = diag.get("usos", {})
    provedores = diag.get("provedores") or {}
    no_ar = [k for k, v in provedores.items() if isinstance(v, dict) and v.get("ok")]
    tempos = [x.get("s") for x in (diag.get("tempos") or []) if isinstance(x, dict) and isinstance(x.get("s"), (int, float))]
    import statistics
    return {
        "no_ar": no_ar,
        "usos_hoje": usos.get(C.agora().strftime("%Y-%m-%d"), 0),
        "usos_total": sum(usos.values()),
        "saude": diag.get("saude") or {},
        "ultima_falha": diag.get("ultima_falha"),
        "tempo_tipico_s": int(statistics.median(tempos)) if tempos else None,
    }


def coletar_buscas():
    try:
        cache = json.loads(C.ler(C.ARQ_CACHE, "") or "{}")
    except Exception:
        cache = {}
    itens = [{"termo": t, "quando": (d or {}).get("quando")} for t, d in cache.items()]
    itens.sort(key=lambda x: x.get("quando") or "", reverse=True)
    return {"total": len(cache), "ultimas": itens[:10]}


def atualizar_serie(anterior, clima, cambio):
    serie = [p for p in (anterior.get("serie") or []) if isinstance(p, dict)]
    serie.append({"quando": _quando(),
                  "temp_C": (clima or {}).get("temp_C"),
                  "USD_BRL": (cambio or {}).get("USD_BRL")})
    return serie[-MAX_SERIE:]


def arquivar_o_dia(banco):
    """Guarda o dia inteiro em MEMORIA/historico/AAAA-MM-DD.json — para sempre, nunca apagado."""
    try:
        hoje = C.agora().strftime("%Y-%m-%d")
        serie = [p for p in (banco.get("serie") or []) if str(p.get("quando", "")).startswith(hoje)]
        clima = banco.get("clima") or {}
        cambio = banco.get("cambio") or {}
        numeros = banco.get("numeros") or {}
        dados = {
            "dia": hoje,
            "serie": serie,
            "resumo": {
                "temp_min_C": min([p["temp_C"] for p in serie if p.get("temp_C") is not None], default=None),
                "temp_max_C": max([p["temp_C"] for p in serie if p.get("temp_C") is not None], default=None),
                "USD_BRL_inicio": next((p["USD_BRL"] for p in serie if p.get("USD_BRL")), None),
                "USD_BRL_fim": next((p["USD_BRL"] for p in reversed(serie) if p.get("USD_BRL")), None),
                "conversas": numeros.get("conversas"),
                "comentarios": numeros.get("comentarios"),
                "sites_ok": all((v or {}).get("no_ar") for v in (banco.get("sites") or {}).values()),
                "clima_descricao": clima.get("descricao"),
            },
            "atualizado": banco.get("atualizado"),
        }
        C.escrever_remoto(f"MEMORIA/historico/{hoje}.json",
                          json.dumps(dados, ensure_ascii=False, indent=1) + "\n",
                          f"historico: arquivando o dia {hoje}")
        return True
    except Exception as e:
        C.log(f"historico: falha ao arquivar ({e})")
        return False


def contar_dias_arquivados():
    try:
        itens = C.gh("GET", f"/repos/{C.REPO}/contents/MEMORIA/historico") or []
        return sum(1 for i in itens if str(i.get("name", "")).endswith(".json"))
    except Exception:
        return 0


# ------------------------------------------------------------------ atualização

def atualizar(origem="manual", escrever=True):
    """Coleta tudo, atualiza o banco (mantendo o que já havia) e grava no repositório."""
    anterior = C.ler_banco()
    banco = {"atualizado": _quando(), "atualizado_por": origem, "versao": C.VERSAO}
    avisos = []
    for nome, funcao in (("clima", coletar_clima), ("cambio", coletar_cambio), ("sites", coletar_sites)):
        try:
            banco[nome] = funcao()
        except Exception as e:
            C.log(f"banco: {nome} falhou ({e})")
            banco[nome] = anterior.get(nome) or {}
            avisos.append(f"{nome}: {str(e)[:100]}")
    banco["numeros"] = coletar_github(anterior)
    banco["motores"] = coletar_motores()
    banco["buscas"] = coletar_buscas()
    banco["serie"] = atualizar_serie(anterior, banco.get("clima"), banco.get("cambio"))
    banco["historico_dias"] = contar_dias_arquivados()
    if avisos:
        banco["avisos"] = avisos
    if escrever:
        arquivar_o_dia(banco)
        banco["historico_dias"] = contar_dias_arquivados()
        try:
            ok = C.escrever_remoto(C.ARQ_BANCO, json.dumps(banco, ensure_ascii=False, indent=1) + "\n",
                                   f"banco: atualização automática ({origem})")
            C.log(f"banco: gravado={ok} | origem={origem} | clima={banco.get('clima',{}).get('temp_C')}°C "
                  f"| USD={banco.get('cambio',{}).get('USD_BRL')} | avisos={avisos}")
        except Exception as e:
            C.log(f"banco: falha ao gravar ({e})")
    return banco


def principal():
    banco = atualizar(origem=__import__("os").environ.get("BANCO_ORIGEM", "manual"))
    print(C.banco_resumo(banco, completo=True))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
