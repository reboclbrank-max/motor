# -*- coding: utf-8 -*-
"""artigo.py — o artigo semanal de bastidores, publicado no Telegraph.

Todo domingo, depois do relatório: ela escreve um devlog curto (com o comitê de
marketing), publica no blog editorial "Rebocl Brank" (Telegraph) e anuncia na
conversa. Mais um palco de divulgação que ELA controla de ponta a ponta —
e mais uma porta de entrada pro site oficial (Google indexa telegra.ph).
"""
import json
import re
import os
import urllib.parse

import comum as C

ARQ_ARTIGOS = "MEMORIA/artigos.json"
SITE = "https://reboclbrank-max.github.io/site/"
MAX_ARTIGOS = 200


def _dividir_artigo(texto):
    """Primeira linha = título; resto = parágrafos limpos (sem markdown)."""
    linhas = (texto or "").strip().splitlines()
    if not linhas:
        return "Bastidores da Rebocl Brank", []
    titulo = linhas[0].lstrip("# ").strip()[:200]
    paragrafos = []
    for p in re.split(r"\n+", "\n".join(linhas[1:])):
        p = p.replace("**", "").replace("#", "").strip()
        if p:
            paragrafos.append(p)
    return titulo or "Bastidores da Rebocl Brank", paragrafos


def _registrar(item):
    registros = C.ler_remoto(ARQ_ARTIGOS, [])
    if isinstance(registros, str):
        try:
            registros = json.loads(registros)
        except Exception:
            registros = []
    registros.append(item)
    registros = registros[-MAX_ARTIGOS:]
    C.escrever_remoto(ARQ_ARTIGOS, json.dumps(registros, ensure_ascii=False, indent=1),
                      f"artigo: {str(item.get('titulo') or item.get('data') or 'novo')[:50]}")
    return registros


def _telegrafo_create_page(token, titulo, paragrafos):
    import urllib.request
    conteudo = [{"tag": "p", "children": [p]} for p in paragrafos]
    if not conteudo:
        conteudo = [{"tag": "p", "children": ["Bastidores em breve."]}]
    dados = urllib.parse.urlencode({
        "access_token": token, "title": titulo, "author_name": "Rebocl Brank",
        "author_url": SITE, "return_content": "false",
        "content": json.dumps(conteudo, ensure_ascii=False)}).encode()
    r = urllib.request.Request("https://api.telegra.ph/createPage", data=dados, headers={
        "User-Agent": "Mozilla/5.0 rebocl-artigo/1.0"})
    with urllib.request.urlopen(r, timeout=60) as x:
        d = json.loads(x.read().decode())
    if not d.get("ok"):
        raise RuntimeError(f"telegra.ph recusou: {str(d.get('error'))[:60]}")
    return d["result"]["url"]


def resumo_na_conversa(texto):
    try:
        from piloto import resumo_na_conversa as _r
        return _r(texto)
    except Exception as e:
        C.log(f"artigo: resumo indisponível ({str(e)[:40]}) — {texto[:80]}")


def criar_artigo():
    """Escreve (comitê) e publica o artigo da semana; devolve a URL pública."""
    from piloto import LINKS, proximo_jogo
    jogo = proximo_jogo()
    nome = "Ceifalume" if jogo == "ceifalume" else "Prancheta"
    system = ("Você é a narradora dos bastidores da Rebocl Brank, estúdio brasileiro "
              "de jogos independentes de terror e futebol.")
    pergunta = (f"Escreva um artigo curto de bastidores (devlog) sobre o jogo {nome} "
                f"({LINKS[jogo]}). PRIMEIRA linha: título chamativo (sem #). Depois, "
                f"4 a 6 parágrafos curtos em PT-BR, tom autêntico de quem constrói o jogo, "
                f"curiosidade em vez de propaganda. Inclua uma linha com o link do site "
                f"oficial: {SITE}. Sem markdown.")
    texto, motor = C.pensar_bem(pergunta, system)
    titulo, paragrafos = _dividir_artigo(texto)
    if SITE not in " ".join(paragrafos):
        paragrafos.append(f"🏠 Conheça o site oficial do estúdio: {SITE}")
    token = (os.environ.get("TELEGRAPH_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("sem TELEGRAPH_TOKEN no ambiente")
    url = _telegrafo_create_page(token, titulo, paragrafos)
    _registrar({"data": C.agora().strftime("%Y-%m-%d"), "jogo": jogo,
                "titulo": titulo, "url": url, "motor": motor})
    resumo_na_conversa(f"📝 **Artigo semanal** publicado no blog editorial: **{titulo}** → {url}")
    return url


def criar_e_divulgar():
    """Cria o artigo semanal e espelha nos palcos keyless (gist, write.as, rentry).
    Falha sozinha por palco — o artigo já estará no Telegraph de qualquer forma."""
    url = criar_artigo()
    try:
        registros = C.ler_remoto(ARQ_ARTIGOS, [])
        ultimo = registros[-1] if isinstance(registros, list) and registros else {}
        titulo = ultimo.get("titulo", "Bastidores da Rebocl Brank")
        corpo = (f"# {titulo}\n\n📖 Artigo completo: {url}\n\n🏠 Site oficial: {SITE}\n"
                 "🌙 Ceifalume — o diário que trabalha sozinho | ⚽ Prancheta — futebol com xG\n"
                 "Grátis, no navegador, em português.\n")
        from divulgacao import publicar_tudo
        links = publicar_tudo(titulo, corpo)
        resumo_na_conversa("📣 Espelhado em: " + ", ".join(links.keys()))
    except Exception as e:
        C.log(f"artigo: espelho falhou ({str(e)[:60]})")
    return url
