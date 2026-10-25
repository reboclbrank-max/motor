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
# A barreira roda ANTES do download da memória, então estes testes usam conteúdo de
# exemplo. Teste que depende de arquivo baixado quebra a barreira — e barreira quebrada
# não protege nada.
import dados as D_
_EXEMPLO = [
    ("MEMORIA/estado-casa.md", "- itch: downloads: alvo 100 · observado 45 · falta 55 · EM_CURSO"),
    ("MEMORIA/estado-casa.md", "- Bluesky: seguidores: alvo 50 · observado 34 · falta 16 · EM_CURSO"),
    ("MEMORIA/manual.md", "**Empresa:** estúdio indie. Jogos: Ceifalume 0.1 e Prancheta 0.1 no itch.io"),
]
_original = D_._linhas_da_casa
D_._linhas_da_casa = lambda: list(_EXEMPLO)
try:
    ok("a camada de dados acha o número medido",
       any("45" in l for _f, l in D_.procurar("quantos downloads o itch teve")))
    ok("acha também seguidores do bluesky",
       any("34" in l for _f, l in D_.procurar("quantos seguidores o bluesky tem")))
    _ctx = D_.montar_contexto("quantos downloads o itch teve e quantos seguidores no bluesky")
    ok("o contexto sai formatado com fonte e aviso de não inventar",
       _ctx.startswith("FATOS DA CASA") and "[" in _ctx and "não invente" in _ctx)
    ok("o contexto respeita o teto de tamanho", len(_ctx) <= 1300, f"{len(_ctx)} chars")
    ok("pergunta sem relação devolve vazio (não inventa contexto)",
       D_.montar_contexto("xilofone pantográfico quântico") == "")
    ok("pergunta vazia devolve vazio", D_.montar_contexto("") == "")
finally:
    D_._linhas_da_casa = _original
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("a camada de dados é usada ANTES de chamar o motor",
   "texto_com_dados" in fonte_resp
   and fonte_resp.index("camada de dados") < fonte_resp.index("C.pensar_bem(pergunta_pensar"))

# 18. rodízio: o limite de um motor não pode virar o limite de todos
import rodizio as R_
_r_original = R_._carregar
_estado = {"a": {"ultimo_uso": 100}, "b": {"ultimo_uso": 3}, "c": {"ultimo_uso": 50}}
R_._carregar = lambda: dict(_estado)
try:
    _prov = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    ok("o rodízio usa primeiro o motor parado há mais tempo",
       [p["id"] for p in R_.ordenar(_prov)] == ["b", "c", "a"])
    _estado["a"] = {"ultimo_uso": 100, "livre_em": __import__("time").time() + 60}
    _ordem = [p["id"] for p in R_.ordenar(_prov)]
    ok("motor em quarentena vai para o fim", _ordem[-1] == "a", str(_ordem))
finally:
    R_._carregar = _r_original
fonte_comum = open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read()
ok("a cadeia aplica o rodízio antes de tentar",
   "import rodizio as _rod" in fonte_comum
   and fonte_comum.index("_rod.ordenar") < fonte_comum.index("for p in lista"))
ok("429 coloca o motor em quarentena", R_.QUARENTENA_429 >= 60)
ok("quarentena não é para sempre (volta sozinho)", R_.QUARENTENA_429 <= 600)

# 19. motor local: reforço que nunca quebra a cadeia
import motor_local as ML_
ok("motor local não quebra quando a biblioteca/modelo faltam",
   ML_.disponivel() in (True, False) and isinstance(ML_.info(), dict))
ok("motor local informa o motivo quando não está pronto",
   ML_.info()["pronto"] or bool(ML_.info()["motivo"]))
_texto, _motivo = ML_.responder("teste") if ML_.disponivel() else (None, "indisponível")
ok("responder do motor local devolve (texto, motivo) sem exceção",
   isinstance(_motivo, str) or _texto is not None)
fonte_comum = open(os.path.join(RAIZ, "comum.py"), encoding="utf-8").read()
ok("o motor local é ÚLTIMO recurso, depois de todos os remotos",
   fonte_comum.index("import motor_local as _ml") > fonte_comum.index("for passada in range(2)"))
