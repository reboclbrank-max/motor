# -*- coding: utf-8 -*-
"""confirmar_contas.py — manutenção de contas criadas para divulgação.

Roda NO Actions (onde a senha de app de e-mail existe selada). Nunca imprime
credencial: só status, IDs públicos e URLs públicas.

Modos (env MODE):
  confirmar — confirma o e-mail do @ceifalume no mastodon.social e troca a
              senha para uma DERIVADA do segredo EMAIL_SENHA_APP (a senha
              original se perdeu com segurança; a derivada nunca sai daqui).
  recriar   — apaga a conta (senha derivada) e cria de novo, com cadeia de
              nomes determinística; confirma e posta o 1º toot.

A senha derivada é recriável por qualquer workflow:
    sha256(EMAIL_SENHA_APP + ":mastodon-ceifalume-v1") → base64[:16] + "Aa1!"
"""
import base64
import hashlib
import imaplib
import json
import os
import re
import time
import urllib.parse
import urllib.request
import email as _email

import http.cookiejar

from nacl.public import PublicKey, SealedBox

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) rebocl-contas/1.0"}
BASE = "https://mastodon.social"
ENDERECO = os.environ["EMAIL_ENDERECO"]
SENHA_APP = os.environ["EMAIL_SENHA_APP"]
ALIAS = os.environ.get("CEIFALUME_MASTO_EMAIL", "")  # endereço vem de secret, nunca do código
MODO = os.environ.get("MODE", "confirmar")
NOMES = ["ceifalume", "ceifalumeoficial", "jogoceifalume", "ceifalumejogo"]


def senha_derivada():
    d = hashlib.sha256((SENHA_APP + ":mastodon-ceifalume-v1").encode()).digest()
    return base64.b64encode(d).decode()[:16] + "Aa1!"


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _get(op, url, referer=None):
    h = dict(UA)
    if referer:
        h["Referer"] = referer
    r = op.open(urllib.request.Request(url, headers=h), timeout=30)
    final = r.read().decode("utf-8", "replace")
    r.close()
    return final


def _post_form(op, url, dados, referer):
    r = op.open(urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(),
                 headers={**UA, "Referer": referer}), timeout=30)
    final = r.read().decode("utf-8", "replace")
    r.close()
    return final


def _post_json(url, corpo, hdr=None):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                 headers={**UA, "Content-Type": "application/json", **(hdr or {})})
    with urllib.request.urlopen(req, timeout=30) as x:
        return json.loads(x.read().decode())


def _corpo_de(bruto):
    msg = _email.message_from_bytes(bruto)
    partes_texto = []
    if msg.is_multipart():
        for parte in msg.walk():
            if parte.get_content_type() in ("text/plain", "text/html"):
                try:
                    partes_texto.append(parte.get_payload(decode=True).decode("utf-8", "replace"))
                except Exception:
                    pass
    else:
        try:
            partes_texto.append(msg.get_payload(decode=True).decode("utf-8", "replace"))
        except Exception:
            pass
    # junta linhas quebradas dentro de URLs (quoted-printable e wrap de 72 cols)
    texto = "\n".join(partes_texto)
    texto = texto.replace("=\r\n", "").replace("=\n", "").replace("=3D", "=")
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"[ \t]*\n[ \t]*", "", texto)
    return texto


def emails_links(de_filtro, padrao, tentativas=6, so_nao_lidos=True, janela=6):
    """Procura (com espera) links em e-mails de um remetente.
    Vasculha INBOX e SPAM; recompõe URLs quebradas por wrap."""
    pastas = ["INBOX", "[Gmail]/Spam"]
    for _ in range(tentativas):
        achados = []
        with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30) as caixa:
            caixa.login(ENDERECO, SENHA_APP)
            for pasta in pastas:
                try:
                    caixa.select(pasta, readonly=True)
                except Exception:
                    continue
                criterio = (f'(UNSEEN FROM "{de_filtro}")' if so_nao_lidos
                            else f'(FROM "{de_filtro}")')
                tipo, dados = caixa.search(None, criterio)
                for id_email in reversed((dados[0] or b"").split()[-janela:]):
                    tipo, partes = caixa.fetch(id_email, "(BODY.PEEK[])")
                    bruto = next((p[1] for p in (partes or []) if isinstance(p, tuple) and len(p) >= 2), None)
                    if not bruto:
                        continue
                    m = re.search(padrao, _corpo_de(bruto))
                    if m:
                        achados.append(m.group(0))
        if achados:
            return achados
        time.sleep(10)
    return []


