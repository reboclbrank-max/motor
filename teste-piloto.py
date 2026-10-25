#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Testa o piloto automático (v3.10): fila, retry, alternância, textos, cadência, estado."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C
import piloto as P

store = {}
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)


def fake_escrever(caminho, conteudo, mensagem=""):
    store[caminho] = conteudo
    return True


C.escrever_remoto = fake_escrever

falhas = {"bluesky": True}


def fake_publicar(item, canais=None):
    return [c for c in (canais or P.CANAIS) if falhas.get(c)]


P.publicar_canais = fake_publicar
P.medir_metricas = lambda: {"ceifalume": {"itch_views": 108, "itch_downloads": 39, "apk": 66},
                            "prancheta": {"itch_views": 14, "itch_downloads": 2, "apk": 12}}
P.publicar_estado = lambda fila=None: store.update({"_estado_publicado": store.get("_estado_publicado", 0) + 1})
P.registrar_metricas_base = lambda m: store.update({"_metricas_registradas": m})
_texto_vivo_real = P.texto_vivo
P.texto_vivo = P.texto_do_dia          # no teste de main: sem rede
_responder_mencoes_real = P.responder_mencoes
P.responder_mencoes = lambda: 0
comentarios = []
C.gh = lambda metodo, caminho, dados=None: [] if "issues?labels" in caminho else {"number": 999}
C.comentar = lambda numero, texto: comentarios.append(texto)
C.ler_avisos = lambda: {"avisos": [{"ativo": True}], "lembretes": [{"feito": False}]}
C.ler_diagnostico = lambda: {"provedores": {}}
C.carregar_placar = lambda: {}

ok = True


def check(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


check("primeiro jogo = ceifalume", P.proximo_jogo() == "ceifalume")
store[P.ARQ_PILOTO_ESTADO] = json.dumps({"ultimo_jogo": "ceifalume"})
check("alterna para prancheta", P.proximo_jogo() == "prancheta")
t1 = P.texto_do_dia("prancheta")
check("texto tem link", "https://rebocl-brank.itch.io/prancheta" in t1)
ids = set()
for _ in range(3):
    ids.add(P.texto_do_dia("prancheta").split("\n")[0][:30])
check("3 textos diferentes", len(ids) == 3)

store.pop(P.ARQ_PILOTO, None)
P.main()
check("desligado: só estado", store.get("_estado_publicado", 0) >= 1 and not store.get(P.ARQ_FILA))

store[P.ARQ_PILOTO] = "ligado\n"
store.pop(P.ARQ_PILOTO_ESTADO, None)
comentarios.clear()
P.main()
fila = json.loads(store.get(P.ARQ_FILA, "[]"))
check("falha parcial → fila + registro", len(fila) == 1 and fila[0]["pendente"] == ["bluesky"]
      and json.loads(store[P.ARQ_PILOTO_ESTADO])["ultimo_jogo"] in ("ceifalume", "prancheta"))
check("resumo na conversa", any("Piloto automático" in c for c in comentarios))
hist = json.loads(store[P.ARQ_PILOTO_ESTADO])["historico"]
check("histórico registra canais_ok=5", hist[-1]["canais_ok"] == 5)

comentarios.clear()
P.main()
check("cadência 20h respeitada", not any("post de hoje" in c for c in comentarios))
fila2 = json.loads(store.get(P.ARQ_FILA, "[]"))
check("retry: tentativa 1, só bluesky", len(fila2) == 1 and fila2[0]["tentativas"] == 1)

falhas.clear()
P.main()
fila3 = json.loads(store.get(P.ARQ_FILA, "[]"))
check("fila esvaziou", len(fila3) == 0)

msg = P.postar_agora("ceifalume")
check("postar_agora ok", "Postei" in msg)
check("postar_agora inválido", "desconhecido" in P.postar_agora("mario"))

est = P.montar_estado([])
for chave in ("atualizado", "piloto", "fila_publicacao", "motores", "cerebro", "metricas", "avisos"):
    check(f"estado tem '{chave}'", chave in est)
check("métricas no estado", est["metricas"]["ceifalume"]["itch_views"] == 108)

msg = C.ferramenta_piloto("ligar")
check("piloto ligar cria arquivo", "MEMORIA/PILOTO.txt" in store and "ligado" in msg)
check("piloto status ligado", "✅ ligado" in C.ferramenta_piloto("status"))
C.gh = lambda metodo, caminho, dados=None: {"sha": "abc"} if metodo == "GET" else {}
check("piloto desligar", "desligado" in C.ferramenta_piloto("desligar"))

# ---- v2: menções + texto vivo ----
from datetime import datetime, timezone
P.texto_vivo = _texto_vivo_real
P.responder_mencoes = _responder_mencoes_real

notifs_bsky = {"notifications": [
    {"reason": "mention", "uri": "at://did:plc:x/app.bsky.feed.post/abc", "cid": "cid1",
     "author": {"handle": "seguidor1"}, "record": {"text": "jogo top demais!"}},
    {"reason": "like", "uri": "at://did:plc:x/app.bsky.feed.post/def", "cid": "cid2",
     "author": {"handle": "reboclbrank.bsky.social"}, "record": {"text": ""}},
]}
notifs_masto = [{"id": 55, "account": {"acct": "amigo@mastodon.social"},
                 "status": {"id": 900, "content": "<p>quero jogar!</p>"}}]
chamadas_http = []


def fake_http(m, url, dados=None, headers=None, tipo="json", timeout=60):
    chamadas_http.append((m, url))
    if "createSession" in url:
        return {"accessJwt": "jwt", "did": "did:plc:x"}
    if "listNotifications" in url:
        return notifs_bsky
    if "getRecord" in url:
        return {"value": {}}
    if "mastodon.social/api/v1/notifications" in url:
        return notifs_masto
    if "createRecord" in url or "statuses" in url:
        return {"uri": "at://x/y"}
    return {}


P._http = fake_http
menc = P.ler_mencoes_bsky("jwt")
check("bsky: 1 menção (like da própria conta ignorado)", len(menc) == 1 and menc[0]["autor"] == "seguidor1")
menc2 = P.ler_mencoes_mastodon()
check("masto: 1 menção, html limpo", len(menc2) == 1 and menc2[0]["texto"] == "quero jogar!")

C.chamar_llm = lambda mensagens, system=None, **kw: ("Valeu demais!", "motor", None)
antes = len(chamadas_http)
check("responder_mencao bsky posta reply", P.responder_mencao(menc[0]) is True and len(chamadas_http) > antes)
check("responder_mencao masto posta reply", P.responder_mencao(menc2[0]) is True)
check("responder_mencao texto curto → False",
      P.responder_mencao({"canal": "mastodon", "texto": "oi", "autor": "x", "status_id": "1"}) is False)

store[P.ARQ_PILOTO_ESTADO] = json.dumps({
    "mencoes_respondidas": [{"dia": C.agora().strftime("%Y-%m-%d"), "id": str(i)} for i in range(10)],
    "mencoes_processadas": []})
check("limite diário de menções (10)", P.responder_mencoes() == 0)

_hora_real = C.agora
C.agora = lambda: datetime(2026, 10, 8, 3, 0, tzinfo=timezone.utc)   # 0h em Brasília
store[P.ARQ_PILOTO_ESTADO] = json.dumps({"mencoes_respondidas": [], "mencoes_processadas": []})
check("fora do horário não responde", P.responder_mencoes() == 0)

C.agora = lambda: datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)  # 12h em Brasília
n = P.responder_mencoes()
check("responde menção nova (bsky + masto)", n == 2)
est2 = json.loads(store[P.ARQ_PILOTO_ESTADO])
check("menção marcada como processada", len(est2["mencoes_processadas"]) == 2)
check("não responde de novo a mesma menção", P.responder_mencoes() == 0)
C.agora = _hora_real