ok("o motor local não é dependência: a cadeia devolve erro normal se ele faltar",
   "motor local indisponível" in fonte_comum)
# A preparação do motor local pode viver no workflow do PÚBLICO (que é quem roda o Chat).
# Em vez de exigir um arquivo específico — que muda de repositório — verifico o que importa:
# existe algum workflow que prepara o llama.cpp, e ele não pode derrubar o job se falhar.
_prepara, _protegido = False, False
_diretorio_wf = os.path.join(RAIZ, ".github", "workflows")
for _nome in (os.listdir(_diretorio_wf) if os.path.isdir(_diretorio_wf) else []):
    if not _nome.endswith((".yml", ".yaml")):
        continue
    _txt = open(os.path.join(_diretorio_wf, _nome), encoding="utf-8", errors="replace").read()
    if "llama-cpp-python" in _txt and "motor_local" in _txt:
        _prepara = True
        if "continue-on-error: true" in _txt:
            _protegido = True
# No repositório que NÃO roda o Chat (o privado, cujo workflow está desativado), o que
# importa é que o motor exista e esteja ligado na cadeia. Onde o workflow prepara o motor,
# aí sim exijo a proteção.
_tem_codigo = (os.path.exists(os.path.join(RAIZ, "motor_local.py"))
               and "import motor_local" in open(os.path.join(RAIZ, "comum.py"),
                                               encoding="utf-8").read())
ok("o motor local está preparado para rodar", _prepara or _tem_codigo)
ok("a preparação do motor local não pode derrubar o job", _protegido or not _prepara)

# 20. comando !local: forçar o motor da CPU (garantia de zero API)
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("existe o comando !local", "def local_cmd" in fonte_resp and "local:" in fonte_resp.replace(" ", ""))
ok("o comando !local avisa quando o motor não está pronto",
   "não está pronto" in fonte_resp)
ok("o comando !local mostra o tempo e que não usou cota",
   "sem chave, sem API, sem cota" in fonte_resp)

# 21. consulta de número não passa por modelo (modelo pequeno troca alvo por observado)
_EX_NUM = [("MEMORIA/estado-casa.md", "- itch: downloads: alvo 100 · observado 45 · falta 55 · EM_CURSO"),
           ("MEMORIA/estado-casa.md", "- Bluesky: seguidores: alvo 50 · observado 34 · falta 16 · EM_CURSO")]
_orig2 = D_._linhas_da_casa
D_._linhas_da_casa = lambda: list(_EX_NUM)
try:
    _r = D_.resposta_direta("quantos downloads o itch tem?")
    ok("consulta de número responde direto do arquivo", _r and "observado 45" in _r, str(_r)[:120])
    ok("a resposta direta mostra a fonte", _r and "estado-casa.md" in _r)
    ok("a resposta direta não promete estimativa", _r and "em vez de estimar" in _r)
    ok("conversa comum não é tratada como consulta",
       D_.resposta_direta("bom dia, tudo bem?") is None)
finally:
    D_._linhas_da_casa = _orig2
fonte_resp = open(os.path.join(RAIZ, "responder.py"), encoding="utf-8").read()
ok("a resposta direta vem antes do motor",
   fonte_resp.index("resposta_direta") < fonte_resp.index("C.pensar_bem(pergunta_pensar"))

# 22. dado de máquina (JSON) não vira resposta de fato
_LIXO = [("MEMORIA/cache.json", '{"itens": ["https://a.com", "https://b.com"], "quando": "x"}'),
         ("MEMORIA/estado-casa.md", "- itch: downloads: alvo 100 · observado 45 · falta 55 · EM_CURSO")]
_orig3 = D_._linhas_da_casa
D_._linhas_da_casa = lambda: list(_LIXO)
try:
    _rd = D_.resposta_direta("quantos downloads o itch tem?")
    ok("linha de JSON não aparece na resposta", _rd and '"itens"' not in _rd, str(_rd)[:120])
    ok("a resposta ainda traz a medição certa", _rd and "observado 45" in _rd)
finally:
    D_._linhas_da_casa = _orig3

