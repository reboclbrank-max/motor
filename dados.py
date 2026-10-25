#!/usr/bin/env python3
"""Camada de DADOS: o que a casa sabe, recuperado sem modelo nenhum.

POR QUE EXISTE
--------------
O dono perguntou por que depender de cota e API. Parte da resposta é: não precisa, para
tudo. Um modelo grande sem contexto erra; um modelo pequeno COM o fato certo acerta. E o
fato já está aqui dentro — 59 arquivos de memória, o placar de metas, as medições de cada
canal, o diário do que foi feito.

Esta camada:
  1. LÊ os arquivos da casa (memória + medições).
  2. ACHA os trechos que respondem à pergunta (BM25 simplificado, sem dependência).
  3. Entrega os trechos formatados para entrarem no prompt.

O motor passa a responder com os números reais em vez de inventar. Se não achar nada,
devolve nada — e o chamador segue sem contexto em vez de receber texto inventado.
"""
import math
import os
import re
from collections import Counter

# Palavras que não ajudam a achar nada.
PARADAS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "e", "ou", "que",
    "em", "no", "na", "nos", "nas", "por", "para", "pra", "com", "sem", "as", "ao", "aos",
    "é", "eh", "sao", "são", "ser", "esta", "está", "estou", "foi", "era", "tem", "ter",
    "meu", "minha", "seu", "sua", "ele", "ela", "isso", "isto", "aquilo", "como", "qual",
    "quais", "quanto", "quantos", "quanta", "quantas", "quando", "onde", "porque", "por",
    "sobre", "mais", "menos", "muito", "pouco", "ja", "já", "nao", "não", "sim", "voce",
    "você", "eu", "nos", "nós", "the", "of", "and", "to", "in", "is", "a",
}

# Arquivos que sempre valem a pena olhar (medições e metas).
FONTES_FIXAS = [
    ("site", "posts/placar-metas.md"),
    ("site", "posts/desempenho.md"),
]

MIN_LINHA = 25          # linha curta demais não é fato, é rótulo
MAX_LINHAS = 4000       # teto de segurança
MAX_CONTEXTO = 1100     # caracteres no prompt


def _palavras(texto):
    return [p for p in re.findall(r"[a-zà-ú0-9]{3,}", (texto or "").lower())
            if p not in PARADAS]


def _linhas_da_casa():
    """Devolve [(fonte, linha)] lido dos arquivos locais e das fontes fixas remotas."""
    itens = []
    pastas = ["MEMORIA", "MEMORIA/conversas", "MEMORIA/historico"]
    for pasta in pastas:
        try:
            for nome in sorted(os.listdir(pasta)):
                # SÓ .md: arquivo .json é estado de máquina, não fato para o dono. A issue #42
                # respondeu com um bloco {"itens": [...]} de cache porque eu lia .json aqui.
                if not nome.endswith(".md"):
                    continue
                caminho = os.path.join(pasta, nome)
                try:
                    if os.path.getsize(caminho) > 400_000:
                        continue
                    with open(caminho, encoding="utf-8", errors="replace") as f:
                        for linha in f:
                            linha = linha.strip()
                            if len(linha) < MIN_LINHA or len(linha) > 300:
                                continue
                            # linha de JSON/estrutura não é fato legível
                            if linha[0] in "{[<" or linha.count('"') > 4:
                                continue
                            itens.append((f"{pasta}/{nome}", linha))
                except Exception:
                    continue
        except Exception:
            continue
    # medições que vivem em outro repositório da casa
    try:
        import comum as C
        for repo, caminho in FONTES_FIXAS:
            texto = C.ler_de(repo, caminho, "")
            for linha in (texto or "").splitlines():
                linha = linha.strip()
                if len(linha) >= MIN_LINHA:
                    itens.append((f"{repo}/{caminho}", linha))
    except Exception:
        pass
    return itens[:MAX_LINHAS]


