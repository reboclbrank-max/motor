#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Piloto automático — o assistente posta e mede sozinho (tudo grátis, R$ 0).

Roda a cada 3 h (workflow piloto.yml). Se MEMORIA/PILOTO.txt existir:
  1. tenta publicar o que ficou na fila (retry, máx 5 tentativas por item)
  2. posta 1 vez por dia, alternando Ceifalume e Prancheta, nos 6 canais
  3. mede as métricas e registra na base
  4. posta o resumo na conversa "📋 rotina"
Sempre (ligado ou não): atualiza o estado público em site/estado-ia.json.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import comum as C

ARQ_PILOTO = "MEMORIA/PILOTO.txt"
ARQ_FILA = "MEMORIA/fila-publicacao.json"
ARQ_PILOTO_ESTADO = "MEMORIA/piloto-estado.json"
ARQ_BANCO_TEXTOS = "MEMORIA/banco-textos.json"
REPO_SITE = "reboclbrank-max/site"
REPO_BASE = "reboclbrank-max/base"
ESTADO_SITE = "estado-ia.json"
MAX_TENTATIVAS = 12
HORAS_ENTRE_POSTS = 9  # projeto farol: 2 posts/dia (manhã e noite, jogos alternando)
MAX_MENCOES_DIA = 10          # o piloto responde no máx 10 menções por dia
HORA_MIN_MENCOES, HORA_MAX_MENCOES = 7, 22   # horário de Brasília em que responde menções

SYSTEM_COMUNIDADE = (
    "Você é o assistente oficial da Rebocl Brank nas redes sociais (Bluesky e Mastodon). "
    "Responda a menção do seguidor com simpatia, em português do Brasil, em NO MÁXIMO 200 caracteres. "
    "Nunca prometa brindes, nunca peça dados pessoais, nunca fale de valores. "
    "Se a pessoa falar do jogo, convide para jogar grátis no itch.io. "
    "Se for elogio, agradeça. Se for crítica, seja humilde e ofereça ouvir. "
    "No máximo 1 emoji. Sem hashtags."
)

CANAIS = ["bluesky", "mastodon", "threads", "tumblr", "telegram", "discord"]

TEXTOS_PADRAO = {
    "ceifalume": [
        {"id": "diario", "texto": ("🌙 **Ceifalume** — o diário de desenvolvimento nº 1 está no ar! "
                                   "A fazenda que trabalha sozinha enquanto você dorme, agora com bastidores abertos: {link}\n\n"
                                   "Jogue grátis no navegador. O que você queria ver no próximo diário? 👇 #indiedev #godot #idlegame")},
        {"id": "chuva", "texto": ("🌧️ Dia de chuva no **Ceifalume**: a fazenda continua — plantando, colhendo, entregando. "
                                  "Você só cuida do que dá para ver. Jogue grátis: {link} #indiedev #godot #idlegame")},
        {"id": "dormir", "texto": ("🌙 **Ceifalume**: feche o jogo e vá dormir — a fazenda não para. "
                                   "Quando você volta, tem história nova esperando. Jogue grátis no navegador: {link} #indiedev #godot #idlegame")},
    ],
    "prancheta": [
        {"id": "xg", "texto": ("⚽ **Prancheta**: o placar não conta tudo — o pós-jogo mostra a qualidade de cada chance (xG) "
                               "por origem. Escolher bem vale mais que chutar muito. Jogue grátis: {link} #indiedev #godot #footballmanager")},
        {"id": "decisao", "texto": ("⚽ **Prancheta**: aos 45', o jogo vira. A decisão de segurar ou atacar muda o resultado — "
                                    "e o vestiário sente. Jogue grátis: {link} #indiedev #godot #footballmanager")},
        {"id": "entrevista", "texto": ("⚽ **Prancheta**: depois do apito, a entrevista esquenta (ou esfria) o vestiário. "
                                       "Cada resposta muda o moral do grupo para a próxima partida. Jogue grátis: {link} #indiedev #godot #footballmanager")},
    ],
}
MIDIA = {
    "ceifalume": "https://raw.githubusercontent.com/reboclbrank-max/midia/main/ceifalume/devlog-1-1280x720.png",
    "prancheta": "https://raw.githubusercontent.com/reboclbrank-max/midia/main/prancheta/xg-1280x720.png",
}
LINKS = {
    "ceifalume": "https://rebocl-brank.itch.io/ceifalume",
    "prancheta": "https://rebocl-brank.itch.io/prancheta",
}