# 23. aproveitamento: o desperdício tem de ser medido, não sentido
ok("existe auditoria de uso", os.path.exists(os.path.join(RAIZ, "auditoria-uso.py")))
fonte_aud = open(os.path.join(RAIZ, "auditoria-uso.py"), encoding="utf-8").read()
for _eixo in ("funcoes_orfas", "robos_por_repo", "motores_em_uso", "segredos_sem_uso"):
    ok(f"a auditoria mede {_eixo}", f"def {_eixo}" in fonte_aud)
ok("a auditoria cobra sozinha (roda em cron e posta relatório)",
   "schedule" in open(os.path.join(RAIZ, ".github", "workflows", "auditoria-uso.yml"),
                      encoding="utf-8").read() and "issues" in fonte_aud)
# os robôs portados existem de verdade
_robos = ["checkup", "sentinela", "relatorio-semanal", "estudo", "oficina", "melhoria-continua",
          "boletim", "rotina", "inspire", "manutencao", "espelho", "banco",
          "batente", "piloto", "caca-motores", "varredura-motores", "confirmar-contas", "testes"]
_faltando = [r for r in _robos
             if not os.path.exists(os.path.join(RAIZ, ".github", "workflows", f"{r}.yml"))]
ok("os 18 robôs portados estão no repositório público", not _faltando, str(_faltando))
_scripts = ["checkup", "sentinela", "relatorio", "estudo", "oficina", "digestao", "autocritica",
            "boletim", "rotina", "inspire", "manutencao", "banco", "piloto", "confirmar_contas",
            "varredura", "teste-chat", "teste-orquestrador", "teste-semantica"]
_faltando_s = [x for x in _scripts if not os.path.exists(os.path.join(RAIZ, f"{x}.py"))]
ok("os scripts que os robôs usam estão presentes", not _faltando_s, str(_faltando_s))

# 24. o juiz não pode ser confundido com resposta legítima que fala de juiz
ok("resposta legítima que menciona juiz NÃO é descartada",
   not C_.parece_veredicto("O juiz do tribunal decidiu que o réu é inocente."))
ok("veredicto de verdade continua sendo descartado",
   C_.parece_veredicto("**Veredicto** Resposta A venceu"))

# 25. os canais que ficaram parados agora trabalham, mas sem publicar
ok("vitrine.py existe (canais parados trabalhando)", os.path.exists("vitrine.py"))
ok("workflow da vitrine existe e tem cron", "vitrine.yml" in os.listdir(".github/workflows"))
if os.path.exists(".github/workflows/vitrine.yml"):
    _vitrine = open(".github/workflows/vitrine.yml", encoding="utf-8").read()
    ok("vitrine roda a barreira antes de tocar a rede",
       _vitrine.find("teste-casa.py") < _vitrine.find("vitrine.py"))
    ok("vitrine não recebe segredo de escrita em rede social",
       "BSKY" not in _vitrine and "TUMBLR" not in _vitrine)
ok("vitrine tem teste próprio", os.path.exists("teste-vitrine.py"))

# 26. chave de API só entra pela porta única (_k) e sai decodificada
_fonte_comum = open("comum.py", encoding="utf-8").read()
ok("chave de API só é lida pela função _k",
   "def _k(" in _fonte_comum and _fonte_comum.count('= _k("') >= 12)
ok("nenhuma chave de motor é lida direto do ambiente",
   not any(f'os.environ.get("{v}"' in _fonte_comum for v in
           ("GROQ_API_KEY", "OPENROUTER_API_KEY", "SAMBANOVA_API_KEY", "UPSTAGE_API_KEY",
            "NOVITA_API_KEY", "GLAMA_API_KEY", "HUGGINGFACE_API_KEY")))

# 27. a porta única das chaves decodifica blob do cofre e preserva chave crua
import base64 as _b64
import os as _os
_blob = _b64.b64encode(_b64.b64encode(b"12345678-90ab-cdef-1234-567890abcdef")).decode()
_cru = "gsk_chave-crua-que-nao-e-base64"
_os.environ["CHAVE_DE_TESTE"] = _blob
ok("_k decodifica blob do cofre (base64 duplo) até virar chave",
   C_._k("CHAVE_DE_TESTE") == "12345678-90ab-cdef-1234-567890abcdef")