def procurar(pergunta, k=4):
    """Trechos mais relevantes para a pergunta. Vazio quando nada serve."""
    termos = _palavras(pergunta)
    if not termos:
        return []
    itens = _linhas_da_casa()
    if not itens:
        return []
    # IDF: termo que aparece em pouca linha vale mais ("itch", "seguidores")
    docs = [(fonte, linha, Counter(_palavras(linha))) for fonte, linha in itens]
    total = len(docs)
    df = Counter()
    for _, _, cont in docs:
        for t in set(cont):
            df[t] += 1
    pontuados = []
    for fonte, linha, cont in docs:
        pontos, casados = 0.0, set()
        for t in termos:
            if cont.get(t):
                idf = math.log(1 + total / (1 + df[t]))
                pontos += (1 + math.log(cont[t])) * idf
                casados.add(t)
        if pontos <= 0:
            continue
        # exigir mais de um termo casado, OU um termo raro (idf alto)
        raro = any(math.log(1 + total / (1 + df[t])) > math.log(1 + total / 12) for t in casados)
        if len(casados) < 2 and not raro:
            continue
        pontuados.append((pontos, fonte, linha))
    pontuados.sort(reverse=True)
    vistos, saida = set(), []
    for pontos, fonte, linha in pontuados:
        chave = re.sub(r"\W+", "", linha.lower())[:80]
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append((fonte, linha))
        if len(saida) >= k:
            break
    return saida


def montar_contexto(pergunta, k=4):
    """Bloco de contexto para o prompt, ou "" quando não há fato relevante."""
    achados = procurar(pergunta, k=k)
    if not achados:
        return ""
    linhas = ["FATOS DA CASA (lidos dos arquivos agora — use estes números, não invente):"]
    usado = len(linhas[0])
    for fonte, linha in achados:
        curto = linha if len(linha) <= 220 else linha[:217] + "..."
        entrada = f"- [{os.path.basename(fonte)}] {curto}"
        if usado + len(entrada) > MAX_CONTEXTO:
            break
        linhas.append(entrada)
        usado += len(entrada)
    if len(linhas) == 1:
        return ""
    return "\n".join(linhas)


# ------------------------------------------------------------ resposta direta
# Um número medido não deve ser interpretado por modelo. O Qwen 1.5B, recebendo
# "itch: downloads: alvo 100 · observado 45 · falta 55", respondeu "downloads: 100" —
# pegou a meta no lugar da medição. Não é bug do modelo: é pedir leitura de número a quem
# gera linguagem. Quando a pergunta é de consulta, a resposta sai do arquivo, formatada.
RE_CONSULTA = re.compile(
    r"\b(quantos?|quantas?|qual\s+(?:o|a|os|as)\s+\w+|quanto\s+(?:falta|tem|falta)|"
    r"me\s+diz\s+(?:os|as|o|a)\s+n[úu]meros?|n[úu]meros?|placar|metas?)\b",
    re.IGNORECASE)

RE_MEDIDA = re.compile(r"(observado|atual|medido|alvo|falta|total)", re.IGNORECASE)


def resposta_direta(pergunta):
    """Resposta pronta a partir dos arquivos, sem modelo. None quando não é consulta."""
    if not pergunta or len(pergunta) > 300:
        return None
    if not RE_CONSULTA.search(pergunta):
        return None
    achados = procurar(pergunta, k=6)
    uteis = [(f, l) for f, l in achados
             if RE_MEDIDA.search(l) and re.search(r"\d", l)
             and l[0] not in "{[<" and len(l) <= 300 and l.count('"') <= 2]
    if not uteis:
        return None
    linhas = ["**Do que está medido** (lido dos arquivos agora, sem passar por modelo):", ""]
    vistos = set()
    for fonte, linha in uteis:
        limpa = linha.lstrip("-*• ").replace("**", "").strip()
        chave = limpa[:60].lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        linhas.append(f"- {limpa}  ·  _({os.path.basename(fonte)})_")
        if len(linhas) >= 7:
            break
    if len(linhas) <= 2:
        return None
    linhas.append("")
    linhas.append("_Número lido do arquivo da casa. Se faltar alguma coisa, é porque não foi "
                  "medida ainda — e aí eu digo que não sei, em vez de estimar._")
    return "\n".join(linhas)
