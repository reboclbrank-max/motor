#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vitrine: põe os canais parados para trabalhar SEM publicar.

Os quatro robôs que ficaram de fora do port (bom-dia/Instagram, marketing/Bluesky,
eco-devlog/itch, teste-tumblr) existiam para postar. Publicar exige pedido explícito do
dono, então aqui eles fazem a parte útil e segura:

1. **conferir** cada credencial com uma chamada SOMENTE DE LEITURA (quem sou eu?);
2. **escrever o rascunho** do post do dia com o cérebro da casa;
3. **guardar** tudo em fila, marcado "aguardando pedido do dono".

Nada é enviado para fora. A única coisa que sai daqui é leitura de identidade e o texto
salvo na própria memória. Publicar é outro comando, e só com ordem.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

import comum as C

ARQ = "MEMORIA/vitrine.json"
LIMITE = {"instagram": 900, "itch": 1200, "tumblr": 1200, "bluesky": 280}


def _http(metodo, url, cabeceras=None, corpo=None, timeout=30):
    """Chamada crua com resposta curta. Nunca levanta: devolve (ok, texto)."""
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cabeceras or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.read().decode("utf-8", "replace")[:400]
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except Exception as e:
        return False, str(e)[:150]


def _confere_instagram():
    """GET /me no Graph: confirma token e conta, sem publicar nada."""
    token, uid = os.environ.get("IG_TOKEN", "").strip(), os.environ.get("IG_USER_ID", "").strip()
    if not token or not uid:
        return "ausente", "IG_TOKEN/IG_USER_ID não configurados"
    url = ("https://graph.facebook.com/v21.0/" + urllib.parse.quote(uid)
           + "?fields=username&access_token=" + urllib.parse.quote(token))
    ok, txt = _http("GET", url)
    if ok and "username" in txt:
        return "vivo", f"conta @{txt.split('username')[1].split(':')[1].strip(' \"}')[:40]}"
    return "falhou", txt


def _confere_itch():
    """GET /profile/me na API v1 do itch: valida a chave sem criar nada."""
    chave = os.environ.get("ITCH_API_KEYS", "").strip()
    if not chave:
        return "ausente", "ITCH_API_KEYS não configurada"
    chave = chave.split(",")[0].strip()
    # Endpoint real do itch é /api/1/<chave>/me; api.itch.io devolve 404 ("invalid api
    # endpoint"). Com chave boa volta "user"; com chave ruim volta {"errors":["invalid key"]}.
    ok, txt = _http("GET", "https://itch.io/api/1/" + urllib.parse.quote(chave) + "/me")
    if ok and '"user"' in txt:
        return "vivo", "chave aceita pela API do itch"
    if "invalid key" in txt:
        return "falhou", "chave recusada pelo itch (invalid key)"
    return "falhou", txt


