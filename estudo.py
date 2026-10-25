#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estudo autodidata (v3.14): todo dia a Assistente Rebocl estuda um tema,
destila lições práticas com o motor e guarda no caderno de estudos (MEMORIA/estudos.md).
Roda no GitHub Actions (cron diário) ou manualmente via dispatch."""
import json
import re

import comum as C

TEMAS = [
    ("marketing-indie", "marketing de jogos indie divulgação itch.io dicas"),
    ("marketing-ganchos", "títulos e ganchos que vendem jogos exemplos"),
    ("design-terror", "design de jogos de terror dread susto ritmo dicas"),
    ("design-sustos", "jump scare e sound design de terror jogos dicas"),
    ("performance-pc-fraco", "otimização performance jogos PC fraco gamedev"),
    ("performance-web", "otimização jogos html5 navegador webgl performance"),
    ("folclore-norte", "folclore brasileiro lendas amazônia boitatá mapinguari"),
    ("folclore-sul", "folclore brasileiro curupira saci cabeça-de-cuia boúna"),
    ("game-feel", "game feel gamedev dicas coyote time juice"),
    ("roteiro-suspense", "como escrever suspense terror roteiro tensão dicas"),
    ("itchio-seo", "itch.io otimizar página do jogo tags descrição dicas"),
    ("comunidade", "como crescer comunidade discord jogo indie dicas"),
    ("pixel-art", "pixel art técnicas iluminação paleta dicas"),
    ("audio-terror", "sound design terror atmosfera áudio jogos dicas"),
    ("level-design", "level design jogos de terror tensão guias dicas"),
    ("game-jams", "game jam dicas participação aprendizado indie"),
    ("devlog", "devlog como escrever divulgar desenvolvimento dicas"),
    ("midia-social", "divulgar jogo indie redes sociais bluesky tiktok dicas"),
    ("narrativa-ambiental", "narrativa ambiental storytelling jogos dicas"),
    ("boss-design", "boss design criar chefes de jogo dicas"),
    ("playtest", "playtest como testar jogo checklist dicas"),
    ("acessibilidade", "acessibilidade em jogos opções legendas dicas"),
    ("monetizacao-gratis", "monetizar jogo indie de graça doações dicas"),
    ("solo-dev", "desenvolvedor solo rotina produtividade gamedev dicas"),
]
def arq_estudo_hoje():
    """Caderno de estudos POR DIA: arquivo novo a cada dia — sem arquivo gigante
    que engasga o GitHub (com ~864 estudos/dia, arquivo único não aguenta)."""
    return "MEMORIA/estudos-" + C.agora().strftime("%d-%m-%Y") + ".md"
ARQ_ESTUDO_ESTADO = "MEMORIA/estudo-estado.json"


def _estado_carregar():
    try:
        return json.loads(C.ler_remoto(ARQ_ESTUDO_ESTADO, "{}") or "{}")
    except Exception:
        return {}


def estudar(tema_pedido=None, forcar=False, pulo=0):
    """Estuda um tema: busca na internet, lê as fontes, destila lições e grava.
    Modo contínuo (forcar=True): ignora o freio de 1 por dia. `pulo` desloca o tema
    para turmas paralelas (workers) estudarem assuntos diferentes ao mesmo tempo."""
    estado = _estado_carregar()
    hoje = C.agora().strftime("%d/%m/%Y")
    if tema_pedido:
        par = next(((k, t) for k, t in enumerate(TEMAS) if t[0] == tema_pedido), None)
        if not par:
            return f"Não conheço o tema '{tema_pedido}'. Temas: " + ", ".join(t[0] for t in TEMAS)
        indice, (nome, consulta) = par
    else:
        if not forcar and estado.get("ultimo_dia") == hoje:
            return f"Hoje já estudei '{estado.get('ultimo_tema', '?')}' — volto amanhã com o próximo tema."
        indice = (int(estado.get("indice", 0)) + int(pulo)) % len(TEMAS)
        nome, consulta = TEMAS[indice]

    try:
        resultados, fonte = C.buscar_web(consulta, 4)
    except Exception as e:
        return f"Busca falhou hoje ({str(e)[:80]}); tento de novo amanhã."
    if not resultados:
        return "A busca não devolveu nada hoje; tento de novo amanhã."

    material = []
    for r in resultados[:3]:
        try:
            texto = C.abrir_url(r["url"], limite_texto=3500)
            if texto and len(texto) > 200:
                material.append(f"### {r['titulo']}\n{texto[:3500]}")
        except Exception as e:
            C.log(f"estudo: página falhou ({r['url'][:50]}): {str(e)[:60]}")
    if not material:
        material.append(C.formatar_busca(resultados, consulta, fonte))

    prompt = (
        f"Estou estudando '{nome}'. Abaixo, material real da internet de hoje.\n\n"
        + "\n\n".join(material)[:9000]
        + "\n\nDestile EXATAMENTE 6 lições PRÁTICAS e específicas (nada genérico) que melhoram meu trabalho: "
          "sou a assistente de uma empresa brasileira solo de jogos de terror, com PC fraco e divulgação em 6 canais. "
          "Formato: só uma lista com '- '. Sem introdução, sem conclusão."
    )
    licoes, motor, _erro = C.chamar_llm([{"role": "user", "content": prompt}])
    if not licoes:
        return "Nenhum motor respondeu hoje para destilar as lições; tento de novo amanhã."
    licoes = C._limpar_pensar(licoes).strip()[:3000]

    fontes_txt = "\n".join(f"- {r['url'][:100]}" for r in resultados[:2])
    C.acrescentar_memoria(
        arq_estudo_hoje(),
        f"## {hoje} — {nome}\n\nFontes:\n{fontes_txt}\n\n{licoes}\n",
        titulo="# Caderno de estudos (ela estuda sozinha na internet todo dia)\n",
    )
    estado.update({"ultimo_dia": hoje, "ultimo_tema": nome, "indice": (indice + 1) % len(TEMAS)})
    try:
        C.escrever_remoto(ARQ_ESTUDO_ESTADO, json.dumps(estado, ensure_ascii=False), "estudo: estado do dia")
    except Exception as e:
        C.log(f"estado do estudo em conflito (turmas paralelas): {str(e)[:70]}")
    return f"✅ Estudei '{nome}' (fonte: {fonte}; motor: {motor}) e guardei as lições no caderno de estudos."


def estudar_caixa():
    """Lê a caixa de entrada dela (Alertas do Google, newsletters) e transforma
    a primeira novidade com link em mais um capítulo do caderno de estudos."""
    try:
        caixa = C.ferramenta_caixa("")
    except Exception as e:
        return f"Caixa indisponível agora ({str(e)[:60]})."
    if "senha de app" in caixa:
        return caixa
    if "sem e-mails novos" in caixa:
        return "📬 Caixa sem novidades hoje — nada para estudar por aqui."
    links = []
    for linha in caixa.splitlines():
        links.extend(re.findall(r"https?://[^\s\)\]]+", linha))
    links = [l for l in links if "google.com" not in l and "gstatic" not in l][:3]
    if not links:
        return "📬 Li a caixa, mas os e-mails novos não tinham link para estudar."
    material, fonte_link = "", ""
    for link in links:
        try:
            texto = C.abrir_url(link, limite_texto=3000)
            if texto and len(texto) > 200:
                material, fonte_link = texto[:3000], link
                break
        except Exception as e:
            C.log(f"caixa-estudo: página falhou ({link[:50]}): {str(e)[:60]}")
    if not material:
        material = caixa[:2000]
        fonte_link = links[0]
    prompt = (
        "Chegou novidade na caixa de entrada da empresa (Alertas do Google/newsletters). "
        "Estou estudando o material abaixo.\n\n" + material
        + "\n\nDestile EXATAMENTE 3 lições PRÁTICAS (lista com '- ', nada mais) para uma empresa "
          "brasileira solo de jogos de terror. Sem introdução, sem conclusão."
    )
    licoes, motor, _erro = C.chamar_llm([{"role": "user", "content": prompt}])
    if not licoes:
        return "Nenhum motor respondeu para destilar a novidade da caixa; amanhã eu tento de novo."
    licoes = C._limpar_pensar(licoes).strip()[:2000]
    C.acrescentar_memoria(
        arq_estudo_hoje(),
        f"## {C.agora().strftime('%d/%m/%Y')} — da caixa do Gmail\n\nFonte: {fonte_link[:100]}\n\n{licoes}\n",
        titulo="# Caderno de estudos (ela estuda sozinha na internet todo dia)\n",
    )
    return f"✅ Estudei a novidade da caixa ({fonte_link[:70]}…) com o motor {motor}."


if __name__ == "__main__":
    print(estudar())
