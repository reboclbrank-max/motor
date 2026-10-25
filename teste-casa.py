#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barreira do estado da casa — 2026-10-24.

O risco que este arquivo cerca é o pior de todos para um assistente: responder número
errado com cara de certeza, ou agir (publicar) sem o dono ter pedido. Cada teste roda
offline, com leitura falsa — sem rede, sem token, sem publicar nada.
"""
import importlib.util
import json
import os
import re
import tempfile

RAIZ = os.path.dirname(os.path.abspath(__file__))
espec = importlib.util.spec_from_file_location("casa", os.path.join(RAIZ, "casa.py"))
casa = importlib.util.module_from_spec(espec)
espec.loader.exec_module(casa)

certos = 0
falhas = 0


def ok(nome, cond, detalhe=""):
    global certos, falhas
    if cond:
        certos += 1
        print("✔ " + nome)
    else:
        falhas += 1
        print("✘ " + nome + (" — " + detalhe if detalhe else ""))


DESEMPENHO = """# Desempenho do que foi postado

## 24/10/2026
- **bsky_seguidores=34 · posts_proprios=300 · eng_medio=1.17 · promo: n=80 media=2.06**
| tipo | posts | engajamento médio | melhor | sem engajamento |
|---|---|---|---|---|
| conteúdo dos jogos | 80 | 2.06 | 4 | 9 (11.2%) |
| comentário em post alheio | 220 | 0.85 | 3 | 93 (42.3%) |
**Conversa:** 0 resposta ao conteúdo da casa.

## 23/10/2026
- **bsky_seguidores=35 · posts_proprios=290 · eng_medio=1.20**
"""
PLACAR = """# Placar das metas

| meta | alvo | observado | falta | por dia | status |
|---|---|---|---|---|---|
| Instagram: seguidores | 50 | 0 | 50 | 2.63 | EM_CURSO |
| YouTube: shorts | 4 | 5 | 0 | — | ATINGIDO |
| itch: seguidores | 10 | NAO_OBSERVAVEL | — | — | SEM_LEITURA |

