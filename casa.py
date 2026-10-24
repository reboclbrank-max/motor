#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Casa — o que o Chat passa a saber e a poder fazer (2026-10-24).

POR QUE EXISTE: o Chat respondia sobre resultados da casa **de memória**. Quando o dono
perguntava "está funcionando?", a resposta podia ser plausível e errada. Aqui ficam as
ferramentas que leem o estado REAL medido (o que `site/tools/metricas.py` grava) e as
duas ações que o dono pode mandar executar pelo chat.

REGRAS (não regredir):
  * número só sai daqui se foi lido de um arquivo real; falha de leitura vira
    `NAO_OBSERVAVEL (motivo)` — nunca zero, nunca estimativa;
  * valor de credencial NUNCA aparece; só o NOME das que existem;
  * ação (publicar/medir) só em workflow e repositório da lista fechada;
  * o cache serve para responder rápido sem rede, mas sempre diz QUANDO foi medido.
"""
import json
import os
import re

REPO_SITE = "site"
ARQ_DESEMPENHO = "posts/desempenho.md"
ARQ_PLACAR = "posts/placar-metas.md"
ARQ_LOG = "posts/log.md"
ARQ_METAS = "posts/metas.json"
ARQ_COFRE = "ferramentas/cofare.json"
REPO_COFRE = "base"

CACHE = "MEMORIA/estado-casa.md"

# Lista fechada: o chat não escolhe workflow, ref nem repositório.
ACOES_PERMITIDAS = {
    "publicar": (REPO_SITE, "postagem-diaria.yml", "ciclo de publicação da casa"),
    "diagnosticar": (REPO_SITE, "diagnostico-da-casa.yml", "diagnóstico somente-leitura"),
}

NAO = "NAO_OBSERVAVEL"


# ------------------------------------------------------------------ leitura
def _comum():
    """Importa o comum só quando usado (os testes rodam sem rede e sem token)."""
    import comum  # noqa: PLC0415
    return comum


def ler_repo(repo, caminho, ler_remoto=None):
    """Lê um arquivo de qualquer repositório da casa. Devolve (texto, motivo_da_falha)."""
    try:
        if ler_remoto is None:
            # Lê do repositório certo (site/base), não do repositório das conversas.
            ler_remoto = _comum().ler_de
        if ler_remoto is _comum().ler_de or getattr(ler_remoto, "__name__", "") == "ler_de":
            texto = ler_remoto(repo, caminho, "")
        else:
            texto = ler_remoto(f"{repo}/{caminho}", "")
        return (texto, None) if texto else (None, "arquivo vazio")
    except Exception as e:  # rede, permissão, 404 — tudo é ausência de leitura
        return None, type(e).__name__


# ------------------------------------------------------------- interpretação
def bloco_do_dia(texto, dia=None):
    """Recorta o bloco "## dd/mm/aaaa" mais recente do arquivo de desempenho."""
    if not texto:
        return ""
    partes = re.split(r"^## ", texto, flags=re.M)[1:]
    if not partes:
        return ""
    if dia:
        for p in partes:
            if p.startswith(dia):
                return "## " + p
        return ""
    return "## " + partes[0]


def numeros_do_dia(bloco):
    """Extrai os pares chave=valor da linha em negrito. Não interpreta, só lê."""
    achados = {}
    for chave, valor in re.findall(r"([a-z_]+)=([0-9.]+|NAO_OBSERVAVEL)", bloco or ""):
        achados[chave] = valor
    return achados


def linhas_de_tabela(bloco):
    """Devolve as linhas de tabela markdown do bloco, já em células."""
    linhas = []
    for linha in (bloco or "").splitlines():
        if not linha.strip().startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
        if not celulas or set("".join(celulas)) <= set("-: "):
            continue
        linhas.append(celulas)
    return linhas


def desempenho(texto, dia=None):
    """Resumo do que foi medido no dia: números, tabela por tipo e o que falta."""
    bloco = bloco_do_dia(texto, dia)
    if not bloco:
        return None
    dados = {"dia": bloco.split("\n", 1)[0].replace("## ", "").strip()}
    dados["numeros"] = numeros_do_dia(bloco)
    tabela = linhas_de_tabela(bloco)
    dados["por_tipo"] = []
    for linha in tabela:
        if len(linha) >= 5 and linha[0].lower().startswith(("conteúdo", "comentário", "conteudo", "comentario")):
            dados["por_tipo"].append({"tipo": linha[0], "posts": linha[1], "media": linha[2],
                                      "melhor": linha[3], "sem_retorno": linha[4]})
    for linha in bloco.splitlines():
        if linha.startswith("**Conversa:**") or linha.startswith("**Instagram") or linha.startswith("**YouTube") \
                or linha.startswith("**itch.io:**"):
            dados.setdefault("observacoes", []).append(linha.replace("**", "").strip())
    return dados


def placar(texto):
    """Lê a tabela de metas: alvo, observado, falta, prazo. Linhas viram dicionários."""
    if not texto:
        return None
    linhas = [l for l in linhas_de_tabela(texto) if len(l) >= 6 and l[0].lower() != "meta"]
    metas = [{"meta": l[0], "alvo": l[1], "observado": l[2], "falta": l[3],
              "por_dia": l[4], "status": l[5]} for l in linhas]
    prazo = ""
    for l in texto.splitlines():
        if l.startswith("Prazo:"):
            prazo = l.replace("**", "").strip()
    return {"metas": metas, "prazo": prazo} if metas else None


def ultimo_ciclo(texto):
    """Último ciclo registrado no log do postador: quando e o que cada canal respondeu."""
    if not texto:
        return None
    partes = re.split(r"^## ", texto, flags=re.M)[1:]
    if not partes:
        return None
    bloco = "## " + partes[-1]
    resultado = {"quando": bloco.split("\n", 1)[0].replace("## ", "").strip(), "canais": []}
    for linha in linhas_de_tabela(bloco):
        if len(linha) >= 2 and linha[0].lower() != "canal":
            resultado["canais"].append({"canal": linha[0], "resultado": linha[1]})
    return resultado


def credenciais_presentes(texto_cofre):
    """Só os NOMES das credenciais que existem — nunca os valores."""
    try:
        dados = json.loads(texto_cofre or "{}")
    except ValueError:
        return None
    if not isinstance(dados, dict):
        return None
    return sorted(k for k in dados if not k.startswith("_"))


# ------------------------------------------------------------------ resumo
def _fmt(valor):
    return valor if valor not in (None, "") else NAO


def resumo(desempenho_d, placar_d, ciclo, credenciais, falhas=None):
    """Texto compacto e honesto para o cérebro do chat usar como fonte de verdade."""
    linhas = []
    if desempenho_d:
        n = desempenho_d["numeros"]
        linhas.append(f"### Medição de {desempenho_d['dia']}")
        linhas.append(f"- Bluesky: {_fmt(n.get('bsky_seguidores'))} seguidor(es) · "
                      f"{_fmt(n.get('posts_proprios'))} posts próprios lidos · "
                      f"engajamento médio {_fmt(n.get('eng_medio'))}")
        for t in desempenho_d["por_tipo"]:
            linhas.append(f"- {t['tipo']}: {t['posts']} posts · média {t['media']} · "
                          f"melhor {t['melhor']} · sem retorno {t['sem_retorno']}")
        for obs in desempenho_d.get("observacoes", [])[:4]:
            linhas.append(f"- {obs}")
    else:
        linhas.append(f"### Medição: {NAO} (arquivo de desempenho não lido)")

    if placar_d:
        linhas.append(f"### Metas ({placar_d['prazo'] or 'prazo não definido'})")
        for m in placar_d["metas"]:
            linhas.append(f"- {m['meta']}: alvo {m['alvo']} · observado {m['observado']}"
                          f" · falta {m['falta']} · {m['status']}")
    else:
        linhas.append(f"### Metas: {NAO} (placar não lido)")

    if ciclo:
        linhas.append(f"### Último ciclo publicado ({ciclo['quando']})")
        for c in ciclo["canais"][:8]:
            linhas.append(f"- {c['canal']}: {c['resultado']}")

    if credenciais:
        linhas.append(f"### Credenciais no cofre ({len(credenciais)})")
        linhas.append("- " + ", ".join(credenciais[:14]) + ("…" if len(credenciais) > 14 else ""))

    if falhas:
        linhas.append("### Falhas de leitura")
        for f in falhas:
            linhas.append(f"- {f}")

    return "\n".join(linhas)


def atualizar(ler_remoto=None):
    """Lê tudo e devolve o resumo. Grava cache local quando a leitura funciona."""
    falhas = []

    def pega(repo, caminho):
        texto, erro = ler_repo(repo, caminho, ler_remoto)
        if erro:
            falhas.append(f"{repo}/{caminho}: {erro}")
        return texto

    texto_des = pega(REPO_SITE, ARQ_DESEMPENHO)
    texto_pla = pega(REPO_SITE, ARQ_PLACAR)
    texto_log = pega(REPO_SITE, ARQ_LOG)
    texto_cofre = pega(REPO_COFRE, ARQ_COFRE)
    texto = resumo(desempenho(texto_des), placar(texto_pla), ultimo_ciclo(texto_log),
                   credenciais_presentes(texto_cofre), falhas)
    # Cache só é sobrescrito por leitura completa; leitura parcial não apaga o último bom.
    if not falhas or not ler_cache()[0]:
        gravar_cache(texto)
    return texto


# -------------------------------------------------------------------- cache
def gravar_cache(texto, caminho=None):
    """Guarda o último resumo bom para responder sem rede (e para o prompt do cérebro)."""
    caminho = caminho or CACHE
    try:
        comum = _comum()
        carimbo = comum.agora().strftime("%d/%m/%Y %H:%M")
        corpo = f"<!-- medido em {carimbo} -->\n{texto}\n"
        pasta = os.path.dirname(caminho)
        if pasta and not os.path.isdir(pasta):
            os.makedirs(pasta, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(corpo)
        return caminho
    except Exception:
        return None


def ler_cache(caminho=None):
    """Devolve (texto, quando_foi_medido). Nunca levanta exceção."""
    caminho = caminho or CACHE
    try:
        with open(caminho, encoding="utf-8") as f:
            bruto = f.read()
    except OSError:
        return "", ""
    achado = re.match(r"<!-- medido em ([^>]+) -->\n", bruto)
    if achado:
        return bruto[achado.end():].strip(), achado.group(1).strip()
    return bruto.strip(), ""


# ------------------------------------------------------------------- ações
_PEDIDO_ATUAL = ""

RE_PEDE_PUBLICAR = re.compile(
    r"\b(publica|publicar|publica[çc][ãa]o|posta|postar|poste|dispara o ciclo|roda o ciclo)\b",
    re.IGNORECASE)
RE_NEGA_PUBLICAR = re.compile(r"\b(n[ãa]o\s+(publica|posta|publique|poste)|sem\s+publicar)\b", re.IGNORECASE)


def definir_pedido(texto):
    """Guarda a mensagem do dono desta rodada — a ação é autorizada por ela, não pelo motor."""
    global _PEDIDO_ATUAL
    _PEDIDO_ATUAL = texto or ""
    return _PEDIDO_ATUAL


def pedido_explicito(texto=None):
    """Verdadeiro só quando o DONO pediu publicação/postagem nesta mensagem."""
    texto = _PEDIDO_ATUAL if texto is None else texto
    if not texto or RE_NEGA_PUBLICAR.search(texto):
        return False
    return bool(RE_PEDE_PUBLICAR.search(texto))


def disparar(acao, gh=None):
    """Dispara uma ação da lista fechada e conta o resultado com honestidade."""
    chave = (acao or "").strip().lower()
    if chave not in ACOES_PERMITIDAS:
        return (f"⚠️ Ação desconhecida: `{acao}`. O chat só executa "
                + ", ".join(f"`{k}`" for k in ACOES_PERMITIDAS) + ".")
    # Publicar não é decisão do motor: só sai com pedido explícito do dono na mensagem.
    if chave == "publicar" and not pedido_explicito():
        return ("⛔ Publicação exige pedido explícito do dono na mensagem "
                "(\"publica\", \"posta\", \"roda o ciclo\"). Nada foi disparado.")
    repo, workflow, descricao = ACOES_PERMITIDAS[chave]
    try:
        comum = _comum()
        (gh or comum.gh)("POST", f"/repos/reboclbrank-max/{repo}/actions/workflows/{workflow}/dispatches",
                         {"ref": "main"})
    except Exception as e:
        mensagem = str(e)[:160]
        return (f"⚠️ Não consegui disparar **{descricao}** (`{workflow}`): {mensagem}\n"
                "Isso normalmente é token sem permissão de Actions no repositório `site`.")
    return (f"✅ **{descricao}** disparado (`{repo}/{workflow}`).\n"
            f"Leva alguns minutos. O resultado aparece em "
            f"https://github.com/reboclbrank-max/{repo}/actions — e o próximo `casa:` já mostra os números novos.")


def publicar(gh=None):
    return disparar("publicar", gh)


def diagnosticar(gh=None):
    return disparar("diagnosticar", gh)