_chamar_llm_mencao = lambda mensagens, system=None, **kw: ("Bastidor novo do jogo hoje!", "motor", None)


def _mock_pensar_bem(pergunta, system=None):
    if "240 caracteres" in pergunta:  # é o prompt do post de marketing
        P.C.chamar_llm = _chamar_llm_mencao  # restaurar para as menções seguintes
        return ("Bastidor novo do jogo hoje! " + P.LINKS["ceifalume"], "comitê: 2 motores + juiz")
    return _chamar_llm_mencao([{"role": "user", "content": pergunta}], system)


C.pensar_bem = _mock_pensar_bem
C.chamar_llm = _chamar_llm_mencao
tv = P.texto_vivo("ceifalume")
check("texto vivo inclui link", "https://rebocl-brank.itch.io/ceifalume" in tv)
banco2 = json.loads(store[P.ARQ_BANCO_TEXTOS])
check("texto vivo guardado no banco", any(v["texto"] == tv for v in banco2["ceifalume"]["vivos"]))
C.chamar_llm = lambda mensagens, system=None, **kw: (None, None, "falhou")
tv2 = P.texto_vivo("prancheta")
check("texto vivo cai no banco se motor falhar", "itch.io/prancheta" in tv2)

est = P.montar_estado([])
check("estado piloto tem historico", "historico" in est["piloto"])
check("estado piloto tem mencoes_hoje", "mencoes_hoje" in est["piloto"])

# ---- v3: saúde dos canais + resumo semanal ----
import os as _os
for _k in ("TUMBLR_CONSUMER_KEY", "TUMBLR_CONSUMER_SECRET", "TUMBLR_REFRESH_TOKEN", "TUMBLR_TOKEN", "TUMBLR_TOKEN_SECRET"):
    _os.environ.setdefault(_k, "fake")
saude = P.saude_canais()
check("saúde: 6 canais ok com http fake", len(saude) == 6 and all(v == "ok" for v in saude.values()))
def _http_erro(*a, **k):
    raise RuntimeError("fora do ar")
P._http = _http_erro
saude2 = P.saude_canais()
check("saúde: tudo erro quando os canais caem", all(v == "erro" for v in saude2.values()))
P._http = fake_http

resumos = []
P.resumo_na_conversa = lambda texto: resumos.append(texto)
P.medir_metricas = lambda: {"ceifalume": {"itch_views": 120, "itch_downloads": 40, "apk": 70},
                            "prancheta": {"itch_views": 20, "itch_downloads": 3, "apk": 13}}
C.carregar_placar = lambda: {"Pollinations (sem chave)": {"rapida": {"ok": 9}}}
store[P.ARQ_PILOTO_ESTADO] = json.dumps({
    "historico": [{"jogo": "ceifalume", "em": "2026-10-08T10:00:00+00:00", "canais_ok": 6}],
    "mencoes_respondidas": [{"dia": C.agora().strftime("%Y-%m-%d"), "id": "x", "canal": "bluesky"}],
    "resumo_semanal_em": ""})
check("resumo semanal gera", P.resumo_semanal() is True)
check("resumo cita posts, menções e métricas",
      "ceifalume" in resumos[-1] and "Menções respondidas" in resumos[-1] and "120 views" in resumos[-1])
check("resumo não repete no mesmo dia", P.resumo_semanal() is False)
est3 = P.montar_estado([])
check("estado piloto tem canais", "canais" in est3["piloto"])

print("\nTESTE PILOTO:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