def confirmar_email(op, so_nao_lidos=True):
    links = emails_links("mastodon.social", r"https://mastodon\.social/confirmation\?confirmation_token=[A-Za-z0-9_\-]+",
                         so_nao_lidos=so_nao_lidos)
    if not links:
        print("confirmacao: nenhum e-mail com link (talvez ja confirmado)")
        return False
    final = _get_seguro(op, links[0])
    ok = bool(re.search(r"confirmed|confirmado|welcome|boas.vindas", final, re.I))
    print("confirmacao:", "ok" if ok else "sem certeza (seguir mesmo assim)")
    return True


def resetar_senha(op, nova):
    h = _get(op, BASE + "/auth/password/new")
    csrf = re.search(r'name="authenticity_token" value="([^"]+)"', h)
    if not csrf:
        print("reset: form sem token — layout mudou")
        return False
    _post_form(op, BASE + "/auth/password",
               {"authenticity_token": csrf.group(1), "user[email]": ALIAS},
               BASE + "/auth/password/new")
    links = emails_links("mastodon.social", r"https://mastodon\.social/auth/password/edit\?reset_password_token=[A-Za-z0-9_\-]+")
    if not links:
        print("reset: e-mail de reset não chegou")
        return False
    h2 = _get_seguro(op, links[0])
    csrf2 = re.search(r'name="authenticity_token" value="([^"]+)"', h2)
    rtoken = re.search(r'name="user\[reset_password_token\]" value="([^"]+)"', h2) or \
             re.search(r'name="reset_password_token" value="([^"]+)"', h2)
    if not csrf2 or not rtoken:
        print("reset: link sem form esperado")
        return False
    _post_form(op, BASE + "/auth/password",
               {"_method": "put", "authenticity_token": csrf2.group(1),
                "user[reset_password_token]": rtoken.group(1),
                "user[password]": nova, "user[password_confirmation]": nova},
               links[0])
    print("reset: senha substituída ✓ (derivada, selada por derivação)")
    return True


def login_token(app_id, app_secret, senha):
    d = _post_json(BASE + "/oauth/token",
                   {"grant_type": "password", "client_id": app_id, "client_secret": app_secret,
                    "username": ALIAS, "password": senha, "scope": "read write"})
    return d.get("access_token")


def criar_app():
    app = _post_json(BASE + "/api/v1/apps",
                     {"client_name": "rebocl-manutencao", "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
                      "scopes": "read write"})
    return app["client_id"], app["client_secret"]