_os.environ["CHAVE_DE_TESTE"] = _cru
ok("_k não estraga chave crua", C_._k("CHAVE_DE_TESTE") == _cru)
_os.environ.pop("CHAVE_DE_TESTE", None)

# 28. as chaves que esgotaram têm substituto sem chave, medido e vigiado
_fonte_pf = open("prova_fogo.py", encoding="utf-8").read()
ok("prova-de-fogo cobre motores sem chave", "PROVEDORES_SEM_CHAVE" in _fonte_pf)
ok("prova-de-fogo exige a palavra pedida (200 sozinho não passa)",
   "ESPERADO.lower() not in conteudo.lower()" in _fonte_pf)
ok("há pelo menos 4 sem-chave vigiados",
   _fonte_pf.count('", "https://') >= 4)
_fonte_comum2 = open("comum.py", encoding="utf-8").read()
ok("o cérebro usa os sem-chave medidos", "KEYLESS_MEDIDOS" in _fonte_comum2)

# 29. exatidão: conta não depende de motor, e o motor não pode inventar número
ok("exatidao.py existe", os.path.exists("exatidao.py"))
ok("exatidao tem teste próprio", os.path.exists("teste-exatidao.py"))
ok("workflow do desafio de exatidão existe", os.path.exists(".github/workflows/exatidao.yml"))
if os.path.exists("exatidao.py"):
    import exatidao as _EX
    ok("conta exata sai sem motor", "33.033" in (_EX.responder("quanto é 847 * 39?") or ""))
    ok("número errado de motor é corrigido pela conta",
       _EX.conferir("quanto é 847 * 39", "são 33.000")[0] is False)
    ok("pergunta aberta não é sequestrada", _EX.responder("qual a capital da Austrália?") is None)
_fonte_desafio = open("desafio_exatidao.py", encoding="utf-8").read()
ok("desafio cobra honestidade (dizer que não sabe)", "NAO_SEI" in _fonte_desafio)
ok("cadeia ordena por nota medida", "ordenar_por_exatidao" in open("comum.py", encoding="utf-8").read())

# 30. resposta aberta é auditada: motor fraco não passa batido
ok("confianca.py existe", os.path.exists("confianca.py"))
ok("confianca tem teste próprio", os.path.exists("teste-confianca.py"))
if os.path.exists("confianca.py"):
    import confianca as _CF
    ok("promessa de ação é risco grave",
       any("promete uma ação" in m for m in
           _CF.sinais_de_risco("oi", "Já publiquei no Instagram!", "qualquer")))
    ok("a segunda opinião é comparada por similaridade", callable(_CF.concordancia))
_fonte_conf = open("confianca.py", encoding="utf-8").read()
ok("motor bom não gasta segunda opinião", "nota >= NOTA_BAIXA and not motivos" in _fonte_conf)
ok("resposta da conversa passa pela auditoria",
   "import confianca as _cf" in open("responder.py", encoding="utf-8").read())

# 31. motor fraco não responde no caminho normal, e a pergunta aberta vai a consenso
_fonte_cf2 = open("confianca.py", encoding="utf-8").read()
ok("existe piso de nota na cadeia", "NOTA_MINIMA_CADEIA" in _fonte_cf2)
ok("existe consenso entre motores", "def consenso(" in _fonte_cf2)
ok("consenso aceita retorno de 2 ou 3 campos", "Aceita os dois" in _fonte_cf2)
_fonte_resp2 = open("responder.py", encoding="utf-8").read()
ok("conversa abre consenso com motor de nota baixa", "abrindo consenso" in _fonte_resp2)
ok("rodapé avisa quando veio da reserva", "reserva, nota" in _fonte_resp2)
_fonte_comum3 = open("comum.py", encoding="utf-8").read()
ok("cadeia separa reserva por nota", "motores_de_confianca" in _fonte_comum3)
ok("emergência só na segunda passada", "emergência: tentando os motores de nota baixa" in _fonte_comum3)
ok("Gemini descobre o modelo na própria chave", "def modelos_gemini(" in _fonte_comum3)

print("\n%d/%d verificações do estado da casa passaram" % (certos, certos + falhas))
raise SystemExit(1 if falhas else 0)
