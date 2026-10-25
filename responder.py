#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assistente Rebocl — v3.1 (blindado). Responde as conversas do repositório.

Garantias desta versão:
  - NUNCA fica em silêncio: qualquer falha vira uma resposta explicando (com caminho de volta).
  - NUNCA responde duas vezes: cada resposta leva uma marca invisível (dedupe).
  - Sem motor nenhum? Ainda responde o que der com as próprias ferramentas (modo direto).
  - Motores: cadeia com troca automática + duas passadas + reservas sem chave.
  - Reprocessamento: o vigia (sentinela) pode disparar a resposta de uma mensagem específica.
"""
import json
import os
import re
import sys
import time

import comum as C

MARCA_ABERTURA = "<!--resp:"
MARCA_EMERGENCIA = "<!-- rebocl-emergencia -->"
MAX_RESUMO = 160


def eh_resposta_emergencia(corpo, login):
    """Só a resposta marcada e publicada pela conta do dono é recuperação local.

    O marcador sozinho não autoriza descartar uma mensagem: alguém poderia digitá-lo
    por acidente ou de propósito. A interface web publica pelo PAT do dono.
    """
    return login == C.DONO_GITHUB and (corpo or "").lstrip().startswith(MARCA_EMERGENCIA)


def ler_evento():
    caminho = os.environ.get("GITHUB_EVENT_PATH", "")
    if caminho and os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return C.json.load(f)
    return {}


def evento_de_texto(texto, numero, marca):
    """Junta o texto e a informação de rastreio (dedupe)."""
    return {"texto": texto, "numero": numero, "marca": marca}


def do_evento():
    evento = ler_evento()
    nome = os.environ.get("GITHUB_EVENT_NAME", "")
    issue = evento.get("issue") or {}
    comentario = evento.get("comment") or {}

    # reprocessamento disparado pelo vigia
    repro_issue = os.environ.get("REPROCESSAR_ISSUE", "").strip()
    repro_comentario = os.environ.get("REPROCESSAR_COMMENT", "").strip()
    if repro_issue and repro_comentario:
        num = int(repro_issue)
        dados = C.gh("GET", f"/repos/{C.REPO}/issues/comments/{repro_comentario}")
        corpo = (dados.get("body") or "").strip()
        login = (dados.get("user") or {}).get("login")
        if login == "github-actions[bot]" or eh_resposta_emergencia(corpo, login):
            return None
        return {"texto": corpo or "(mensagem vazia)", "numero": num,
                "marca": f"c{repro_comentario}", "origem": "reprocessamento"}

    if nome == "issues" and evento.get("action") == "opened":
        return {"texto": (issue.get("body") or "").strip() or "(conversa iniciada sem texto)",
                "numero": issue.get("number"), "marca": f"a{issue.get('number')}", "origem": "nova conversa"}
    if nome == "issue_comment":
        autor = comentario.get("user") or {}
        if autor.get("type") == "Bot" or autor.get("login") == "github-actions[bot]":
            return None
        corpo_txt = (comentario.get("body") or "").strip()
        if corpo_txt.startswith("[sync-local]") or eh_resposta_emergencia(corpo_txt, autor.get("login")):
            return None  # sync local ou recuperação marcada do navegador — já é resposta, não pergunta
        return {"texto": corpo_txt, "numero": issue.get("number"),
                "marca": f"c{comentario.get('id')}", "origem": "comentário"}
    return None


def ja_respondida(numero, marca):
    """Verdadeiro quando a resposta para esta mensagem já existe (evita duplicatas)."""
    alvo = MARCA_ABERTURA + marca + "-->"
    try:
        comentarios = C.gh("GET", f"/repos/{C.REPO}/issues/{numero}/comments?per_page=100") or []
    except Exception as e:
        C.log(f"dedupe: não consegui conferir ({e})")
        return False
    return any(alvo in (c.get("body") or "") for c in comentarios)


def responder(numero, texto, marca, extra=""):
    """Publica sempre — com rodapé e marca invisível de dedupe."""
    corpo = f"{C.ASSINATURA}\n\n{texto}"
    if extra:
        corpo += f"\n\n---\n{extra}"
    corpo += f"\n\n{MARCA_ABERTURA}{marca}-->"
    C.comentar(numero, corpo)


def ajuda():
    return (
        "**Motores disponíveis (" + str(len(C.montar_provedores())) + " robôs na casa):** "
        + " · ".join(p["nome"] for p in C.montar_provedores()[:8])
        + (" … +" + str(len(C.montar_provedores()) - 8) if len(C.montar_provedores()) > 8 else "") + "\n\n"
        "**Como falar comigo:** mande uma mensagem normal (pesquiso, gero imagem, vejo o clima… quando precisar).\n\n"
        "| Comando | O que faz |\n|---|---|\n"
        "| `pesquisar: termo` | busca na internet |\n"
        "| `abrir: url` | lê uma página (HTML ou PDF; usa o arquivo se estiver fora do ar) |\n"
        "| `arquivo: url` | lê a versão arquivada de uma página (Internet Archive) |\n"
        "| `cep: 00000-000` | endereço a partir do CEP |\n"
        "| `feriados: [ano]` | feriados nacionais |\n"
        "| `clima: [cidade]` | clima agora (padrão: sua cidade) |\n"
        "| `cambio: [moeda]` | cotação (padrão USD) |\n"
        "| `noticias: [termo]` | manchetes |\n"
        "| `hora: [fuso]` | hora em outro lugar |\n"
        "| `youtube: url` | dados de um vídeo |\n"
        "| `imagem: descrição` | gera uma imagem |\n"
        "| `verificar: url` | confere se um site está no ar |\n"
        "| `memoria: termo` | procura na memória |\n"
        "| `dados:` | mostra o banco de dados (atualiza na hora) |\n"
        "| `banco: termo` | procura no banco (clima, cotações, buscas guardadas) |\n"
        "| `placar:` | painel: motores, velocidade, uso, banco |\n"        "| `janelas:` | 📊 histórico de caçadas: IPs sorteados, vivos, fila |\n"        "| `cacar:` | 🏹 dispara a caça de motores AGORA (IP novo) |\n"        "| `pagos:` | 💳 mapa dos motores pagos (o que uma chave destrava) |\n"
        "| `modomaximo: pergunta` | 🏛 COMITÊ TOTAL: todos os motores ao mesmo tempo + juiz |\n"
        "| `melhorias:` | lista o que o vigia anotou para consertar |\n"
        "| `panorama:` / `resumir:` | panorama geral da memória (gera de novo agora) |\n"
        "| `avise quando: o dólar passar de 6` | cria um aviso automático (cotação, clima, site, página, notícia) |\n"
        "| `avisos:` / `avisos: apagar 2` | lista / cancela os avisos |\n"
        "| `vigiar: https://…` | avisa quando a página mudar |\n"
        "| `lembrete: pagar a conta \\| amanhã 9h` | marca um lembrete |\n"
        "| `lembretes:` / `lembretes: apagar 3` | lista / cancela lembretes |\n"
        "| `aviso teste:` | testa se os avisos chegam em você |\n"
        "| `anotar: texto` / `lembrar: fato` | grava na memória |\n"
        "| `/status` | motores + uso + banco |\n\n"
        "_Todos os comandos funcionam mesmo se os motores estiverem fora do ar._"
    )


def status():
    linhas = C.testar_provedores()
    diag = C.ler_diagnostico()
    usos = diag.get("usos", {})
    hoje = C.agora().strftime("%Y-%m-%d")
    corpo = ["**Motores:**", ""]
    corpo += ["- " + l for l in linhas]
    corpo += ["", f"**Uso:** {usos.get(hoje, 0)} hoje · {sum(usos.values())} no total (30 dias)."]
    saude = diag.get("saude", {})
    if saude:
        corpo.append(f"**Saúde:** {saude.get('estado','?')} (desde {saude.get('desde','?')})")
    try:
        dados_avisos = C.ler_avisos()
        n_ativos = len([a for a in dados_avisos.get("avisos", []) if a.get("ativo")])
        n_lembretes = len([l for l in dados_avisos.get("lembretes", []) if not l.get("feito")])
        if n_ativos or n_lembretes:
            corpo.append(f"**🔔 Avisos:** {n_ativos} ativo(s) · **⏰ Lembretes:** {n_lembretes} pendente(s) "
                         "— veja com `avisos:`")
    except Exception as e:
        C.log(f"status avisos: {e}")
    if diag.get("ultima_falha"):
        f = diag["ultima_falha"]
        corpo.append(f"**Última falha de motor:** {f.get('quando','?')[:16]} — `{f.get('erro','?')[:120]}`")
    banco = C.ler_banco()
    if banco:
        corpo.append(f"**🗄 Banco de dados:** atualizado {str(banco.get('atualizado','?'))[:16].replace('T',' ')} UTC "
                     f"(por {banco.get('atualizado_por','?')}) — use `dados:` para ver tudo")
    else:
        corpo.append("**🗄 Banco de dados:** ainda vazio (atualiza sozinho de hora em hora; ou use `dados:`)")
    return "\n".join(corpo)


def janelas_cmd():
    """Diário de caçadas: cada linha = 1 IP sorteado pelo GitHub."""
    try:
        conteudo = C.ler("MEMORIA/janelas.md", "")
    except Exception:
        conteudo = ""
    linhas = [l.strip() for l in (conteudo or "").splitlines()
              if l.strip().startswith("|") and "---" not in l]
    dados = linhas[1:][-12:]
    if not dados:
        return ("**📊 Diário de janelas:** ainda vazio — a primeira caçada com o diário "
                "grava a 1ª linha (a cada caçada entra 1 linha: 4 por dia).")
    total_caçadas = len(linhas) - 1
    corpo = ["**📊 Diário de janelas** — cada linha = 1 caçada = 1 IP novo sorteado:", "",
             "| hora UTC | catalogados | llm7 vivos | keyless abertos | fila acumulada |",
             "|---|---|---|---|---|"] + dados
    corpo += ["", f"**{total_caçadas} caçadas registradas** · a fila é acumulativa (só cresce) · "
              f"caça roda 4×/dia (06:00, 12:00, 18:30 e agora também a cada guarda de 6 h)."]
    return "\n".join(corpo)


def pensar_bem_com_ferramentas(resposta, numero, motor_nome):
    """Se o 'pensar bem' devolveu marcadores [[...]], EXECUTA (o sistema faz a requisição,
    não a IA) e pede a versão final — até 3 rodadas de ferramenta."""
    usos = []
    for _ in range(3):
        m = C.RE_FERRAMENTA.search(resposta or "")
        if not m:
            break
        tipo, argumento = m.group(1).upper(), m.group(2).strip()
        try:
            resultado = C.executar_ferramenta(tipo, argumento)
        except Exception as e:
            resultado = f"A ferramenta falhou: {str(e)[:150]}"
        usos.append(f"{tipo.lower()}: {argumento[:50]}")
        try:
            novo, motor2, _e = C.chamar_llm(
                [{"role": "user", "content": (
                    resposta + f"\n\n[resultado da ferramenta {tipo}]\n{str(resultado)[:4000]}\n\n"
                    "Continue: se precisar de MAIS UMA ferramenta, escreva o próximo marcador numa linha; "
                    "se não, responda o dono de forma final e completa (sem citar marcadores).")}],
                C.montar_system(numero))
        except Exception:
            break
        if not novo:
            break
        resposta, motor_nome = novo, (motor2 or motor_nome)
    return C.RE_FERRAMENTA.sub("", resposta or "").strip(), motor_nome, usos


def cacar_cmd():
    """Dispara a caça de motores AGORA — o GitHub sorteia um IP novo."""
    try:
        C.gh("POST", f"/repos/{C.REPO}/actions/workflows/caca-motores.yml/dispatches", {"ref": "main"})
        return ("🏹 **Caçada disparada!** O GitHub sorteia um IP novo e sonda todos os motores "
                "(~4 min). Depois digite `janelas:` pra ver o que o IP novo trouxe.")
    except Exception as e:
        return f"⚠️ Não consegui disparar a caçada agora: `{str(e)[:120]}`"


def local_cmd(pergunta):
    """Responde usando SÓ o motor local (roda na CPU do runner, sem chave e sem cota).

    Serve para dois fins: quando o dono quer garantir que nenhuma API foi chamada, e para
    medir a qualidade do modelo local com pergunta de verdade.
    """
    pergunta = (pergunta or "").strip()
    if not pergunta:
        return "Me diga a pergunta: `!local: por que o céu é azul?`"
    try:
        import time as _t
        import motor_local as _ml
        if not _ml.disponivel():
            return ("O motor local não está pronto nesta execução "
                    f"(`{_ml.info()['motivo']}`). Ele é preparado pelo workflow do chat; "
                    "se a instalação falhou, o Chat segue com os motores da nuvem.")
        # Modelo pequeno é gerador de LINGUAGEM, não fonte de FATO: o 1.5B afirmou que a
        # pressão é menor ao nível do mar. Por isso os fatos da casa entram antes, e a
        # instrução proíbe completar número de cabeça.
        contexto = ""
        try:
            import dados as _d
            contexto = _d.montar_contexto(pergunta)
        except Exception:
            pass
        pedido = (contexto + "\n\nPergunta do dono: " + pergunta) if contexto else pergunta
        sistema = ("Responda em português do Brasil, direto. Use SOMENTE os fatos fornecidos "
                   "quando eles existirem; não invente número. Se não souber, diga que não sabe.")
        t0 = _t.time()
        texto, motivo = _ml.responder(pedido, sistema)
        dur = _t.time() - t0
        if not texto:
            return f"O motor local não respondeu ({motivo})."
        return f"{texto}\n\n---\n_(💻 motor local · {dur:.0f}s · sem chave, sem API, sem cota)_"
    except Exception as e:
        return f"⚠️ motor local falhou: `{str(e)[:160]}`"


def motores_cmd():
    """Mostra quais motores REALMENTE pensam, medidos pelo desafio — não por HTTP 200."""
    diag = C.ler_diagnostico()
    estados = diag.get("provedores", {})
    if not estados:
        return ("Nenhum teste ainda. Rode o workflow **motores** "
                "(Actions → *motores (teste de verdade)* → Run workflow) e eu mostro aqui.")
    ultimo = diag.get("ultimo_teste", {})
    vivos = [(k, v) for k, v in estados.items() if v.get("cerebro")]
    mortos = [(k, v) for k, v in estados.items() if v.get("cerebro") is False]
    linhas = ["**Motores — medidos pelo desafio** (conta verificável, não HTTP 200)", ""]
    if ultimo.get("quando"):
        linhas.append(f"Último teste: {str(ultimo['quando'])[:16].replace('T', ' ')}")
        linhas.append("")
    linhas.append(f"**Pensam: {len(vivos)}**")
    for k, v in sorted(vivos, key=lambda kv: kv[1].get("ms_ultimo") or 99999)[:10]:
        acertos = v.get("acertos_cerebro")
        testes = v.get("testes_cerebro")
        extra = f" · cérebro {acertos}/{testes}" if acertos is not None else ""
        linhas.append(f"- `{k}` — {v.get('ms_ultimo', '?')} ms{extra}")
    if mortos:
        linhas.append("")
        linhas.append(f"**Não pensam: {len(mortos)}**")
        for k, v in mortos[:10]:
            linhas.append(f"- `{k}` — {str(v.get('erro') or 'falhou')[:60]}")
    try:
        import motor_local as _ml
        _i = _ml.info()
        estado = "pronto" if _i["pronto"] else f"não pronto ({_i['motivo']})"
        linhas.append("")
        linhas.append(f"**Motor local (roda no próprio runner, sem cota): {estado}**")
        if _i["mb"]:
            linhas.append(f"- `{_i['arquivo']}` — {_i['mb']} MB · medido a 26 tok/s "
                          f"(~11 s para 300 tokens)")
        linhas.append("- entra quando todos os remotos falham; não substitui a conta, "
                      "que continua saindo de código")
    except Exception:
        pass
    linhas.append("")
    linhas.append("_Um motor só entra aqui se acertar a conta do desafio. Endpoint que devolve "
                  "texto fixo é reprovado, mesmo respondendo 200._")
    return "\n".join(linhas)


def pagos_cmd():
    """Mapa dos motores pagos (401) — o que uma chave do dono destrava."""
    try:
        pagos = json.loads(C.ler("MEMORIA/motores-pagos.json", "[]") or "[]")
    except Exception:
        pagos = []
    if not pagos:
        return ("**💳 Mapa de pagos:** ainda vazio — a próxima caçada registra os motores "
                "que deram 401 (pagos). O 2º strike seguido os aposenta do catálogo.")
    amostra = ", ".join("`" + p + "`" for p in pagos[:12])
    return (f"**💳 Mapa de pagos: {len(pagos)} motores** que existem mas exigem chave "
            f"(aposentados do catálogo no 2º strike para não desperdiçar sonda)." + chr(10) + chr(10)
            + f"Destraváveis com UMA chave grátis (llm7 token, Groq, Airforce): "
            + amostra + ("…" if len(pagos) > 12 else "") + chr(10) + chr(10)
            + "_Lista completa: `MEMORIA/motores-pagos.json` no repositório `agente`._")


# ------------------------------------------------------------- rede de segurança

RE_COMANDO_SOLTO = re.compile(r"^\s*(anotar|lembrar)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def executar_comandos_soltos(resposta):
    """Se o motor escreveu 'anotar: ...'/'lembrar: ...' como texto (em vez do marcador),
    executa de verdade e troca a linha pela confirmação. Nada se perde."""
    achados = RE_COMANDO_SOLTO.findall(resposta or "")
    if not achados:
        return resposta, []

    def trocar(m):
        verbo, conteudo = m.group(1).lower(), m.group(2).strip()
        conteudo = conteudo.strip("“”\"' “”")
        try:
            if verbo == "anotar":
                C.acrescentar_memoria(C.ARQ_ANOT, f"- **{C.agora().strftime('%d/%m/%Y %H:%M')}** — {conteudo}",
                                      titulo="# Anotações da memória (via chat)\n")
                return f"✅ Anotado: “{conteudo[:200]}”"
            C.acrescentar_memoria(C.ARQ_LONGA, f"- ({C.agora().strftime('%d/%m/%Y')}) {conteudo}",
                                  titulo="# Memória longa — fatos e preferências\n")
            return f"✅ Guardei na memória longa: “{conteudo[:200]}”"
        except Exception as e:
            return f"⚠️ Não consegui guardar isso agora (`{str(e)[:120]}`)"

    usos = [f"{v.lower()}: {c.strip()[:50]}" for v, c in achados[:2]]
    return RE_COMANDO_SOLTO.sub(trocar, resposta), usos


# ------------------------------------------------- rede de segurança da memória

RE_PEDE_GUARDAR = [
    re.compile(r"\b(guarde?|salve?|anote?|registre?|memorize?|lembre(?:-se)?)\b[^?\n]{0,60}"
               r"\b(mem[óo]ria|guardar|anotar|lembrar|memorizar|registrar)\b", re.IGNORECASE),
    re.compile(r"\b(mem[óo]ria)\b[^?\n]{0,40}"
               r"\b(guarde?|salve?|anote?|registre?|memorize?|lembre(?:-se)?)\b", re.IGNORECASE),
    re.compile(r"\b(lembre(?:-se)?|anote|guarde|salve|registre|memorize)\b[^?\n]{0,15}?\bque\b", re.IGNORECASE),
]
RE_NAO_GUARDAR = re.compile(r"\b(n[ãa]o\s+(?:precisa|quero|guarde|salve|anote|registre|memorize|lembre)"
                            r"|esque[çc]a|esquece)\b", re.IGNORECASE)

def pede_guardar(texto):
    """Verdadeiro quando o dono claramente pediu para guardar algo."""
    if RE_NAO_GUARDAR.search(texto):
        return False
    return any(padrao.search(texto) for padrao in RE_PEDE_GUARDAR)


def guardar_direto(numero, texto, marca):
    """Pedido claro de guardar: grava sem depender do motor (rápido e sem risco de recusa)."""
    if not pede_guardar(texto) or len(texto) > 300 or "?" in texto:
        return False
    fato = extrair_fato(texto)
    e_anotacao = bool(re.search(r"\banot", texto, re.IGNORECASE))
    try:
        if e_anotacao:
            C.acrescentar_memoria(C.ARQ_ANOT, f"- **{C.agora().strftime('%d/%m/%Y %H:%M')}** — {fato}",
                                  titulo="# Anotações da memória (via chat)\n")
            confirmacao = f"✅ Anotado: “{fato[:200]}”"
        else:
            C.acrescentar_memoria(C.ARQ_LONGA, f"- ({C.agora().strftime('%d/%m/%Y')}) {fato}",
                                  titulo="# Memória longa — fatos e preferências\n")
            confirmacao = f"✅ Guardei na memória longa: “{fato[:200]}”"
    except Exception:
        return False
    extra = "_Guardei direto na memória, sem depender dos motores._"
    responder(numero, confirmacao, marca, extra=extra)
    C.registrar_conversa(numero, texto, confirmacao, "modo direto")
    C.registrar_diario(f"- **{C.agora().strftime('%d/%m %H:%M')}** — dono: {texto[:MAX_RESUMO].replace(chr(10), ' ')} "
                       f"→ eu: {confirmacao[:MAX_RESUMO].replace(chr(10), ' ')} (modo direto de memória)")
    return True



def extrair_fato(texto):
    """Tira o fato a guardar da mensagem do dono (aspas > depois dos ':' > depois de 'que')."""
    m = re.search(r"[“\"']([^”\"']{8,400})[”\"']", texto)
    if m:
        return m.group(1).strip(" .")
    m = re.search(r":\s*([^:]{8,400})$", texto, re.DOTALL)
    if m and not m.group(1).strip().lower().startswith("http"):
        return m.group(1).strip(" .")
    m = re.search(r"\bque\s+(.{8,400})$", texto, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip(" .")
    return texto.strip()[:400]


def garantir_memoria(texto_dono, resposta, usos):
    """Se o dono pediu para guardar e o motor não guardou (ou mentiu que guardou),
    a gravação acontece de verdade e a resposta recebe a confirmação."""
    if RE_NAO_GUARDAR.search(texto_dono):
        return resposta, usos
    if not any(padrao.search(texto_dono) for padrao in RE_PEDE_GUARDAR):
        return resposta, usos
    usos = usos or []
    ja_salvou = any(u.lower().startswith(("anotar", "lembrar")) for u in usos) \
        or "✅ Anotado" in resposta or "✅ Guardei" in resposta
    if ja_salvou:
        return resposta, usos
    fato = extrair_fato(texto_dono)
    e_anotacao = bool(re.search(r"\banot", texto_dono, re.IGNORECASE))
    try:
        if e_anotacao:
            C.acrescentar_memoria(C.ARQ_ANOT, f"- **{C.agora().strftime('%d/%m/%Y %H:%M')}** — {fato}",
                                  titulo="# Anotações da memória (via chat)\n")
            confirmacao = f"✅ Anotado: “{fato[:200]}”"
        else:
            C.acrescentar_memoria(C.ARQ_LONGA, f"- ({C.agora().strftime('%d/%m/%Y')}) {fato}",
                                  titulo="# Memória longa — fatos e preferências\n")
            confirmacao = f"✅ Guardei na memória longa: “{fato[:200]}”"
        return resposta.rstrip() + "\n\n" + confirmacao, usos + [f"memória (rede de segurança): {fato[:40]}"]
    except Exception as e:
        return resposta.rstrip() + f"\n\n⚠️ Tentei guardar na memória e falhou: `{str(e)[:120]}`", usos


# ------------------------------------------------------------------ modo direto

INTENCOES = [
    (r"\b(me avise|avise quando|avisa quando|quero ser avisado|me avisa)\b", "AVISAR", r"(.*)$"),
    (r"\b(me lembr\w+|cria?r? lembrete|lembrete)\b", "LEMBRETE", r"(.*)$"),
    (r"\b(vigiar|acompanhar a p[áa]gina|ficar de olho na p[áa]gina)\b", "VIGIAR", r"(https?://\S+)$"),
    (r"\b(meus avisos|avisos ativos|tem aviso|o que voc[êe] est[áa] vigiando)\b", "AVISOS", r"(.*)$"),
    (r"\b(meus lembretes|lembretes marcados)\b", "LEMBRETES", r"(.*)$"),
    (r"\b(clima|tempo|temperatura|vai chover|chover)\b", "CLIMA", r"(?:d[eoa]\s+)?([A-Za-zÀ-ÿ\s]{3,40})?$"),
    (r"\b(d[óo]lar|cota[çc][ãa]o|c[âa]mbio|euro|bitcoin)\b", "CAMBIO", r"(?:d[eoa]\s+)?(\w+)?$"),
    (r"\b(not[íi]cias?|manchetes?|o que est[áa] acontecendo)\b", "NOTICIAS", r"(.*)$"),
    (r"\b(que horas|horas? em|hora agora)\b", "HORA", r"(.*)$"),
    (r"\b(pesquis[ae]r?|buscar?|procur[ae]r? na internet)\b", "PESQUISAR", r"(.*)$"),
    (r"\b(verificar|checar|est[áa] no ar|site fora)\b", "VERIFICAR", r"(https?://\S+|\S+\.\w+.*)$"),
    (r"\b(cep)\b", "CEP", r"(\d{5}-?\d{3})"),
    (r"\b(feriado|feriados)\b", "FERIADOS", r"(\d{4})"),
    (r"\b(vers[ãa]o arquivada|arquivo do site|wayback|internet archive)\b", "ARQUIVO", r"(https?://\S+)$"),
    (r"\b(abr[ae]|ler|leia|veja|visite|confira)\b.*https?://", "ABRIR", r"(https?://\S+)$"),
    (r"\b(imagem|desenho|desenhar|figura)\b", "IMAGEM", r"(.*)$"),
    (r"\b(banco de dados|seus dados|seu banco|estat[íi]sticas|os n[úu]meros)\b", "DADOS", r"(.*)$"),
    (r"\b(mem[óo]ria|lembrar de|o que voc[êe] sabe)\b", "MEMORIA", r"(.*)$"),
    (r"\b(youtube|v[íi]deo)\b", "YOUTUBE", r"(https?://\S+)$"),
]


def modo_direto(texto):
    """Sem motor: entende pedidos comuns e responde com as ferramentas. Sempre devolve algo."""
    baixo = texto.lower()
    for padrao, ferramenta, extra_padrao in INTENCOES:
        if re.search(padrao, baixo):
            m = re.search(extra_padrao, texto.strip(), re.IGNORECASE)
            argumento = (m.group(1).strip() if m and m.group(1) else "")
            try:
                resultado = C.executar_ferramenta(ferramenta, argumento)
            except Exception as e:
                resultado = f"(a ferramenta {ferramenta} falhou: {str(e)[:100]})"
            return f"{resultado}\n\n_Meus motores gratuitos estão oscilando agora, mas isto eu consegui fazer com as minhas ferramentas._"
    return None


# ------------------------------------------------------------------ principal

def drenar_fila_respostas():
    """Se os motores voltaram, responde o que ficou na fila (máx 2 por execução)."""
    itens = C.fila_respostas_carregar()
    if not itens:
        return
    restantes = list(itens)
    processadas = 0
    for item in itens:
        if processadas >= 2:
            break
        numero_p = item.get("numero")
        texto_p = item.get("texto")
        marca_p = item.get("marca")
        if not (numero_p and texto_p and marca_p):
            restantes.remove(item)
            continue
        if ja_respondida(numero_p, marca_p):
            restantes.remove(item)  # já foi respondida por outro caminho
            continue
        historico_p = C.historico_da_conversa(numero_p) + [{"role": "user", "content": texto_p}]
        resposta_p, motor_p, _usos_p, _erro_p = C.responder_com_ferramentas(historico_p, numero_p)
        if resposta_p is None:
            C.log("fila: motores ainda fora do ar — mantenho a fila para a próxima execução")
            return
        responder(numero_p, resposta_p, marca_p,
                  extra="chequei a fila e respondi agora que os motores voltaram "
                        f"(motor {motor_p or 'modo direto'})")
        C.registrar_conversa(numero_p, texto_p, resposta_p, motor_p or "modo direto")
        try:
            C.registrar_resposta_cache(texto_p, resposta_p)
        except Exception:
            pass
        restantes.remove(item)
        processadas += 1
    if len(restantes) != len(itens):
        C.fila_respostas_salvar(restantes)


def principal():
    t_inicio = time.time()

    def segundos():
        return int(time.time() - t_inicio)

    def registrar_tempo():
        """Guarda quanto tempo a resposta levou (o banco mostra a velocidade típica)."""
        try:
            diag = C.ler_diagnostico()
            tempos = [x for x in (diag.get("tempos") or []) if isinstance(x, dict)][-49:]
            tempos.append({"quando": C.agora().isoformat(timespec="seconds"), "s": segundos()})
            diag["tempos"] = tempos
            C.salvar_diagnostico(diag)
        except Exception as e:
            C.log(f"tempo: não consegui registrar ({e})")

    dados = do_evento()
    if not dados:
        C.log("evento ignorado")
        return 0
    numero, texto, marca, origem = dados["numero"], dados["texto"], dados["marca"], dados.get("origem", "?")
    C.log(f"origem: {origem} | conversa #{numero} | marca: {marca} | texto: {texto[:80]!r}")
    if not numero:
        return 0

    try:
        if origem == "reprocessamento":
            C.log(f"reprocessamento: ignoro a trava anti-duplicado de propósito (marca {marca})")
        elif ja_respondida(numero, marca):
            C.log(f"já respondida (marca {marca}) — ignorando para não duplicar")
            return 0

        baixo = texto.lower().strip()

        # Estado real da casa: atualiza a fotografia que o cérebro verá no prompt e
        # autoriza (ou não) ação de publicação por esta mensagem do dono.
        try:
            import casa
            casa.definir_pedido(texto)
            if os.environ.get("GITHUB_TOKEN"):
                casa.atualizar()
        except Exception as e:
            C.log(f"estado da casa: não atualizei ({e})")

        # Pergunta de DECISÃO ("paro o Instagram?", "qual canal cortar?") responde com a
        # análise dos números, sem passar pelo motor. Motivo medido: com as chaves de motor
        # mortas, o último recurso devolveu marketing genérico ("pare o canal com ROAS < 2:1")
        # e ignorou todos os dados da casa. Número genérico é pior que silêncio.
        try:
            import casa as _casa
            if _casa.pede_decisao(texto) and len(texto) < 400:
                _placar_txt = C.ler_de("site", "posts/placar-metas.md", "")
                _des_txt = C.ler_de("site", "posts/desempenho.md", "")
                _analise = _casa.analise(_placar_txt, _des_txt)
                if _analise:
                    responder(numero, _analise, marca)
                    return 0
        except Exception as e:
            C.log(f"análise direta: não apliquei ({e})")

        # Pergunta sobre resultado/meta responde com números medidos, sem passar pelo motor:
        # rápido, honesto e impossível de inventar.
        if baixo in ("casa", "/casa", "estado", "/estado", "metas", "/metas",
                     "resultados", "como está a casa", "como esta a casa", "status casa"):
            import casa
            try:
                resposta_estado = casa.atualizar()
            except Exception as e:
                resposta_estado = f"⚠️ Não consegui ler os números agora ({str(e)[:120]})."
            responder(numero, resposta_estado, marca)
            return 0

        # avisos e lembretes: checagem leve a cada mensagem (não deixa aviso esperando o vigia)
        try:
            resumo_rapido = C.checar_avisos_rapido()
            if resumo_rapido.get("disparados") or resumo_rapido.get("lembretes"):
                C.log(f"avisos (na mensagem): {resumo_rapido}")
        except Exception as e:
            C.log(f"avisos rápidos: {e}")

        # fila de respostas pendentes: motores voltaram → respondo o que ficou devendo
        try:
            drenar_fila_respostas()
        except Exception as e:
            C.log(f"drenar fila: {e}")

        if baixo in ("/ajuda", "/help", "ajuda", "/comandos") and len(texto) < 20:
            responder(numero, ajuda(), marca)
            return 0
        if baixo in ("/status", "status"):
            responder(numero, status(), marca)
            return 0
        if baixo in ("/ruim", "ficou ruim", "resposta ruim", "não gostei", "nao gostei"):
            responder(numero, C.marcar_ultima_resposta_ruim(numero), marca)
            return 0
        m = re.match(r"^/?piloto\s*:?\s*(ligar|desligar|status|on|off)?\s*$", texto, re.IGNORECASE)
        if m:
            responder(numero, C.ferramenta_piloto((m.group(1) or "status").lower()), marca)
            return 0
        m = re.match(r"^/?postar\s+agora\s*:?\s*(ceifalume|prancheta)\s*$", texto, re.IGNORECASE)
        if m:
            import piloto
            responder(numero, piloto.postar_agora(m.group(1).lower()), marca)
            return 0
        if re.match(r"^/?medir\s+(agora)?\s*:?\s*$", baixo):
            import piloto
            responder(numero, piloto.medir_e_resistrar_texto(), marca)
            return 0
        m = re.match(r"^/?pensar\s*:?\s+(.+)$", texto, re.IGNORECASE | re.DOTALL)
        if m:
            pergunta = m.group(1).strip()
            C.log(f"modo pensar: {pergunta[:80]!r}")
            resposta_p, info = C.pensar_bem(pergunta, C.montar_system(numero))
            if resposta_p:
                responder(numero, resposta_p, marca, extra=f"🧠 modo pensar — {info}")
                try:
                    C.registrar_resposta_cache(pergunta, resposta_p)
                except Exception:
                    pass
            else:
                responder(numero, "⚠️ Não consegui pensar agora: " + str(info), marca)
            return 0

        m = re.match(r"^/?(?:anotar)\s*:?\s+(.+)$", texto, re.IGNORECASE | re.DOTALL)
        if m:
            conteudo = m.group(1).strip()
            try:
                C.acrescentar_memoria(C.ARQ_ANOT, f"- **{C.agora().strftime('%d/%m/%Y %H:%M')}** — {conteudo}",
                                      titulo="# Anotações da memória (via chat)\n")
                responder(numero, f"✅ Anotado: “{conteudo[:200]}”", marca)
            except Exception as e:
                responder(numero, f"⚠️ Não consegui anotar agora: `{str(e)[:150]}`", marca)
            return 0

        m = re.match(r"^/?(?:lembrar)\s*:?\s+(.+)$", texto, re.IGNORECASE | re.DOTALL)
        if m:
            conteudo = m.group(1).strip()
            try:
                C.acrescentar_memoria(C.ARQ_LONGA, f"- ({C.agora().strftime('%d/%m/%Y')}) {conteudo}",
                                      titulo="# Memória longa — fatos e preferências\n")
                responder(numero, f"✅ Guardei na memória longa: “{conteudo[:200]}”", marca)
            except Exception as e:
                responder(numero, f"⚠️ Não consegui guardar agora: `{str(e)[:150]}`", marca)
            return 0

        comandos = (
            (r"^/?(?:avise|avisa|avisar)\s*(?:quando)?\s*:?\s*(.+)$", "🔔", "aviso", C.ferramenta_avisar),
            (r"^/?(?:avisos)\s*:?\s*(.*)$", "", "avisos", C.ferramenta_avisos),
            (r"^/?(?:aviso\s+teste|testar?\s+aviso|teste\s+de\s+aviso)\s*:?\s*$", "", "teste de aviso",
             lambda _a: C.ferramenta_aviso_teste()),
            (r"^/?(?:vigiar|vigia)\s*:?\s*(https?://\S+)$", "👁", "vigia de página", C.ferramenta_vigiar),
            (r"^/?(?:lembrete|me\s+lembre)\s*:?\s*(.+)$", "", "lembrete", C.ferramenta_lembrete),
            (r"^/?(?:lembretes)\s*:?\s*(.*)$", "", "lembretes", C.ferramenta_lembretes),
            (r"^/?apagar\s+(?:o\s+)?aviso\s*:?\s*(\d+|todos)$", "", "aviso",
             lambda a: C.ferramenta_avisos("apagar " + a)),
            (r"^/?apagar\s+(?:o\s+)?lembrete\s*:?\s*(\d+|todos)$", "", "lembrete",
             lambda a: C.ferramenta_lembretes("apagar " + a)),
            (r"^/?(?:pesquisar|buscar|search)\s*:?\s+(.+)$", "🌐", "busca", C._ferramenta_pesquisar),
            (r"^/?(?:abrir|ler)\s*:?\s+(https?://\S+)$", "📄", "página", C._ferramenta_abrir),
            (r"^/?(?:arquivo|wayback|archive)\s*:?\s+(https?://\S+)$", "", "arquivo", C.ferramenta_arquivo),
            (r"^/?(?:cep)\s*:?\s*(\d{5}-?\d{3})?$", "", "CEP", C.ferramenta_cep),
            (r"^/?(?:feriados?)\s*:?\s*(\d{4})?$", "", "feriados", C.ferramenta_feriados),
            (r"^/?(?:clima|tempo)\s*:?\s*(.*)$", "🌤", "clima", C.ferramenta_clima),
            (r"^/?(?:cambio|câmbio|cotacao|cotação|dolar|dólar)\s*:?\s*(.*)$", "💱", "cotação", C.ferramenta_cambio),
            (r"^/?(?:noticias|notícias)\s*:?\s*(.*)$", "📰", "notícias", C.ferramenta_noticias),
            (r"^/?(?:hora|horas)\s*:?\s*(.*)$", "🕐", "hora", C.ferramenta_hora),
            (r"^/?(?:youtube)\s*:?\s+(https?://\S+)$", "▶️", "vídeo", C.ferramenta_youtube),
            (r"^/?(?:imagem|desenhar|gerar imagem|desenho)\s*:?\s+(.+)$", "🎨", "imagem", C.ferramenta_imagem),
            (r"^/?(?:verificar|checar|cheque)\s*:?\s+(https?://\S+)$", "🔎", "verificação", C.ferramenta_verificar),
            (r"^/?(?:memoria|memória)\s*:?\s+(.+)$", "🧠", "memória", C.ferramenta_memoria),
            (r"^/?(?:dados|banco de dados)\s*:?\s*$", "", "banco de dados", lambda _a: C.ferramenta_dados_agora()),
            (r"^/?(?:banco)\s*:?\s+(.+)$", "🗄", "banco de dados", C.buscar_no_banco),
            (r"^/?(?:placar|painel)\s*:?\s*$", "", "painel", lambda _a: C.ferramenta_placar()),
            (r"^/?(?:janelas|caçadas|cacas)\s*:?\s*$", "📊", "diário de janelas",
             lambda _a: janelas_cmd()),
            (r"^/?(?:cacar|caçar)\s*:?\s*$", "🏹", "caçada de motores", lambda _a: cacar_cmd()),
            (r"^/?(?:pagos|pagas)\s*:?\s*$", "💳", "mapa de pagos", lambda _a: pagos_cmd()),
            (r"^[!/]?(?:motores|motor|engines)\s*:?\s*$", "⚙️", "motores", lambda _a: motores_cmd()),
            (r"^[!/]?local\s*:?\s+(.+)$", "💻", "motor local", lambda a: local_cmd(a)),
            (r"^/?(?:melhorias)\s*:?\s*$", "", "melhorias", lambda _a: C.ferramenta_melhorias()),
            (r"^/?(?:panorama|resumir)\s*:?\s*$", "", "panorama",
             lambda _a: C.resumir_memoria() if "resumir" in texto.lower() else C.ferramenta_panorama()),
        )
        for padrao, emoji, rotulo, funcao in comandos:
            m = re.match(padrao, texto, re.IGNORECASE | re.DOTALL)
            if m:
                argumento = (m.group(1) if m.groups() else "").strip()
                try:
                    resultado = funcao(argumento)
                except Exception as e:
                    resultado = f"⚠️ {rotulo} falhou: `{str(e)[:200]}`"
                responder(numero, (f"{emoji} {resultado}").strip(), marca)
                return 0

        # pedido claro de guardar memória → atende direto, sem motor
        if guardar_direto(numero, texto, marca):
            return 0

        # cache exato: mesma pergunta já respondida → responde do próprio arquivo, sem motor
        try:
            cache = C.cache_exato(texto)
        except Exception:
            cache = None
        if cache:
            responder(numero, cache + "\n\n---\n\n_(🗄 do meu cache — você já fez essa pergunta)_", marca)
            C.registrar_diario(f"- **{C.agora().strftime('%d/%m %H:%M')}** — dono: "
                               f"{texto[:MAX_RESUMO].replace(chr(10), ' ')} → CACHE EXATO")
            return 0

        # COMITÊ TOTAL: "modomaximo: pergunta" — TODOS os motores ao mesmo tempo + juiz
        if texto.lstrip().lower().startswith(("modomaximo:", "modo máximo:", "comite:", "comitê:")):
            pergunta_mm = texto.split(":", 1)[1].strip() or "diga ok"
            C.log("COMITÊ TOTAL: todos os motores em paralelo")
            try:
                txt_mm, desc_mm = C.comite_total(C.montar_system(numero), pergunta_mm)
            except Exception as e:
                txt_mm, desc_mm = None, f"comitê falhou: {str(e)[:100]}"
            if txt_mm:
                responder(numero, txt_mm + "\n\n---\n_(🏛 " + desc_mm + ")_", marca)
            else:
                responder(numero, "🏛 Ninguém respondeu agora (" + desc_mm + "). "
                          "As janelas dos motores estão fechadas — tenta de novo em minutos.", marca)
            return 0

        # DADOS DA CASA: antes de qualquer motor, o que a casa já sabe entra no prompt.
        # Motivo: motor pequeno COM o fato certo acerta; motor grande SEM contexto inventa.
        # A recuperação lê os arquivos (memória, placar, medições) e não depende de API.
        texto_com_dados = texto
        # CONSULTA DE NÚMERO: sai do arquivo, não do modelo. Modelo pequeno troca "alvo" por
        # "observado" (aconteceu na issue #39: respondeu downloads=100 com 45 medidos).
        try:
            import dados as _dd
            _direta = _dd.resposta_direta(texto)
            if _direta:
                responder(numero, _direta, marca)
                return 0
        except Exception as e:
            C.log(f"resposta direta não usada ({str(e)[:80]})")
        try:
            import dados as _dados
            _ctx = _dados.montar_contexto(texto)
            if _ctx:
                texto_com_dados = _ctx + "\n\nPergunta do dono: " + texto
                C.log(f"camada de dados: {_ctx.count(chr(10))} fato(s) da casa no prompt")
        except Exception as e:
            C.log(f"camada de dados não usou nada ({str(e)[:90]})")

        # modo "pensar bem": comando explícito "pensar: ..." ou pergunta complexa →
        # 2 motores respondem e um juiz escreve a versão final (v3.14, cérebro)
        pergunta_pensar = ""
        if texto.lstrip().lower().startswith("pensar:"):
            pergunta_pensar = texto.split(":", 1)[1].strip()
            try:
                import dados as _d
                _c = _d.montar_contexto(pergunta_pensar)
                if _c:
                    pergunta_pensar = _c + "\n\nPergunta do dono: " + pergunta_pensar
            except Exception:
                pass
        elif C._pergunta_complexa(texto):
            pergunta_pensar = texto_com_dados
        resposta, motor_nome, usos, erro = None, None, None, None
        resposta_falha = False
        if pergunta_pensar:
            C.log("modo pensar bem ativado (2 motores + juiz)")
            try:
                resposta, motor_nome = C.pensar_bem(pergunta_pensar, C.montar_system(numero))
                if resposta:
                    usos = ["pensar bem (2 motores + juiz)"]
                    if "[[" in resposta:
                        resposta, motor_nome, usos_pb = pensar_bem_com_ferramentas(resposta, numero, motor_nome)
                        usos += usos_pb
            except Exception as e:
                C.log(f"pensar bem falhou ({str(e)[:90]}) — cai para o fluxo normal")
                resposta = None

        # resposta com motor (o orquestrador escolhe o melhor para o tipo de pergunta)
        if resposta is None:
            categoria = C.categoria_da_pergunta(texto)
            preferido = C.escolher_motor(categoria)
            if preferido:
                C.log(f"orquestrador: categoria '{categoria}' → motor preferido '{preferido}'")
            historico = C.historico_da_conversa(numero) + [{"role": "user", "content": texto_com_dados}]
            resposta, motor_nome, usos, erro = C.responder_com_ferramentas(historico, numero, preferir=preferido)

            if resposta is None:
                resposta = modo_direto(texto)

        # self-refine: resposta muito curta para pergunta longa → tenta outro motor
        if resposta and len(resposta.strip()) < 40 and len(texto.strip()) > 100:
            C.log("resposta muito curta — tentando de novo com outro motor")
            try:
                outra, motor_outro, _e = C.chamar_llm(
                    [{"role": "user", "content": texto}], C.montar_system(numero), excluir=(motor_nome,))
                if outra and len(outra.strip()) > len(resposta.strip()):
                    resposta, motor_nome = outra, motor_outro
            except Exception as e:
                C.log(f"self-refine: {e}")

        if not resposta:
            # NUNCA mais silêncio: falla com honestidade (a marca só grava COM resposta)
            detalhe = str(erro)[:140] if erro else "janelas dos motores fechadas"
            resposta = ("🚦 **Não consegui falar com nenhum motor agora** (" + detalhe + ").\n"
                        "O IP do runner alterna janelas a cada hora — reprocesse em minutos "
                        "(ou reenvie com outras palavras) que eu respondo.")
            motor_nome = None
            resposta_falha = True

        if resposta:
            resposta, usos_extras = executar_comandos_soltos(resposta)
            if usos_extras:
                usos = (usos or []) + usos_extras
            resposta, usos = garantir_memoria(texto, resposta, usos)
            rodape = f"_(⏱ {segundos()} s · {motor_nome or 'modo direto, sem motor'}"
            if usos:
                rodape += " · usei: " + "; ".join(usos)
            rodape += ")_"
            responder(numero, resposta, marca, extra=rodape)
            registrar_tempo()
            C.registrar_conversa(numero, texto, resposta, motor_nome or "modo direto")
            try:
                C.registrar_resposta_cache(texto, resposta)
            except Exception as e:
                C.log(f"cache de respostas: {e}")
            if not resposta_falha:
                try:
                    C.registrar_placar(motor_nome or "modo direto", C.categoria_da_pergunta(texto),
                                       ok=True, tempo_s=segundos())
                except Exception as e:
                    C.log(f"placar: {e}")
            C.registrar_diario(f"- **{C.agora().strftime('%d/%m %H:%M')}** — dono: "
                               f"{texto[:MAX_RESUMO].replace(chr(10), ' ')} → eu: "
                               f"{resposta[:MAX_RESUMO].replace(chr(10), ' ')} ({motor_nome or 'modo direto'})")
        else:
            reserva = None
            try:
                reserva = C.resposta_de_reserva(texto)
            except Exception as e:
                C.log(f"cérebro de reserva indisponível: {e}")
            if reserva:
                responder(numero,
                          "🗄 **Cérebro de reserva (100% meu, sem motores):** os motores online estão fora do ar "
                          "agora, mas achei no meu próprio histórico uma resposta parecida com a sua pergunta:\n\n"
                          "---\n\n" + reserva + "\n\n---",
                          marca,
                          extra="Quando os motores voltarem eu respondo melhor. Essa resposta veio do meu arquivo de memória.")
                C.registrar_diario(f"- **{C.agora().strftime('%d/%m %H:%M')}** — dono: "
                                   f"{texto[:MAX_RESUMO].replace(chr(10), ' ')} → RESERVA (motores fora do ar)")
                return 0
            try:
                C.fila_respostas_adicionar(numero, texto, marca)
            except Exception as e:
                C.log(f"fila de respostas: {e}")
            responder(numero,
                      "⚠️ Agora não consegui responder: **os motores gratuitos estão todos fora do ar no momento** "
                      "(isso costuma durar minutos).\n\n"
                      "📥 **Sua pergunta entrou na fila** — assim que os motores voltarem eu respondo sozinho, "
                      "aqui mesmo, sem você precisar reenviar.\n\n"
                      "**Enquanto isso, isto funciona sem motor:** `pesquisar:`, `abrir:`, `clima:`, `cambio:`, "
                      "`noticias:`, `hora:`, `imagem:`, `verificar:`, `memoria:`, `anotar:`, `lembrar:`, "
                      "`avise quando:`, `lembrete:`, `/status`.\n\n"
                      f"_Detalhe técnico: `{str(erro)[:200]}`_",
                      marca,
                      extra="Mensagem na fila de respostas — o vigia e a próxima mensagem drenam a fila sozinhos.")
            C.registrar_diario(f"- **{C.agora().strftime('%d/%m %H:%M')}** — dono: "
                               f"{texto[:MAX_RESUMO].replace(chr(10), ' ')} → FALHA de motores")
        return 0

    except Exception as e:
        C.log(f"erro inesperado: {e!r}")
        try:
            C.comentar(numero, f"{C.ASSINATURA}\n\n⚠️ Tive um erro interno inesperado: `{str(e)[:300]}`\n\n"
                               f"Vou reprocessar essa mensagem automaticamente.\n\n{MARCA_ABERTURA}erro:{marca}-->")
        except Exception as e2:
            C.log(f"nem o aviso de erro consegui postar: {e2!r}")
        return 0


if __name__ == "__main__":
    sys.exit(principal())