def _confere_telegram():
    """getMe: barato, 1 chamada, confirma o bot que entrega o boletim."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return "ausente", "TELEGRAM_BOT_TOKEN não configurado"
    ok, txt = _http("GET", f"https://api.telegram.org/bot{token}/getMe")
    if ok and '"ok":true' in txt.replace(" ", ""):
        return "vivo", "bot responde ao getMe"
    return "falhou", txt


def _confere_youtube():
    """Channels.list da própria conta: leitura, sem upload."""
    chave = os.environ.get("YT_API_KEY", "").strip()
    if not chave:
        return "ausente", "YT_API_KEY não configurada"
    # mine=true só funciona com OAuth de usuário; a chave de API valida em endpoint
    # público. Sem isso o teste reprovava chave boa com 401.
    ok, txt = _http("GET", "https://www.googleapis.com/youtube/v3/videos?part=id"
                          "&chart=mostPopular&maxResults=1&key=" + urllib.parse.quote(chave))
    if ok:
        return "vivo", "chave aceita (leitura pública)"
    return "falhou", txt


CANDEIROS = {
    "instagram": _confere_instagram,
    "itch": _confere_itch,
    "telegram": _confere_telegram,
    "youtube": _confere_youtube,
}


def conferir():
    """Confere todos os canais conhecidos. Devolve {canal: (estado, detalhe)}."""
    resultado = {}
    for nome, funcao in CANDEIROS.items():
        try:
            resultado[nome] = funcao()
        except Exception as e:
            resultado[nome] = ("falhou", str(e)[:120])
        C.log(f"vitrine: {nome} → {resultado[nome][0]}")
    return resultado


def _assunto_do_dia():
    """Puxa do que a casa já sabe: estado da casa e últimas lições. Sem inventar número."""
    pedacos = []
    try:
        estado = C.ler_remoto("MEMORIA/estado-casa.md", "")
        for l in estado.splitlines():
            if l.strip().startswith(("- ", "# ")):
                pedacos.append(l.strip("- ").strip())
    except Exception:
        pass
    try:
        licoes = C.ler_remoto(C.ARQ_LICOES, "")
        for l in licoes.splitlines()[-12:]:
            if l.strip().startswith("- "):
                pedacos.append(l.strip("- ")[:160])
    except Exception:
        pass
    return pedacos[:14]


def _rascunho(canal, pistas, vivo):
    """Escreve o post do dia com o cérebro. Sem motor vivo, devolve aviso claro."""
    limite = LIMITE.get(canal, 900)
    system = (f"Você escreve posts curtos para {canal}. Português do Brasil, direto, sem "
              "inventar número, sem prometer o que não foi feito. Devolva só o texto do post.")
    base = ("Fatos de hoje na casa (use só o que estiver aqui):\n- " + "\n- ".join(pistas[:10])
            if pistas else "Nenhum fato novo registrado.")
    pedido = (f"{base}\n\nEscreva um post para {canal}, de até {limite} caracteres, sobre o que foi feito hoje. "
              "Se não houver fato novo, escreva uma nota curta de bastidor.")
    try:
        texto, modelo, erro = C.chamar_llm([{"role": "user", "content": pedido}], system=system)
    except Exception as e:
        return "", f"cérebro falhou: {str(e)[:80]}"
    if not texto:
        return "", f"sem motor vivo: {str(erro)[:80]}"
    texto = texto.strip().strip('"')
    if len(texto) > limite:
        texto = texto[:limite - 1].rstrip() + "…"
    return texto, f"escrito por {modelo}"


def montar():
    """Confere canais + monta a fila de rascunhos. Não publica nada."""
    canais = conferir()
    pistas = _assunto_do_dia()
    try:
        fila = json.loads(C.ler_remoto(ARQ, "{}") or "{}")
    except Exception:
        fila = {}
    rascunhos = fila.get("rascunhos") or {}
    hoje = C.agora().strftime("%Y-%m-%d") if hasattr(C, "agora") else "hoje"

    novos = 0
    for canal, (estado, detalhe) in canais.items():
        if estado == "ausente":
            continue  # canal sem credencial aqui: não há o que rascunhar
        texto, como = _rascunho(canal, pistas, estado == "vivo")
        if not texto:
            C.log(f"vitrine: sem rascunho para {canal} ({como})")
            continue
        rascunhos[canal] = {
            "dia": hoje,
            "texto": texto,
            "como": como,
            "canal": estado,
            "estado": "rascunho — aguardando pedido do dono",
        }
        novos += 1

    C.escrever_remoto(ARQ, json.dumps({
        "quando": hoje,
        "canais": {k: {"estado": v[0], "detalhe": v[1]} for k, v in canais.items()},
        "rascunhos": rascunhos,
        "regra": "Nada é publicado por este robô. Publicar exige pedido explícito do dono.",
    }, ensure_ascii=False), "vitrine: canais conferidos e rascunhos do dia na fila")

    vivos = sum(1 for e, _ in canais.values() if e == "vivo")
    return (f"🖼️ Vitrine: {vivos}/{len(canais)} canais respondem · "
            f"{novos} rascunho(s) na fila · nada publicado.")


if __name__ == "__main__":
    print(montar())