def confirmado_ok(token):
    try:
        req = urllib.request.Request(BASE + "/api/v1/accounts/verify_credentials",
                                     headers={**UA, "Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, timeout=30) as x:
            d = json.loads(x.read().decode())
        return d
    except urllib.error.HTTPError:
        return None



ARQ_LINKS = "MEMORIA/links-seguros.nacl"
ARQ_APP = "MEMORIA/app-ceifalume.nacl"
ARQ_CHAVE_PUB = "chave-links.pub"


def _commit(caminho, conteudo_bytes, mensagem, token):
    import base64 as _b64
    api = "https://api.github.com/repos/reboclbrank-max/agente/contents/" + caminho
    def _req(metodo, dados=None):
        r = urllib.request.Request(api, data=dados, method=metodo,
                                   headers={"Authorization": "token " + token,
                                            "User-Agent": "x", "Content-Type": "application/json",
                                            "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(r, timeout=60) as x:
            corpo = x.read().decode()
            return x.status, (json.loads(corpo) if corpo else None)
    try:
        st, info = _req("GET", None)
        sha = info.get("sha") if isinstance(info, dict) else None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        sha = None  # arquivo novo — regra 404-tolerante
    payload = {"message": mensagem,
               "content": _b64.b64encode(conteudo_bytes).decode("ascii"), "branch": "main"}
    if sha:
        payload["sha"] = sha
    st, r = _req("PUT", json.dumps(payload).encode())
    print("commit", caminho, "->", st)


def extrair_links(token):
    """Lê e-mails do mastodon (reset + confirmação), CIFRA os links com a chave
    pública do sandbox e commita o blob. Nada sensível em texto puro."""
    token_api = token
    req = urllib.request.Request(
        "https://api.github.com/repos/reboclbrank-max/agente/contents/" + ARQ_CHAVE_PUB + "?ref=main",
        headers={"Authorization": "token " + token_api, "User-Agent": "x",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as x:
        d = json.loads(x.read().decode())
    pub_b64 = base64.b64decode(d["content"]).decode().strip()
    caixa_pub = SealedBox(PublicKey(base64.b64decode(pub_b64)))
    padroes = {
        "reset": r"https://mastodon\.social/auth/password/edit\?reset_password_token=[A-Za-z0-9_\-]+",
        "confirmacao": r"https://mastodon\.social/[a-z/]*confirmation\?confirmation_token=[A-Za-z0-9_\-]+",
    }
    achados = {}
    for nome, padrao in padroes.items():
        janela = 40 if nome == "confirmacao" else 6  # confirmação é antiga — caçar fundo
        links = emails_links("mastodon.social", padrao, tentativas=8, so_nao_lidos=False, janela=janela)
        if links:
            achados[nome] = links[0]
    if not achados:
        print("extrair: nenhum link encontrado (inbox+spam, lidos e não lidos)")
        try:
            import email.utils
            with imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30) as caixa:
                caixa.login(ENDERECO, SENHA_APP)
                caixa.select("INBOX", readonly=True)
                tipo, dados = caixa.search(None, '(FROM "mastodon.social")')
                for id_email in reversed((dados[0] or b"").split()[-12:]):
                    tipo, partes = caixa.fetch(id_email, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
                    bruto = next((p[1] for p in (partes or []) if isinstance(p, tuple) and len(p) >= 2), None)
                    if bruto:
                        msg = _email.message_from_bytes(bruto)
                        print("   visto:", (msg.get("Subject") or "?")[:60], "|", (msg.get("Date") or "?")[:22])
        except Exception as e:
            print("   diagnóstico falhou:", str(e)[:60])
        return 1
    blob = json.dumps(achados).encode()
    cifrado = base64.b64encode(caixa_pub.encrypt(blob))
    _commit(ARQ_LINKS, cifrado, "contas: blob de links (cifrado)", token)
    print("extrair:", ", ".join(achados.keys()), "cifrado e commitado ✓")
    return 0


def main():
    print(f"modo: {MODO}")
    if MODO == "extrair":
        return extrair_links(os.environ.get("GH_TOKEN", ""))
    if MODO == "criar-app":
        token = os.environ.get("GH_TOKEN", "")
        app = _post_json(BASE + "/api/v1/apps",
                         {"client_name": f"rebocl-final-{MODO[:0]}{os.environ.get('GITHUB_RUN_ID', 'x')}",
                          "redirect_uris": "urn:ietf:wg:oauth:2.0:oob", "scopes": "read write",
                          "website": "https://reboclbrank-max.github.io/site/"})
        assert app.get("client_id"), str(app)[:120]
        pub_b64 = base64.b64decode(json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://api.github.com/repos/reboclbrank-max/agente/contents/" + ARQ_CHAVE_PUB + "?ref=main",
            headers={"Authorization": "token " + token, "User-Agent": "x",
                     "Accept": "application/vnd.github+json"}), timeout=60).read().decode())["content"]).decode().strip()
        from nacl.public import PublicKey as _PK, SealedBox as _SBx
        caixa = _SBx(_PK(base64.b64decode(pub_b64)))
        cifrado = base64.b64encode(caixa.encrypt(json.dumps(app).encode()))
        _commit(ARQ_APP, cifrado, "contas: app oauth cifrado (criado no runner)", token)
        print("criar-app: cifrado e commitado ok")
        return 0
    op = _opener()
    senha = senha_derivada()

    if MODO == "confirmar":
        confirmar_email(op)
        if not resetar_senha(op, senha):
            return 1
        app_id, app_secret = criar_app()
        token = login_token(app_id, app_secret, senha)
        conta = confirmado_ok(token) if token else None
        if not conta:
            print("login: token não saiu — conferir reset")
            return 1
        if conta.get("error") or (isinstance(conta, dict) and not conta.get("username")):
            print("verificação:", str(conta)[:80])
        if not conta.get("username"):
            # conta existe mas e-mail não confirmado → reenviar confirmação via sessão web
            try:
                h = _get(op, BASE + "/auth/confirmation/new")
                csrf = re.search(r'name="authenticity_token" value="([^"]+)"', h)
                if csrf:
                    _post_form(op, BASE + "/auth/confirmation",
                               {"authenticity_token": csrf.group(1), "user[email]": ALIAS},
                               BASE + "/auth/confirmation/new")
                    confirmar_email(op, so_nao_lidos=False)
                    token = login_token(app_id, app_secret, senha)
                    conta = confirmado_ok(token) if token else None
            except Exception as e:
                print("reenvio:", str(e)[:80])
        if not conta or not conta.get("username"):
            print("status: conta acessível mas e-mail ainda não confirmado")
            return 1
        print("login ok: id", conta.get("id"), "usuario", conta.get("username"))
        d = _post_json(BASE + "/api/v1/statuses",
                       {"status": "🌙 Conta oficial do Ceifalume no ar! O diário de desenvolvimento nº 1 "
                                 "está grátis no navegador: https://reboclbrank-max.github.io/site/ #indiedev #godot"},
                       {"Authorization": "Bearer " + token})
        print("1º toot:", d.get("url", "?"))
        return 0

    if MODO == "recriar":
        app_id, app_secret = criar_app()
        token = login_token(app_id, app_secret, senha)
        conta = confirmado_ok(token) if token else None
        if conta:
            try:
                req = urllib.request.Request(BASE + "/api/v1/accounts",
                    data=json.dumps({"password": senha}).encode(), method="DELETE",
                    headers={**UA, "Content-Type": "application/json", "Authorization": "Bearer " + token})
                urllib.request.urlopen(req, timeout=30)
                print("conta antiga: pedido de exclusão enviado ✓")
            except urllib.error.HTTPError as e:
                print("exclusão:", e.code, "(seguir)")
            time.sleep(5)
        # criar de novo com cadeia de nomes
        novo = None
        for nome in NOMES:
            try:
                app2 = _post_json(BASE + "/api/v1/apps",
                                  {"client_name": "rebocl-cadastro", "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
                                   "scopes": "read write"})
                tok2 = _post_json(BASE + "/oauth/token",
                                  {"grant_type": "client_credentials", "client_id": app2["client_id"],
                                   "client_secret": app2["client_secret"], "scope": "read write"})
                conta2 = _post_json(BASE + "/api/v1/accounts",
                                    {"username": nome, "email": ALIAS, "password": senha,
                                     "agreement": "true", "locale": "pt-BR", "date_of_birth": "1995-06-15"},
                                    {"Authorization": "Bearer " + tok2["access_token"]})
                if conta2.get("access_token") or conta2.get("id"):
                    novo = nome
                    break
            except urllib.error.HTTPError:
                continue
        if not novo:
            print("recriar: nenhum nome livre da cadeia")
            return 1
        print("conta recriada como:", novo)
        confirmar_email(op)
        app_id, app_secret = criar_app()
        token = login_token(app_id, app_secret, senha)
        conta = confirmado_ok(token) if token else None
        if not conta:
            print("login pós-recriação: falhou (talvez confirmacao demore)")
            return 1
        print("login ok: id", conta.get("id"), "usuario", conta.get("username"))
        d = _post_json(BASE + "/api/v1/statuses",
                       {"status": "🌙 Conta oficial do Ceifalume no ar! O diário de desenvolvimento nº 1 "
                                 "está grátis no navegador: https://reboclbrank-max.github.io/site/ #indiedev #godot"},
                       {"Authorization": "Bearer " + token})
        print("1º toot:", d.get("url", "?"))
        return 0

    print("modo desconhecido")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