# ---------------------------------------------------------------- http básico
def _http(metodo, url, dados=None, headers=None, tipo="json", timeout=60):
    cab = {"User-Agent": "rebocl-piloto/1.0"}
    if headers:
        cab.update(headers)
    corpo = None
    if dados is not None:
        if tipo == "json":
            corpo = json.dumps(dados).encode("utf-8")
            cab["Content-Type"] = "application/json"
        elif tipo == "form":
            corpo = urllib.parse.urlencode(dados).encode("utf-8")
            cab["Content-Type"] = "application/x-www-form-urlencoded"
        elif tipo == "raw":
            corpo = dados
    r = urllib.request.Request(url, data=corpo, headers=cab, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            t = x.read().decode("utf-8", "replace")
            try:
                return json.loads(t) if t else {}
            except json.JSONDecodeError:
                return t
    except urllib.error.HTTPError as e:
        detalhe = ""
        try:
            detalhe = repr(e.read().decode("utf-8", "replace")[:500])
        except Exception:
            pass
        raise RuntimeError(f"{metodo} {url} -> HTTP {e.code}: {detalhe}") from e

def _ler_json_remoto(caminho, padrao):
    bruto = C.ler_remoto(caminho, "")
    if not bruto:
        return padrao
    try:
        return json.loads(bruto)
    except Exception:
        return padrao


def piloto_ligado():
    return bool(C.ler_remoto(ARQ_PILOTO, "").strip())


def salvar_fila(fila):
    C.escrever_remoto(ARQ_FILA, json.dumps(fila, ensure_ascii=False, indent=1),
                      "fila de publicação atualizada")


# ---------------------------------------------------------------- escolha do post
def proximo_jogo():
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    ultimo = est.get("ultimo_jogo")
    return "prancheta" if ultimo == "ceifalume" else "ceifalume"


def texto_do_dia(jogo):
    banco = _ler_json_remoto(ARQ_BANCO_TEXTOS, {})
    usados = banco.get(jogo, {}).get("usados", [])
    disponiveis = [t for t in TEXTOS_PADRAO[jogo] if t["id"] not in usados]
    if not disponiveis:
        usados = []
        disponiveis = TEXTOS_PADRAO[jogo]
    t = disponiveis[int(time.time()) % len(disponiveis)]
    usados.append(t["id"])
    banco.setdefault(jogo, {})["usados"] = usados[-10:]
    C.escrever_remoto(ARQ_BANCO_TEXTOS, json.dumps(banco, ensure_ascii=False), "banco de textos atualizado")
    return t["texto"].format(link=LINKS[jogo])


def montar_item(jogo):
    return {"jogo": jogo, "texto": texto_vivo(jogo), "midia": MIDIA[jogo],
            "tentativas": 0, "criado": C.agora().isoformat(timespec="seconds")}


def registrar_post(item):
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    est["ultimo_jogo"] = item["jogo"]
    est["ultimo_post_em"] = C.agora().isoformat(timespec="seconds")
    hist = est.get("historico", [])
    hist.append({"jogo": item["jogo"], "em": est["ultimo_post_em"],
                 "canais_ok": 6 - len(item.get("pendente", []))})
    est["historico"] = hist[-30:]
    C.escrever_remoto(ARQ_PILOTO_ESTADO, json.dumps(est, ensure_ascii=False, indent=1),
                      "piloto: post registrado")


# ---------------------------------------------------------------- canais
def _facet_link(texto, url):
    i = texto.find(url)
    if i < 0:
        return []
    ini = len(texto[:i].encode("utf-8"))
    fim = ini + len(url.encode("utf-8"))
    return [{"index": {"byteStart": ini, "byteEnd": fim},
             "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]}]


def selar(nome, valor, repo="reboclbrank-max/agente"):
    """Re-sela um secret do repo (auto-cura de tokens rotacionais). Valor nunca ecoa."""
    import base64 as _b
    from nacl import encoding as _enc, public as _pub
    pat = os.environ.get("MARKETING_PAT", "").strip()
    if not pat:
        raise RuntimeError("sem MARKETING_PAT para re-selar")
    r = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
                               headers={"Authorization": "token " + pat, "User-Agent": "x"})
    chave = json.loads(urllib.request.urlopen(r, timeout=60).read().decode())
    caixa = _pub.SealedBox(_pub.PublicKey(chave["key"].encode(), _enc.Base64Encoder()))
    corpo = json.dumps({"encrypted_value": _b.b64encode(caixa.encrypt(str(valor).encode())).decode(),
                        "key_id": chave["key_id"]}).encode()
    r = urllib.request.Request(f"https://api.github.com/repos/{repo}/actions/secrets/{nome}",
                               data=corpo, method="PUT",
                               headers={"Authorization": "token " + pat, "User-Agent": "x",
                                        "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as x:
        return x.status


def _bluesky_safe(texto, url=None):
    """Bluesky aceita no máx 300 graphemes; comitê escreve até 399 chars → 400.
    Corta SEM PREJUDICAR o link (recoloca no fim, intacto)."""
    MAX = 280  # margem sob os 300 graphemes (emojis contam como 1 grapheme, 1+ codepoint)
    if len(texto) <= MAX:
        return texto
    url = url or ""
    sem_link = texto.replace(url, " ").strip() if url and url in texto else texto.strip()
    disponivel = MAX - (len(url) + 1 if url else 0)
    cortado = sem_link[:disponivel].rstrip(" ,.;:!?-…\n")
    return (cortado + " " + url).strip() if url else cortado


def _agora_iso():
    """Timestamp RFC 3339 que o Bluesky aceita: termina em Z, nunca '+00:00Z'."""
    d = C.agora()
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def pub_bluesky(item):
    senha = os.environ.get("BSKY_APP_PASSWORD", "")
    if not senha:
        raise RuntimeError("sem BSKY_APP_PASSWORD")
    ua_bsky = {"User-Agent": UA_BSKY}
    sess = _http("POST", "https://bsky.social/xrpc/com.atproto.server.createSession",
                 {"identifier": os.environ.get("BSKY_HANDLE", "reboclbrank.bsky.social"), "password": senha},
                 ua_bsky)
    jwt, did = sess["accessJwt"], sess["did"]
    time.sleep(6)  # respiro pós-login: sessão->post em <2s é sinal de bot
    img = urllib.request.urlopen(item["midia"], timeout=90).read()
    up = _http("POST", "https://bsky.social/xrpc/com.atproto.repo.uploadBlob", img,
               {"Authorization": "Bearer " + jwt, "Content-Type": "image/png", **ua_bsky}, tipo="raw")
    blob = up["blob"]
    texto_final = _bluesky_safe(item["texto"], LINKS[item["jogo"]])
    rec = {"$type": "app.bsky.feed.post", "text": texto_final,
           "createdAt": _agora_iso(),
           "embed": {"$type": "app.bsky.embed.images", "images": [
               {"image": blob, "alt": "Rebocl Brank — " + item["jogo"]}]}}
    facets = _facet_link(texto_final, LINKS[item["jogo"]])
    if facets:
        rec["facets"] = facets
    cab_bsky = {"Authorization": "Bearer " + jwt, "Accept-Encoding": "identity", **ua_bsky}
    ultimo_erro = None
    for tentativa, com_embed in enumerate([True, True, False]):
        try:
            rec_tent = rec
            if not com_embed and "embed" in rec_tent:
                rec_tent = {k: v for k, v in rec_tent.items() if k != "embed"}
                rec_tent.pop("facets", None)
                rec_tent["text"] = _bluesky_safe(texto_final, LINKS[item["jogo"]])
            _http("POST", "https://bsky.social/xrpc/com.atproto.repo.createRecord",
                  {"repo": did, "collection": "app.bsky.feed.post", "record": rec_tent},
                  cab_bsky)
            ultimo_erro = None
            break
        except Exception as e:
            ultimo_erro = e
            C.log(f"bluesky: tentativa {tentativa + 1} (embed={com_embed}) falhou: {str(e)[:120]}")
            time.sleep(4)
    if ultimo_erro:
        raise ultimo_erro


def _multipart(campos, arquivo_nome, arquivo_bytes, arquivo_tipo):
    boundary = "----rebocl" + hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    partes = []
    for k, v in campos.items():
        partes.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    partes.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                   f"filename=\"{arquivo_nome}\"\r\nContent-Type: {arquivo_tipo}\r\n\r\n").encode()
                  + arquivo_bytes + b"\r\n")
    partes.append(f"--{boundary}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={boundary}"


def pub_mastodon(item):
    token = os.environ.get("MASTODON_TOKEN", "")
    if not token:
        raise RuntimeError("sem MASTODON_TOKEN")
    h = {"Authorization": "Bearer " + token}
    img = urllib.request.urlopen(item["midia"], timeout=90).read()
    corpo, tipo = _multipart({"description": "Rebocl Brank — " + item["jogo"]}, "arte.png", img, "image/png")
    mid = _http("POST", "https://mastodon.social/api/v1/media", corpo, {**h, "Content-Type": tipo}, tipo="raw")
    mid_id = mid.get("id") if isinstance(mid, dict) else None
    dados = {"status": item["texto"], "visibility": "public"}
    if mid_id:
        dados["media_ids[]"] = mid_id
    _http("POST", "https://mastodon.social/api/v1/statuses", dados, h, tipo="form")


def pub_threads(item):
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    user = os.environ.get("THREADS_USER_ID", "")
    if not token or not user:
        raise RuntimeError("sem THREADS_ACCESS_TOKEN/THREADS_USER_ID")
    cont = _http("POST", f"https://graph.threads.net/v1.0/{user}/threads",
                 {"media_type": "IMAGE", "image_url": item["midia"], "text": item["texto"],
                  "access_token": token})
    cid = cont.get("id")
    if not cid:
        raise RuntimeError("threads não devolveu id")
    for _ in range(24):  # o container processa no Meta; publicar antes de FINISHED falha
        time.sleep(4)
        stt = _http("GET", f"https://graph.threads.net/v1.0/{cid}?fields=status&access_token={token}")
        if stt.get("status") == "FINISHED":
            break
        if stt.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError("container " + str(stt.get("status")))
    _http("POST", f"https://graph.threads.net/v1.0/{user}/threads_publish",
          {"creation_id": cid, "access_token": token})


def pub_tumblr(item):
    ck = os.environ.get("TUMBLR_CONSUMER_KEY", "")
    cs = os.environ.get("TUMBLR_CONSUMER_SECRET", "")
    refresh = os.environ.get("TUMBLR_REFRESH_TOKEN", "")
    if not (ck and cs and refresh):
        raise RuntimeError("sem credenciais OAuth2 do Tumblr")
    tok = _http("POST", "https://api.tumblr.com/v2/oauth2/token",
                {"grant_type": "refresh_token", "refresh_token": refresh,
                 "client_id": ck, "client_secret": cs}, tipo="form")
    access = tok.get("access_token")
    if not access:
        raise RuntimeError("tumblr: refresh falhou")
    novo_refresh = tok.get("refresh_token")
    if novo_refresh and novo_refresh != refresh:
        try:
            selar("TUMBLR_REFRESH_TOKEN", novo_refresh)
            C.log("tumblr: refresh rotacionado e RE-SELADO (auto-cura) ok")
        except Exception as e:
            C.log(f"tumblr: re-selada falhou ({str(e)[:50]}) — token atual ainda vale (grace)")
    caption = item["texto"].replace("**", "").replace("\n", "<br>")
    _http("POST", "https://api.tumblr.com/v2/blog/reboclbrank/post",
          {"type": "photo", "source": item["midia"], "caption": caption,
           "tags": "indiedev,godot,jogosbrasileiros", "state": "published"},
          {"Authorization": "Bearer " + access}, tipo="form")


def pub_telegram(item):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    canal = os.environ.get("TELEGRAM_CHANNEL", "@ceifalume")
    if not token:
        raise RuntimeError("sem TELEGRAM_BOT_TOKEN")
    caption = item["texto"].replace("**", "").replace("#", "")
    caption = (caption[:860] + "…") if len(caption) > 860 else caption
    caption += "\n\n🏠 Site oficial da Rebocl Brank: https://reboclbrank-max.github.io/site/"
    _http("POST", f"https://api.telegram.org/bot{token}/sendPhoto",
          {"chat_id": canal, "photo": item["midia"], "caption": caption, "parse_mode": "HTML"})


def pub_discord(item):
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    canal = os.environ.get("DISCORD_CHANNEL_ID", "")
    if not token or not canal:
        raise RuntimeError("sem DISCORD_BOT_TOKEN/DISCORD_CHANNEL_ID")
    desc = item["texto"].replace("**", "") + "\n\n🏠 Site oficial: https://reboclbrank-max.github.io/site/"
    _http("POST", f"https://discord.com/api/v10/channels/{canal}/messages",
          {"embeds": [{"title": ("🌙 Ceifalume" if item["jogo"] == "ceifalume" else "⚽ Prancheta") + " — Rebocl Brank",
                       "description": desc[:1000], "url": LINKS[item["jogo"]],
                       "color": 13906855,
                       "image": {"url": item["midia"]}}]},
          {"Authorization": "Bot " + token})


CANAL_FUNCS = {
    "bluesky": pub_bluesky, "mastodon": pub_mastodon, "threads": pub_threads,
    "tumblr": pub_tumblr, "telegram": pub_telegram, "discord": pub_discord,
}


def publicar_canais(item, canais=None):
    """Publica nos canais (padrão: os 6); devolve a lista dos que falharam."""
    pendente = []
    for canal in (canais or CANAIS):
        try:
            CANAL_FUNCS[canal](item)
            C.log(f"piloto: {canal} ✓ ({item['jogo']})")
            time.sleep(1)
        except Exception as e:
            C.log(f"piloto: {canal} falhou: {str(e)[:100]}")
            pendente.append(canal)
    return pendente


# ---------------------------------------------------------------- métricas
def medir_metricas():
    m = {"ceifalume": {}, "prancheta": {}}
    try:
        chave = os.environ.get("ITCH_API_KEY", "")
        d = _http("GET", "https://api.itch.io/profile/games",
                  headers={"Authorization": f"Bearer {chave}"})
        for g in (d.get("games") or []):
            nome = (g.get("title") or "").lower()
            dados = {"itch_views": g.get("views_count"), "itch_downloads": g.get("downloads_count")}
            if "ceifalume" in nome:
                m["ceifalume"].update(dados)
            if "prancheta" in nome:
                m["prancheta"].update(dados)
    except Exception as e:
        C.log(f"piloto: itch falhou ({e})")
    try:
        rels = _http("GET", "https://api.github.com/repos/reboclbrank-max/site/releases")
        m["ceifalume"]["apk"] = sum(a.get("download_count", 0) for r in rels
                                    for a in r.get("assets", []) if a.get("name") == "ceifalume.apk")
    except Exception:
        pass
    try:
        rels = _http("GET", "https://api.github.com/repos/reboclbrank-max/prancheta/releases?per_page=50")
        m["prancheta"]["apk"] = sum(a.get("download_count", 0) for r in rels
                                    for a in r.get("assets", []) if str(a.get("name", "")).endswith(".apk"))
    except Exception:
        pass
    return m


def _gh_outro_repo(repo, metodo, caminho, dados=None):
    token = os.environ.get("CHAT_TOKEN", "")
    return _http(metodo, f"https://api.github.com/repos/{repo}/{caminho}", dados,
                 {"Authorization": "token " + token, "Accept": "application/vnd.github+json"})


def registrar_metricas_base(m):
    caminhos = {"ceifalume": "projetos/01-ceifalume/marketing/METRICAS.md",
                "prancheta": "projetos/02-prancheta/marketing/METRICAS.md"}
    linha_base = C.agora().strftime("%Y-%m-%d %H:%M")
    for jogo, caminho in caminhos.items():
        try:
            dados = m.get(jogo, {})
            if not dados:
                continue
            partes = [f"{k}={v}" for k, v in dados.items()]
            nota = " | piloto automático: " + " · ".join(partes)
            info = _gh_outro_repo(REPO_BASE, "GET", f"contents/{caminho}?ref=main")
            atual = base64.b64decode(info["content"]).decode("utf-8")
            novo = atual.rstrip("\n") + f"\n| {linha_base} | {nota}\n"
            _gh_outro_repo(REPO_BASE, "PUT", f"contents/{caminho}", {
                "message": f"metricas: piloto ({jogo})",
                "content": base64.b64encode(novo.encode("utf-8")).decode("ascii"),
                "sha": info["sha"], "branch": "main"})
            C.log(f"piloto: métricas registradas ({jogo})")
        except Exception as e:
            C.log(f"piloto: métricas ({jogo}) falharam: {str(e)[:100]}")


# ---------------------------------------------------------------- estado público
def montar_estado(fila):
    motores = []
    try:
        placar = C.carregar_placar()
        diag = C.ler_diagnostico()
        for p in C.montar_provedores():
            est = (diag.get("provedores") or {}).get(p["id"], {})
            motores.append({
                "nome": p["nome"],
                "notas": {cat: C.nota_motor(p["nome"], cat)
                         for cat in ("codigo", "longa", "rapida", "criativa")},
                "ok_total": est.get("ok_total", 0), "falhas_total": est.get("falhas_total", 0),
                "ms_medio": est.get("ms_medio", 0)})
    except Exception as e:
        C.log(f"piloto: estado motores falhou ({e})")
    try:
        entradas = json.loads(C.ler_remoto(C.ARQ_RESPOSTAS, "[]") or "[]")
        cerebro = {"cache_respostas": len(entradas),
                   "ultimas": [{"p": e.get("p", ""), "em": e.get("em", "")} for e in entradas[-3:]]}
    except Exception:
        cerebro = {"cache_respostas": 0, "ultimas": []}
    try:
        av = C.ler_avisos()
        avisos = {"ativos": sum(1 for a in (av.get("avisos") or []) if a.get("ativo")),
                  "lembretes_pendentes": sum(1 for l in (av.get("lembretes") or []) if not l.get("feito"))}
    except Exception:
        avisos = {"ativos": 0, "lembretes_pendentes": 0}
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    ultimo = est.get("ultimo_post_em")
    return {
        "atualizado": C.agora().isoformat(timespec="seconds"),
        "piloto": {"ligado": piloto_ligado(), "ultimo_post": est.get("ultimo_jogo") and {
            "jogo": est.get("ultimo_jogo"), "em": ultimo},
            "historico": (est.get("historico") or [])[-10:],
            "mencoes_hoje": len([m for m in (est.get("mencoes_respondidas") or [])
                                 if m.get("dia") == C.agora().strftime("%Y-%m-%d")]),
            "canais": est.get("saude_canais", {})},
        "fila_publicacao": fila,
        "motores": motores,
        "cerebro": cerebro,
        "metricas": medir_metricas(),
        "avisos": avisos,
    }


def publicar_estado(fila=None):
    if fila is None:
        fila = _ler_json_remoto(ARQ_FILA, [])
    est = montar_estado(fila)
    try:
        info = _gh_outro_repo(REPO_SITE, "GET", f"contents/{ESTADO_SITE}?ref=main")
        sha = info.get("sha")
    except Exception:
        sha = None
    corpo = {"message": "estado da IA atualizado pelo piloto",
             "content": base64.b64encode(json.dumps(est, ensure_ascii=False, indent=1).encode("utf-8")).decode("ascii"),
             "branch": "main"}
    if sha:
        corpo["sha"] = sha
    try:
        _gh_outro_repo(REPO_SITE, "PUT", f"contents/{ESTADO_SITE}", corpo)
        C.log("piloto: estado público atualizado")
    except Exception as e:
        C.log(f"piloto: estado público falhou ({e})")


# ---------------------------------------------------------------- conversa
def resumo_na_conversa(texto):
    try:
        issues = C.gh("GET", f"/repos/{C.REPO}/issues?labels=rotina&state=open") or []
        numero = issues[0]["number"] if issues else None
        if not numero:
            nova = C.gh("POST", f"/repos/{C.REPO}/issues",
                        {"title": "📋 rotina do assistente", "body": "Resumos automáticos.",
                         "labels": ["rotina"]})
            numero = nova["number"]
        C.comentar(numero, texto)
    except Exception as e:
        C.log(f"piloto: resumo na conversa falhou ({e})")


# ---------------------------------------------------------------- comandos do chat
def postar_agora(jogo):
    if jogo not in TEXTOS_PADRAO:
        return "❌ jogo desconhecido (use ceifalume ou prancheta)"
    item = montar_item(jogo)
    pend = publicar_canais(item)
    if pend:
        item["pendente"] = pend
    registrar_post(item)
    if pend:
        fila = _ler_json_remoto(ARQ_FILA, [])
        item["pendente"] = pend
        salvar_fila(fila + [item])
        return (f"📣 Postei **{jogo}** agora nos canais disponíveis. "
                f"Ficou pendente em: {', '.join(pend)} — tento de novo sozinho.")
    return f"📣 Postei **{jogo}** agora nos 6 canais! ✓"


def medir_e_resistrar_texto():
    m = medir_metricas()
    registrar_metricas_base(m)
    ce, pr = m.get("ceifalume", {}), m.get("prancheta", {})
    return (f"📊 **Métricas agora:**\n"
            f"- 🌙 Ceifalume: itch {ce.get('itch_views', '?')} views · {ce.get('itch_downloads', '?')} downloads · APK {ce.get('apk', '?')}\n"
            f"- ⚽ Prancheta: itch {pr.get('itch_views', '?')} views · {pr.get('itch_downloads', '?')} downloads · APK {pr.get('apk', '?')}\n"
            f"Registrado nas METRICAS.md dos dois jogos.")


# ---------------------------------------------------------------- menções (a IA viva)
UA_BSKY = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _bsky_sessao():
    senha = os.environ.get("BSKY_APP_PASSWORD", "")
    sess = _http("POST", "https://bsky.social/xrpc/com.atproto.server.createSession",
                 {"identifier": os.environ.get("BSKY_HANDLE", "reboclbrank.bsky.social"), "password": senha},
                 {"User-Agent": UA_BSKY})
    return sess["accessJwt"], sess["did"]


def _bsky_get_record(jwt, uri):
    partes = uri.replace("at://", "").split("/")
    repo, rkey = partes[0], partes[2]
    d = _http("GET", f"https://bsky.social/xrpc/com.atproto.repo.getRecord"
              f"?repo={repo}&collection=app.bsky.feed.post&rkey={rkey}",
              headers={"Authorization": "Bearer " + jwt})
    return (d.get("value") or {}) if isinstance(d, dict) else {}


def ler_mencoes_bsky(jwt):
    d = _http("GET", "https://bsky.social/xrpc/app.bsky.notification.listNotifications?limit=30",
              headers={"Authorization": "Bearer " + jwt})
    mencoes = []
    for n in (d.get("notifications") or []):
        if n.get("reason") not in ("mention", "reply", "like"):
            continue
        autor = (n.get("author") or {})
        if autor.get("handle") == "reboclbrank.bsky.social":
            continue
        mencoes.append({"canal": "bluesky", "tipo": n.get("reason"),
                        "id": (n.get("uri") or "") + (n.get("cid") or ""),
                        "uri": n.get("uri") or "", "cid": n.get("cid") or "",
                        "autor": autor.get("handle", ""), "texto": (n.get("record") or {}).get("text", "")})
    return mencoes


def ler_mencoes_mastodon():
    token = os.environ.get("MASTODON_TOKEN", "")
    d = _http("GET", "https://mastodon.social/api/v1/notifications?types[]=mention&limit=30",
              headers={"Authorization": "Bearer " + token})
    mencoes = []
    if not isinstance(d, list):
        return mencoes
    for n in d:
        conta = (n.get("account") or {})
        if conta.get("acct") in ("ReboclBrank@mastodon.social", "ReboclBrank"):
            continue
        conteudo = re.sub(r"<[^>]+>", "", (n.get("status") or {}).get("content", ""))
        mencoes.append({"canal": "mastodon", "tipo": "mention", "id": str(n.get("id")),
                        "status_id": str((n.get("status") or {}).get("id", "")),
                        "autor": conta.get("acct", ""), "texto": conteudo.strip()})
    return mencoes


def responder_mencao(mencao):
    texto = (mencao.get("texto") or "")[:400]
    if not texto or len(texto) < 3:
        return False
    conversa = [{"role": "user", "content": f"@{mencao['autor']} disse: {texto}\n\n"
                                           f"Responda como a conta oficial da Rebocl Brank."}]
    resposta, _motor, _e = C.chamar_llm(conversa, SYSTEM_COMUNIDADE)
    if not resposta:
        return False
    resposta = resposta.strip().strip('"').strip("'")[:280]
    if not resposta:
        return False
    if mencao["canal"] == "bluesky":
        jwt, did = _bsky_sessao()
        rec = _bsky_get_record(jwt, mencao["uri"])
        if mencao.get("tipo") == "reply" and isinstance(rec.get("reply"), dict):
            parent = {"uri": mencao["uri"], "cid": mencao["cid"]}
            root = rec["reply"].get("root", parent)
        else:
            parent = {"uri": mencao["uri"], "cid": mencao["cid"]}
            root = parent
        record = {"$type": "app.bsky.feed.post", "text": _bluesky_safe(f"@{mencao['autor']} {resposta}"),
                  "createdAt": _agora_iso(),
                  "reply": {"root": root, "parent": parent}}
        _http("POST", "https://bsky.social/xrpc/com.atproto.repo.createRecord",
              {"repo": did, "collection": "app.bsky.feed.post", "record": record},
              {"Authorization": "Bearer " + jwt, "User-Agent": UA_BSKY})
    else:
        token = os.environ.get("MASTODON_TOKEN", "")
        _http("POST", "https://mastodon.social/api/v1/statuses",
              {"status": f"@{mencao['autor']} {resposta}", "in_reply_to_id": mencao.get("status_id"),
               "visibility": "unlisted"},
              {"Authorization": "Bearer " + token}, tipo="form")
    return True


def responder_mencoes():
    """Lê menções novas no Bluesky/Mastodon e responde sozinho (com limites)."""
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    processadas = set(est.get("mencoes_processadas", []))
    hoje = C.agora().strftime("%Y-%m-%d")
    respondidas_hoje = [m for m in est.get("mencoes_respondidas", []) if m.get("dia") == hoje]
    if len(respondidas_hoje) >= MAX_MENCOES_DIA:
        return 0
    hora_br = (C.agora().hour - 3) % 24  # Brasília = UTC-3
    if not (HORA_MIN_MENCOES <= hora_br <= HORA_MAX_MENCOES):
        return 0
    mencoes = []
    try:
        jwt, _did = _bsky_sessao()
        mencoes += ler_mencoes_bsky(jwt)
    except Exception as e:
        C.log(f"piloto menções bsky: {e}")
    try:
        mencoes += ler_mencoes_mastodon()
    except Exception as e:
        C.log(f"piloto menções masto: {e}")
    tentativas = est.get("mencoes_tentativas", {})
    novas = [m for m in mencoes if m["id"] not in processadas
             and int(tentativas.get(m["id"], 0)) < 3]
    if not novas:
        return 0
    respondidas = 0
    for m in novas[:MAX_MENCOES_DIA - len(respondidas_hoje)]:
        try:
            if responder_mencao(m):
                processadas.add(m["id"])
                respondidas_hoje.append({"dia": hoje, "id": m["id"], "canal": m["canal"]})
                respondidas += 1
                tentativas.pop(m["id"], None)
                C.log(f"piloto: respondi menção ({m['canal']}, @{m['autor']})")
                time.sleep(2)
        except Exception as e:
            tentativas[m["id"]] = int(tentativas.get(m["id"], 0)) + 1
            C.log(f"piloto: falha ao responder menção (tentativa {tentativas[m['id']]}/3, novo IP na próxima run): {str(e)[:180]}")
    est["mencoes_tentativas"] = {k: v for k, v in tentativas.items() if v < 3}
    est["mencoes_processadas"] = list(processadas)[-200:]
    est["mencoes_respondidas"] = respondidas_hoje[-50:]
    C.escrever_remoto(ARQ_PILOTO_ESTADO, json.dumps(est, ensure_ascii=False, indent=1),
                      "piloto: menções atualizadas")
    return respondidas


def texto_vivo(jogo):
    """Marketing com COMITÊ: 2 motores escrevem versões, um juiz escolhe e melhora;
    o comitê criativo (regras de terror/marketing destiladas por IA sênior no manual)
    participa junto. Se o comitê falhar, cai para 1 motor; depois no banco fixo."""
    nome = "Ceifalume" if jogo == "ceifalume" else "Prancheta"
    manual = C.ler("MEMORIA/manual.md")
    dica_marketing = ""
    if "Marketing" in manual:
        trecho = manual.split("Marketing", 1)[1][:600]
        dica_marketing = "Regras da casa: " + re.sub(r"\s+", " ", trecho)[:400]
    prompt = (f"Escreva um post curto para redes sociais (máx 240 caracteres, pt-BR, no máximo 1 emoji, "
              f"2 hashtags no final) sobre o jogo {nome} da Rebocl Brank. "
              f"Tom: bastidor de desenvolvimento, empolgado mas honesto. {dica_marketing} "
              f"Varie o ângulo a cada post.")
    try:
        texto, _motor = C.pensar_bem(prompt, "Você é o redator das redes sociais da Rebocl Brank.")
        if texto:
            texto = texto.strip().strip('"')
            if LINKS[jogo] not in texto:
                texto = texto + " " + LINKS[jogo]
            if 40 < len(texto) < 400:
                banco = _ler_json_remoto(ARQ_BANCO_TEXTOS, {})
                vivos = banco.setdefault(jogo, {}).setdefault("vivos", [])
                vivos.append({"id": "vivo-" + C.agora().strftime("%d%H%M%S"), "texto": texto.strip()})
                banco[jogo]["vivos"] = vivos[-20:]
                C.escrever_remoto(ARQ_BANCO_TEXTOS, json.dumps(banco, ensure_ascii=False),
                                  "banco: texto vivo guardado")
                return texto.strip()
    except Exception as e:
        C.log(f"piloto: comitê de marketing falhou ({str(e)[:80]}) — tento 1 motor simples")
        try:
            texto, _m, _e = C.chamar_llm([{"role": "user", "content": prompt}],
                                         "Você é o redator das redes sociais da Rebocl Brank.")
            if texto:
                texto = texto.strip().strip('"')
                if LINKS[jogo] not in texto:
                    texto = texto + " " + LINKS[jogo]
                if 40 < len(texto) < 400:
                    return texto.strip()
        except Exception as e2:
            C.log(f"piloto: 1 motor também falhou ({e2})")
    return texto_do_dia(jogo)


# ---------------------------------------------------------------- pacote Instagram (fantasma-escritor)
def pacote_instagram():
    """Instagram sem quebrar regra nenhuma: ela escreve a legenda (comitê) e gera a arte,
    e envia TUDO pronto para o dono publicar com 2 toques (login automático no Instagram
    bane conta nova — o fantasma-escritor dá o mesmo resultado sem risco)."""
    jogo = proximo_jogo()
    nome = "Ceifalume" if jogo == "ceifalume" else "Prancheta"
    legenda = texto_vivo(jogo)
    arte = ""
    try:
        retorno = C.ferramenta_imagem(f"arte promocional do jogo {nome}, terror brasileiro, atmosfera sombria, pixel art")
        m = re.search(r"\((https://[^)]+)\)", retorno)
        if m:
            arte = m.group(1)
    except Exception as e:
        C.log(f"instagram: arte falhou ({str(e)[:60]})")
    corpo = ("📦 PACOTE INSTAGRAM PRONTO — publique você (2 minutos, sem risco de ban):\n\n"
             "1. Baixe a imagem: " + (arte or "(arte falhou — use um print do jogo)") +
             "\n2. Cole esta legenda:\n\n---\n" + legenda.replace("**", "") +
             "\n---\n\n3. Horários de pico: 12h ou 19h (Brasil). "
             "Hashtags extras se quiser: #jogobrasileiro #indiehorror #terror")
    C.ferramenta_email("📦 Pacote Instagram pronto (Rebocl Brank) | " + corpo)
    return f"📦 Pacote Instagram enviado por e-mail ({nome}, com legenda do comitê" + (" e arte gerada)" if arte else ")")


# ---------------------------------------------------------------- saúde dos canais
def saude_canais():
    """Testa 1 chamada leve por canal; devolve {canal: 'ok'|'erro'}."""
    saude = {}
    testes = [
        ("bluesky", lambda: _bsky_sessao()),
        ("mastodon", lambda: _http("GET", "https://mastodon.social/api/v1/accounts/verify_credentials",
                                    headers={"Authorization": "Bearer " + os.environ.get("MASTODON_TOKEN", "")})),
        ("telegram", lambda: _http("GET", f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN', '')}/getMe")),
        ("discord", lambda: _http("GET", "https://discord.com/api/v10/users/@me",
                                  headers={"Authorization": "Bot " + os.environ.get("DISCORD_BOT_TOKEN", "")})),
        ("threads", lambda: _http("GET", f"https://graph.threads.net/v1.0/me?access_token={os.environ.get('THREADS_ACCESS_TOKEN', '')}")),
        ("tumblr", lambda: _http("POST", "https://api.tumblr.com/v2/oauth2/token",
                                 {"grant_type": "refresh_token",
                                  "refresh_token": os.environ.get("TUMBLR_REFRESH_TOKEN", ""),
                                  "client_id": os.environ.get("TUMBLR_CONSUMER_KEY", ""),
                                  "client_secret": os.environ.get("TUMBLR_CONSUMER_SECRET", "")},
                                 tipo="form")),
    ]
    for nome, fn in testes:
        try:
            fn()
            saude[nome] = "ok"
        except Exception:
            saude[nome] = "erro"
    return saude


def _dias_atras(data_str):
    try:
        d = datetime.strptime(str(data_str), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return 999


def resumo_semanal():
    """Roda 1× por semana (domingo, piloto ligado): a IA conta o que fez sozinha."""
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    if est.get("resumo_semanal_em") == C.agora().strftime("%Y-%m-%d"):
        return False
    semana = (est.get("historico") or [])[-7:]
    mencoes = [m for m in (est.get("mencoes_respondidas") or []) if _dias_atras(m.get("dia", "")) <= 7]
    m = medir_metricas()
    placar = C.carregar_placar()
    top = sorted(placar.items(),
                 key=lambda x: -sum(v.get("ok", 0) for v in x[1].values()))[:3]
    linhas = ["🗓️ **Resumo semanal da IA** (trabalhei sozinho esta semana):"]
    if semana:
        linhas.append("- Posts: " + " · ".join(
            f"{'🌙' if h['jogo'] == 'ceifalume' else '⚽'} {h['jogo']} ({h.get('canais_ok', 6)}/6 canais)"
            for h in semana))
    else:
        linhas.append("- Posts: nenhum esta semana")
    linhas.append(f"- Menções respondidas nas redes: {len(mencoes)}")
    ce, pr = m.get("ceifalume", {}), m.get("prancheta", {})
    linhas.append(f"- Métricas: Ceifalume {ce.get('itch_views', '?')} views / {ce.get('itch_downloads', '?')} dl · "
                  f"Prancheta {pr.get('itch_views', '?')} views / {pr.get('itch_downloads', '?')} dl")
    if top:
        linhas.append("- Motores que mais me ajudaram: " + ", ".join(
            f"{nome} ({sum(v.get('ok', 0) for v in dados.values())} respostas)" for nome, dados in top))
    resumo_na_conversa("\n".join(linhas))
    est["resumo_semanal_em"] = C.agora().strftime("%Y-%m-%d")
    C.escrever_remoto(ARQ_PILOTO_ESTADO, json.dumps(est, ensure_ascii=False, indent=1),
                      "piloto: resumo semanal")
    return True


# ---------------------------------------------------------------- main
def main():
    C.log("piloto: acordou")
    fila = _ler_json_remoto(ARQ_FILA, [])
    publicar_estado(fila)
    if not piloto_ligado():
        C.log("piloto: desligado — só atualizei o estado público")
        return 0

    # 1. fila primeiro (retry)
    if fila:
        ainda = []
        for item in fila:
            pend = publicar_canais(item, canais=item.get("pendente") or CANAIS)
            item["tentativas"] = item.get("tentativas", 0) + 1
            if pend:
                item["pendente"] = pend
                if item["tentativas"] < MAX_TENTATIVAS:
                    ainda.append(item)
                else:
                    C.log(f"piloto: desisti do item após 5 tentativas ({item['jogo']})")
            else:
                item.pop("pendente", None)
                registrar_post(item)
        salvar_fila(ainda)
        fila = ainda

    # 2. post do dia (1 por dia, alternando)
    est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
    ultimo_iso = est.get("ultimo_post_em")
    pode_postar = True
    if ultimo_iso:
        try:
            ultimo_dt = datetime.fromisoformat(ultimo_iso.replace("Z", "+00:00"))
            pode_postar = (datetime.now(timezone.utc) - ultimo_dt).total_seconds() >= HORAS_ENTRE_POSTS * 3600
        except Exception:
            pode_postar = True
    if pode_postar:
        jogo = proximo_jogo()
        item = montar_item(jogo)
        pend = publicar_canais(item)
        if pend:
            item["pendente"] = pend
            salvar_fila(fila + [item])
        registrar_post(item)
        resumo_na_conversa(f"🤖 **Piloto automático** — post de hoje ({jogo}) publicado"
                           + (f"; pendente em: {', '.join(pend)} (tento de novo já já)." if pend
                              else " nos 6 canais ✓"))
    else:
        C.log("piloto: post de hoje já foi")

    # 2b. a IA fica viva: responde menções nas redes (Bluesky + Mastodon)
    try:
        n_mencoes = responder_mencoes()
        if n_mencoes:
            resumo_na_conversa(f"💬 **Piloto:** respondi {n_mencoes} menção(ões) hoje nas redes.")
    except Exception as e:
        C.log(f"piloto: menções falharam ({e})")

    # 2c. saúde dos canais (1× por dia) + resumo semanal (domingo, 1× por semana)
    try:
        if (est.get("ultima_saude") or "")[:10] != C.agora().strftime("%Y-%m-%d"):
            est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})  # recarrega — o post do dia grava depois
            est["saude_canais"] = saude_canais()
            est["ultima_saude"] = C.agora().isoformat(timespec="seconds")
            C.escrever_remoto(ARQ_PILOTO_ESTADO, json.dumps(est, ensure_ascii=False, indent=1),
                              "piloto: saúde dos canais")
    except Exception as e:
        C.log(f"piloto: saúde dos canais falhou ({e})")
    try:
        if (est.get("ultimo_pacote_ig") or "")[:10] != C.agora().strftime("%Y-%m-%d"):
            msg_ig = pacote_instagram()
            est = _ler_json_remoto(ARQ_PILOTO_ESTADO, {})
            est["ultimo_pacote_ig"] = C.agora().isoformat(timespec="seconds")
            C.escrever_remoto(ARQ_PILOTO_ESTADO, json.dumps(est, ensure_ascii=False, indent=1),
                              "piloto: pacote instagram do dia")
            C.log("piloto: " + msg_ig)
    except Exception as e:
        C.log(f"piloto: pacote instagram falhou ({str(e)[:80]})")
    if C.agora().weekday() == 6:  # domingo
        try:
            resumo_semanal()
        except Exception as e:
            C.log(f"piloto: resumo semanal falhou ({e})")

    # 3. mede e registra
    m = medir_metricas()
    registrar_metricas_base(m)

    # 4. estado de novo
    publicar_estado()
    C.log("piloto: fim da execução")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