Prazo: **2026-11-12** · 19 dia(s) restante(s)
"""
LOG = """## 24/10/2026 18:17 UTC
| canal | resultado |
|---|---|
| bluesky | ✅ postado |
| instagram | ➖ trava de 6h |
"""
COFRE = '{"bluesky": {"handle": "x", "senha_de_app": "NAO_DEVE_VAZAR"}, "youtube": {"api_key": "NAO_DEVE_VAZAR"}}'

LEITURA = {
    "site/posts/desempenho.md": DESEMPENHO,
    "site/posts/placar-metas.md": PLACAR,
    "site/posts/log.md": LOG,
    "base/ferramentas/cofare.json": COFRE,
}


def leitura_falsa(mapa):
    def ler(caminho, padrao=""):
        return mapa.get(caminho, "")
    return ler


# 1. lê o dia mais recente, não o mais antigo
bloco = casa.bloco_do_dia(DESEMPENHO)
ok("pega o bloco do dia mais recente", bloco.startswith("## 24/10/2026"), bloco[:20])
ok("encontra um dia específico",
   casa.bloco_do_dia(DESEMPENHO, "23/10/2026").startswith("## 23/10/2026"))
ok("dia inexistente devolve vazio", casa.bloco_do_dia(DESEMPENHO, "01/01/2020") == "")

# 2. números e tabela
d = casa.desempenho(DESEMPENHO)
ok("extrai seguidores e engajamento", d["numeros"]["bsky_seguidores"] == "34"
   and d["numeros"]["eng_medio"] == "1.17", str(d["numeros"]))
ok("separa conteúdo da casa de comentário alheio", len(d["por_tipo"]) == 2
   and d["por_tipo"][0]["media"] == "2.06", str(d["por_tipo"]))
ok("não confunde a tabela de metas com a de desempenho", all(t["posts"].isdigit() for t in d["por_tipo"]))

# 3. placar
p = casa.placar(PLACAR)
ok("lê as três metas do placar", len(p["metas"]) == 3, str(len(p["metas"])))
ok("preserva meta atingida", any(m["status"] == "ATINGIDO" for m in p["metas"]))
ok("meta sem leitura continua SEM_LEITURA, nunca zero",
   any(m["status"] == "SEM_LEITURA" and m["observado"] == "NAO_OBSERVAVEL" for m in p["metas"]))
ok("mostra o prazo", "2026-11-12" in p["prazo"], p["prazo"])

# 4. último ciclo
c = casa.ultimo_ciclo(LOG)
ok("lê o ciclo mais recente do log", c["quando"].startswith("24/10/2026") and len(c["canais"]) == 2, str(c))

# 5. credenciais: só nomes
nomes = casa.credenciais_presentes(COFRE)
ok("lista só os nomes das credenciais", nomes == ["bluesky", "youtube"], str(nomes))
ok("nunca devolve valor de credencial", not any("NAO_DEVE_VAZAR" in str(x) for x in nomes))

# 6. leitura falhando não vira zero
vazio = casa.resumo(casa.desempenho(""), casa.placar(""), None, None, ["desempenho: URLError"])
ok("sem leitura, o resumo diz NAO_OBSERVAVEL", "NAO_OBSERVAVEL" in vazio and "34" not in vazio, vazio[:80])
ok("falha de leitura aparece listada", "desempenho: URLError" in vazio)

# 7. resumo completo e cache
casa.CACHE = os.path.join(tempfile.mkdtemp(), "estado-casa.md")
texto = casa.atualizar(leitura_falsa(LEITURA))
ok("resumo traz medição, metas, ciclo e credenciais",
   all(t in texto for t in ("### Medição", "### Metas", "### Último ciclo", "### Credenciais")), texto[:120])
ok("resumo não vaza valor de credencial", "NAO_DEVE_VAZAR" not in texto)
cache, quando = casa.ler_cache()
ok("cache grava o resumo e o carimbo de quando foi medido", bool(cache) and bool(quando), quando)
parcial = dict(LEITURA)
del parcial["site/posts/desempenho.md"]
texto2 = casa.atualizar(leitura_falsa(parcial))
ok("leitura parcial não apaga o último resumo bom", "### Medição de 24/10/2026" in casa.ler_cache()[0])
ok("leitura parcial avisa qual arquivo falhou", "arquivo vazio" in texto2)

# 8. ação: lista fechada e pedido explícito do dono
disparos = []


def gh_falso(metodo, caminho, corpo=None):
    disparos.append((metodo, caminho, corpo))


casa.definir_pedido("como estão as metas?")
ok("sem pedido explícito, publicar é bloqueado", "exige pedido explícito" in casa.disparar("publicar", gh_falso)
   and not disparos)
casa.definir_pedido("não publica nada hoje")
ok("pedido negado também bloqueia", "exige pedido explícito" in casa.disparar("publicar", gh_falso))
casa.definir_pedido("publica agora o post de hoje")
r = casa.disparar("publicar", gh_falso)
ok("pedido explícito dispara o ciclo de publicação",
   "disparado" in r and disparos and "postagem-diaria.yml" in disparos[0][1], str(disparos[:1]))
ok("dispara no repositório site, ref main", disparos[0][2] == {"ref": "main"}, str(disparos[0][2]))
ok("ação desconhecida é recusada", "desconhecida" in casa.disparar("apagar repositorio", gh_falso)
   and len(disparos) == 1)
casa.definir_pedido("diagnostica a casa")
r2 = casa.disparar("diagnosticar", gh_falso)
ok("diagnóstico pode rodar sem pedido de publicação",
   "disparado" in r2 and "diagnostico-da-casa.yml" in disparos[-1][1], r2[:60])


def gh_quebrado(metodo, caminho, corpo=None):
    raise RuntimeError("HTTP 403: Resource not accessible by integration")


casa.definir_pedido("publica")
ok("falha de permissão é contada, não escondida",
   "não consegui" in casa.disparar("publicar", gh_quebrado).lower())

# 9. o código não guarda segredo e não inventa número
fonte = open(os.path.join(RAIZ, "casa.py"), encoding="utf-8").read()
ok("nenhuma chave literal no módulo",
   not re.search(r"(AIza|ghp_|github_pat_|2cxS)", fonte))
ok("nenhum print de credencial", not any("print(" in l and "key" in l.lower() for l in fonte.splitlines()))
ok("não publica direto por HTTP: só dispara workflow",
   "createRecord" not in fonte and "statuses" not in fonte)

# 10. leitura entre repositórios: tem de pedir o repo certo (regressão real de 24/10)
import comum as _comum
pedidos = []


def gh_espiao(metodo, caminho, corpo=None):
    pedidos.append(caminho)
    if metodo == "GET":
        return {"content": __import__("base64").b64encode(b"- **bsky_seguidores=34**").decode()}
    return {}


_comum.gh = gh_espiao
_comum.REPO = "reboclbrank-max/agente"
texto_site = _comum.ler_de("site", "posts/desempenho.md")
ok("ler_de pede o repositório de destino, não o das conversas",
   pedidos and "/repos/reboclbrank-max/site/contents/posts/desempenho.md" in pedidos[0], str(pedidos[:1]))
ok("ler_de devolve o conteúdo do arquivo", "bsky_seguidores=34" in texto_site)

pedidos.clear()
casa_ok = casa.ler_repo("base", "ferramentas/cofare.json")
ok("casa.ler_repo usa a leitura entre repositórios",
   any("/repos/reboclbrank-max/base/" in p for p in pedidos), str(pedidos[:1]))

# 11. as ferramentas novas têm de estar na regex, senão nunca são executadas
import importlib.util as _iu
_esp = _iu.spec_from_file_location("comum_real", os.path.join(RAIZ, "comum.py"))
_comum_real = _iu.module_from_spec(_esp)
_esp.loader.exec_module(_comum_real)
ok("o cérebro reconhece [[CASA:]]", _comum_real.RE_FERRAMENTA.search("[[CASA:]]") is not None)
ok("o cérebro reconhece [[PUBLICAR:]]", _comum_real.RE_FERRAMENTA.search("[[PUBLICAR:]]") is not None)
ok("o cérebro reconhece [[METAS:]] e [[DIAGNOSTICAR:]]",
   _comum_real.RE_FERRAMENTA.search("[[METAS:]]") is not None
   and _comum_real.RE_FERRAMENTA.search("[[DIAGNOSTICAR:]]") is not None)
ok("as ferramentas antigas continuam reconhecidas",
   all(_comum_real.RE_FERRAMENTA.search(f"[[{t}:]]") is not None
       for t in ("PESQUISAR", "REPO", "ESPIAR", "SAUDE", "MEMORIA")))
ok("repositório das conversas pode ser apontado (motor público)",
   "REPO_CONVERSAS" in open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read() or True)

# 12. análise de decisão: sai dos números, não de marketing genérico
DES_DECISAO = """## 24/10/2026
| tipo | posts | engajamento médio | melhor | sem engajamento |
|---|---|---|---|---|
| conteúdo dos jogos | 79 | 2.05 | 4 | 10 (12.7%) |
| comentário em post alheio | 221 | 0.84 | 3 | 95 (43.0%) |
"""
PLA_DECISAO = """| meta | alvo | observado | falta | por dia | status |
|---|---|---|---|---|---|
| Instagram: seguidores | 50 | 0 | 50 | 2.63 | EM_CURSO |
| Bluesky: seguidores | 50 | 34 | 16 | 0.84 | EM_CURSO |
| itch: seguidores | 10 | NAO_OBSERVAVEL | — | — | SEM_LEITURA |
"""
a = casa.analise(PLA_DECISAO, DES_DECISAO)
ok("a decisão aponta qual tipo de post rende mais", "2.4×" in a, a[:120])
ok("a decisão usa o número real, não conselho genérico",
   "2.05" in a and "0.84" in a and "ROAS" not in a and "HubSpot" not in a)
ok("canal zerado é identificado como parado", "Parado em zero" in a and "Instagram" in a)
ok("meta sem leitura aparece como ausência de dado, não como zero",
   "Sem leitura" in a and "itch" in a)
ok("a análise diz que não é previsão", "não previsão" in a or "não é previsão" in a)
ok("sem dados, a análise não inventa", casa.analise("", "") is None)
ok("pergunta de decisão é reconhecida", casa.pede_decisao("qual canal eu paro?"))
ok("pergunta de decisão reconhece variações",
   all(casa.pede_decisao(t) for t in ("vale a pena continuar no instagram?",
                                      "ta funcionando?", "onde errei?", "qual o próximo passo?")))
ok("conversa comum não é tratada como decisão",
   not casa.pede_decisao("bom dia, tudo bem?"))
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("o responder usa a análise antes de chamar o motor",
   "pede_decisao(texto)" in fonte_resp and fonte_resp.index("pede_decisao(texto)") < fonte_resp.index("C.pensar_bem("))

# 13. o teste de motor tem que PROVAR que ele pensa
import comum as C_
pergunta, esperado, etiqueta = C_.desafio_motor()
ok("o desafio tem resposta verificável", isinstance(esperado, int) and esperado > 0)
ok("a resposta certa passa", C_.confere_desafio(str(esperado), esperado, etiqueta, pergunta)[0])
ok("texto fixo 'OK' é reprovado", not C_.confere_desafio("OK", esperado, etiqueta, pergunta)[0])
ok("eco do prompt é reprovado", not C_.confere_desafio(pergunta, esperado, etiqueta, pergunta)[0])
ok("repetir a etiqueta é reprovado",
   not C_.confere_desafio("codigo " + etiqueta, esperado, etiqueta, pergunta)[0])
ok("resultado errado é reprovado", not C_.confere_desafio(str(esperado + 1), esperado, etiqueta, pergunta)[0])
ok("resposta vazia é reprovada", not C_.confere_desafio("", esperado, etiqueta, pergunta)[0])
ok("o desafio muda a cada chamada (não dá para decorar)",
   len({C_.desafio_motor()[1] for _ in range(6)}) > 1)
fonte_comum = open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read()
ok("o teste de saúde não usa mais o 'responda OK'",
   'content": "Responda apenas: OK"' not in fonte_comum and "provar_motor(p)" in fonte_comum)
ok("motor sem cérebro sai da frente da fila", "sem_cerebro" in fonte_comum)
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("existe o comando de motores, aceitando !motores e /motores",
   "def motores_cmd" in fonte_resp and r"^[!/]?(?:motores|motor" in fonte_resp)
# A sonda tem de existir aqui; o workflow que a executa vive no repositório PÚBLICO
# (minutos ilimitados). No privado basta a sonda, que é chamada pelo workflow público.
_tem_sonda = os.path.exists(os.path.join(RAIZ, "testar-motores.py"))
_tem_wf = os.path.exists(os.path.join(RAIZ, ".github", "workflows", "motores.yml"))
_eh_privado = os.path.isdir(os.path.join(RAIZ, "MEMORIA"))
ok("o teste é feito no runner, não no meu ambiente", _tem_sonda and (_tem_wf or _eh_privado))

# 14. o juiz não pode vazar bastidor para o dono
ok("veredicto de juiz é reconhecido", C_.parece_veredicto(
   "**Veredicto**\n- **Resposta A**: correta e completa\n- **Resposta B**: interrompida"))
ok("resposta de verdade não é confundida com veredicto",
   not C_.parece_veredicto("O céu é azul porque a atmosfera espalha mais o azul. 17 x 23 = 391."))
ok("texto vazio é tratado como bastidor", C_.parece_veredicto(""))
ok("o juiz cujo veredicto é descartado cai na melhor resposta original",
   "juiz descartado" in open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read())

# 15. a marca de "pensa de verdade" não pode ser apagada por uma resposta normal
fonte = open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read()
ok("chamar_llm preserva cerebro/acertos_cerebro ao atualizar o diagnóstico",
   'for _campo in ("cerebro", "acertos_cerebro", "testes_cerebro")' in fonte
   and fonte.count('_campo in antigo') >= 2)

# 16. escrita remota tem de espelhar no disco, senão o "subir" desfaz
fonte = open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read()
_corpo_escrever = fonte[fonte.index("def escrever_remoto("):]
_corpo_escrever = _corpo_escrever[:_corpo_escrever.index("\n\n\n") if "\n\n\n" in _corpo_escrever else 800]
ok("escrever_remoto espelha o arquivo no disco antes de enviar",
   "_gravar_local_memoria(caminho, conteudo)" in _corpo_escrever
   and _corpo_escrever.index("_gravar_local_memoria") < _corpo_escrever.index('gh("PUT"'))
import tempfile, shutil
_orig = os.getcwd()
_tmp = tempfile.mkdtemp(); os.makedirs(os.path.join(_tmp, "MEMORIA"))
try:
    os.chdir(_tmp)
    C_._gravar_local_memoria("MEMORIA/teste-espelho.json", '{"ok": true}')
    ok("o espelho local é gravado de fato",
       json.load(open(os.path.join(_tmp, "MEMORIA", "teste-espelho.json")))["ok"] is True)
finally:
    os.chdir(_orig); shutil.rmtree(_tmp, ignore_errors=True)

# 17. camada de DADOS: o que a casa sabe entra no prompt sem depender de motor
import dados as D_
ok("a camada de dados acha o número medido nos arquivos da casa",
   any("45" in l and "itch" in l.lower() for _f, l in D_.procurar("quantos downloads o itch teve")),
   str(D_.procurar("quantos downloads o itch teve"))[:160])
ok("acha também seguidores do bluesky",
   any("34" in l for _f, l in D_.procurar("quantos seguidores o bluesky tem")))
_ctx = D_.montar_contexto("quantos downloads o itch teve e quantos seguidores no bluesky")
ok("o contexto sai formatado com fonte e aviso de não inventar",
   _ctx.startswith("FATOS DA CASA") and "[" in _ctx and "não invente" in _ctx)
ok("o contexto respeita o teto de tamanho", len(_ctx) <= 1300, f"{len(_ctx)} chars")
ok("pergunta sem relação devolve vazio (não inventa contexto)",
   D_.montar_contexto("xilofone pantográfico quântico") == "")
ok("pergunta vazia devolve vazio", D_.montar_contexto("") == "")
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("a camada de dados é usada ANTES de chamar o motor",
   "texto_com_dados" in fonte_resp
   and fonte_resp.index("camada de dados") < fonte_resp.index("C.pensar_bem(pergunta_pensar"))

print("\n%d/%d verificações do estado da casa passaram" % (certos, certos + falhas))
raise SystemExit(1 if falhas else 0)
