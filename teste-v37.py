# -*- coding: utf-8 -*-
"""Teste local da v3.7 (avisos e lembretes) — sem tocar no GitHub de verdade."""
import base64
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa

ARQUIVOS = {}
ISSUES = []
LABELS = []
TITULOS_ISSUES = []


def fake_gh(metodo, caminho, corpo=None):
    if "/contents/" in caminho:
        cam = caminho.split("/contents/")[1].split("?")[0]
        if metodo == "GET":
            if cam in ARQUIVOS:
                return {"sha": "abc", "content": base64.b64encode(ARQUIVOS[cam]).decode()}
            raise RuntimeError("404 not found")
        if metodo == "PUT":
            if cam in ARQUIVOS and "sha" not in corpo:
                # é exatamente o que a API real responde: criar só se não existir
                raise RuntimeError('GitHub API PUT /contents/... → HTTP 422: sha não informado (arquivo já existe)')
            ARQUIVOS[cam] = base64.b64decode(corpo["content"])
            return {"ok": True, "content": {"sha": "sha-" + cam[-12:]}}
    if metodo == "DELETE" and "/contents/" in caminho:
        cam = caminho.split("/contents/")[1].split("?")[0]
        ARQUIVOS.pop(cam, None)
        return {"ok": True}
    if metodo == "GET" and "/issues?state=all" in caminho:
        criadas = [{"number": 90 + i, "title": (c.get("title") or "")} for i, c in enumerate(ISSUES)]
        return [{"number": 400 + i, "title": t} for i, t in enumerate(TITULOS_ISSUES)] + criadas
    if metodo == "POST" and caminho.endswith("/issues"):
        ISSUES.append(corpo)
        return {"number": 90 + len(ISSUES)}
    if metodo == "POST" and caminho.endswith("/labels"):
        LABELS.append(corpo)
        return {"ok": True}
    return {}


C.gh = fake_gh
# A barreira se declara offline: moeda e clima precisam ser fixtures determinísticas,
# não depender de uma API pública eventualmente lenta/fora do ar.
def fake_cambio_numeros(moeda="USD"):
    return {"BRL": 5.0, "moeda": moeda.upper(), "fonte": "fixture offline"}


def fake_clima_numeros(cidade="Tobias Barreto"):
    return {"cidade": cidade, "temp_C": 30.0, "chuva": 20.0, "fonte": "fixture offline"}


C.cambio_numeros = fake_cambio_numeros
C.clima_numeros = fake_clima_numeros
falhas = []


def checar(rotulo, condicao, extra=""):
    print(("  ✓ " if condicao else "  ✗ ") + rotulo + (f"  [{extra}]" if extra else ""))
    if not condicao:
        falhas.append(rotulo)


print("1) parsing de quando (lembretes)")
for texto in ["amanhã 9h", "hoje 18h", "20/10 15:30", "daqui a 3 dias", "daqui a 2 horas", "sexta", "às 9h",
              "22/12/2026", "dia 25"]:
    iso = C._parse_quando(texto)
    checar(f"entendi {texto!r} → {iso}", bool(iso))
checar("texto vazio → None", C._parse_quando("") is None)
checar("hoje 18h é futuro", C._parse_quando("hoje 18h") > C.agora().isoformat())

print("\n2) criar avisos em linguagem natural (sem rede: ler_avisos/falso GitHub)")
criados = []
for pedido, tipo_esperado in [
    ("o dólar passar de 6", "cambio"),
    ("avise quando o euro ficar abaixo de 5,5", "cambio"),
    ("a temperatura em Tobias Barreto passar de 35", "clima"),
    ("chover em Aracaju", "clima"),
    ("o site https://exemplo.com cair", "site"),
    ("a página https://exemplo.com/promo mudar", "pagina"),
    ("sair novidade sobre godot", "noticia"),
]:
    texto = C.ferramenta_avisar(pedido)
    dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    ultimo = dados["avisos"][-1]
    criados.append(ultimo)
    checar(f"{pedido[:44]!r} → {ultimo['tipo']} | {ultimo['titulo']}",
           ultimo["tipo"] == tipo_esperado, texto.split("\n")[0][:60])
checar("mensagem sem entender pede exemplo", "Não entendi" in C.ferramenta_avisar("asdasd asdas"))
checar("4 avisos com id único", len({a["id"] for a in criados}) == len(criados))

print("\n3) lembretes")
texto = C.ferramenta_lembrete("pagar a conta | amanhã 9h")
dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
lembrete = dados["lembretes"][-1]
checar("lembrete gravado com texto limpo", lembrete["texto"] == "pagar a conta", lembrete["quando"])
checar("confirmação amigável", "Vou te lembrar" in texto, texto.split("\n")[0][:60])
C.ferramenta_lembrete("tomar água em daqui a 2 horas")
dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
checar("dois lembretes", len(dados["lembretes"]) == 2)
lista = C.ferramenta_lembretes("")
checar("lista mostra os lembretes", "pagar a conta" in lista and "tomar água" in lista)
checar("cancelar lembrete", "cancelei o lembrete" in C.ferramenta_lembretes("apagar 1").lower())

print("\n4) listar e cancelar avisos")
lista = C.ferramenta_avisos("")
checar("lista traz os avisos ativos", "Avisos ativos" in lista and "Dólar/BRL" in lista)
primeiro_id = criados[0]["id"]
checar("cancelar aviso", "cancelei o aviso" in C.ferramenta_avisos(f"apagar {primeiro_id}").lower())

print("\n5) cotação em fixture offline")
try:
    cot = C.cambio_numeros("USD")
    checar(f"cambio_numeros → USD {cot.get('BRL')} ({cot.get('fonte')})", bool(cot.get("BRL")))
except Exception as e:
    checar(f"cambio_numeros falhou: {e}", False)

print("\n6) clima em fixture offline")
try:
    cl = C.clima_numeros("Tobias Barreto")
    checar(f"clima_numeros → {cl.get('cidade')} {cl.get('temp_C')}°C chuva {cl.get('chuva')}%", cl.get("temp_C") is not None)
except Exception as e:
    checar(f"clima_numeros falhou: {e}", False)

print("\n7) avaliação de avisos com dados do banco")
try:
    cot = C.cambio_numeros("USD")
    banco_fake = {"cambio": {"USD_BRL": cot.get("BRL"), "fonte": "teste"},
                  "clima": {"temp_C": "30", "umidade": "70", "chuva_prob": "20", "cidade": "Tobias Barreto"},
                  "sites": {"Site oficial": {"url": "https://exemplo.com", "no_ar": False}}}
    a = {"tipo": "cambio", "moeda": "USD", "valor": 1.0, "op": "acima", "estado": "armado", "id": 1,
         "titulo": "Dólar acima de 1"}
    disparou, detalhe, erro = C._av_cambio(a, banco_fake)
    checar(f"câmbio acima de 1 dispara ({detalhe[:48] if detalhe else erro})", disparou is True and not erro)
    a2 = dict(a, valor=999.0)
    checar("câmbio acima de 999 não dispara", C._av_cambio(a2, banco_fake)[0] is False)
    a3 = {"tipo": "clima", "cidade": None, "modo": "temperatura", "valor": 20.0, "op": "acima"}
    checar("temperatura 30 > 20 dispara", C._av_clima(a3, banco_fake)[0] is True)
    a4 = {"tipo": "clima", "cidade": None, "modo": "chuva", "valor": 50.0, "op": "acima"}
    checar("chuva 20% < 50% não dispara", C._av_clima(a4, banco_fake)[0] is False)
    a5 = {"tipo": "site", "url": "https://exemplo.com", "modo": "cair"}
    checar("site fora do ar dispara o aviso de queda", C._av_site(a5, banco_fake)[0] is True)
except Exception as e:
    checar(f"avaliação falhou: {e!r}", False)

print("\n8) disparo completo (checar_avisos) e notificação")
try:
    ARQUIVOS["MEMORIA/avisos.json"] = json.dumps({
        "versao": 1, "avisos": [{"id": 1, "tipo": "site", "titulo": "Site fora do ar: https://exemplo.com",
                                 "url": "https://exemplo.com", "modo": "cair", "ativo": True, "estado": "armado",
                                 "vezes": 0}], "lembretes": [], "historico": []}).encode()
    ARQUIVOS["MEMORIA/banco.json"] = json.dumps({
        "cambio": {"USD_BRL": 5.0, "fonte": "teste"},
        "sites": {"Site oficial": {"url": "https://exemplo.com", "no_ar": False}}}).encode()
    r = C.checar_avisos(incluir_paginas=False, incluir_noticias=False)
    checar(f"disparou 1 aviso ({r['disparados']})", len(r["disparados"]) == 1)
    checar(f"1 conversa de aviso criada (total {len(ISSUES)})", len(ISSUES) == 1)
    corpo = ISSUES[0]["body"] if ISSUES else ""
    checar("a conversa menciona o dono", "@reboclbrank-max" in corpo)
    checar("usa a etiqueta 'aviso'", ISSUES[0].get("labels") == ["aviso"] if ISSUES else False)
    dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    checar("estado virou 'disparado' e contou 1 vez",
           dados["avisos"][0]["estado"] == "disparado" and dados["avisos"][0]["vezes"] == 1)
    checar("entrou no histórico", len(dados["historico"]) == 1)
    r2 = C.checar_avisos(incluir_paginas=False, incluir_noticias=False)
    checar("não repete o aviso na mesma hora (transição)", len(r2["disparados"]) == 0)
except Exception as e:
    checar(f"checar_avisos falhou: {e!r}", False)

print("\n9) lembrete vencido é entregue uma vez")
try:
    dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    dados["lembretes"] = [{"id": 9, "texto": "teste de lembrete",
                           "quando": (C.agora().isoformat(timespec="seconds")), "feito": False}]
    ARQUIVOS["MEMORIA/avisos.json"] = json.dumps(dados).encode()
    antes = len(ISSUES)
    entregues = C.checar_lembretes()
    checar(f"lembrete entregue: {entregues}", len(entregues) == 1 and len(ISSUES) == antes + 1)
    checar("não entrega de novo", C.checar_lembretes() == [])
except Exception as e:
    checar(f"checar_lembretes falhou: {e!r}", False)

print("\n10) ferramentas e modo direto")
checar("ferramenta_avisar no mapa", C.executar_ferramenta("AVISAR", "o dólar passar de 7")[:9] == "Combinado")
checar("AVISOS no mapa", "Avisos ativos" in C.executar_ferramenta("AVISOS", ""))
checar("LEMBRETE no mapa", "Vou te lembrar" in C.executar_ferramenta("LEMBRETE", "dormir | amanhã 22h"))
checar("LEMBRETES no mapa", "Lembretes marcados" in C.executar_ferramenta("LEMBRETES", ""))
checar("VIGIAR sem url explica", "vigiar:" in C.executar_ferramenta("VIGIAR", ""))
checar("marcador [[AVISAR: ...]] reconhecido", bool(C.RE_FERRAMENTA.search("texto [[AVISAR: o dólar passar de 6]]")))
checar("marcador [[LEMBRETE: ...]] reconhecido", bool(C.RE_FERRAMENTA.search("[[LEMBRETE: dormir | hoje 22h]]")))
checar("system fala de avisos", "Avisos e lembretes" in C.montar_system())
checar("teu nome no system (ferramentas novas)", "[[AVISAR:" in C.montar_system())

print("\n11) trava contra aviso repetido por execuções em paralelo")
try:
    agora_iso = C.agora().isoformat(timespec="seconds")
    ARQUIVOS["MEMORIA/avisos.json"] = json.dumps({
        "versao": 1,
        "avisos": [{"id": 5, "tipo": "site", "titulo": "Site fora do ar: https://exemplo.com",
                    "url": "https://exemplo.com", "modo": "cair", "ativo": True, "estado": "armado",
                    "vezes": 1, "ultimo_disparo": agora_iso}],
        "lembretes": [], "historico": []}).encode()
    ARQUIVOS["MEMORIA/banco.json"] = json.dumps({
        "sites": {"Site oficial": {"url": "https://exemplo.com", "no_ar": False}}}).encode()
    antes = len(ISSUES)
    r = C.checar_avisos(incluir_paginas=False, incluir_noticias=False)
    checar("não repete dentro de 30 min (carimbos iguais)", len(r["disparados"]) == 0 and len(ISSUES) == antes)
    dados = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    checar("a corrida ficou carimbada como disparada", dados["avisos"][0]["estado"] == "disparado")

    # 2) dedupe por título na hora de notificar (mesmo aviso já enviado há minutos)
    TITULOS_ISSUES.append("🔔 Site fora do ar: https://exemplo.com")
    canais = C.notificar("Site fora do ar: https://exemplo.com", "de novo", tipo="aviso")
    checar("notificar recusa repetir o mesmo título na janela", canais == [] and len(ISSUES) == antes)
    canais = C.notificar("Site fora do ar: https://exemplo.com", "de novo", tipo="teste")
    checar("teste explícito não é bloqueado pelo dedupe", len(canais) == 1)
    TITULOS_ISSUES.clear()

    # 3) trava atômica: duas execuções no MESMO instante reclamam o mesmo aviso
    antes = len(ISSUES)
    for k in [k for k in ARQUIVOS if k.startswith("MEMORIA/trava/")]:
        ARQUIVOS.pop(k)
    t1 = C._reclamar_aviso("Aviso de corrida simultânea")
    t2 = C._reclamar_aviso("Aviso de corrida simultânea")
    checar(f"1ª execução pega a trava ({str(t1)[:22]}) e a 2ª é barrada ({t2})", bool(t1) and t2 is False)
    # 4) a trava fica presa a janela inteira: execução que começa segundos depois também é barrada
    for k in [k for k in ARQUIVOS if k.startswith("MEMORIA/trava/")]:
        ARQUIVOS.pop(k)   # vira a janela de 15 min: a trava antiga já não vale
    c1 = C.notificar("Aviso de corrida simultânea", "primeira execução", tipo="aviso")
    c2 = C.notificar("Aviso de corrida simultânea", "segunda execução", tipo="aviso")
    checar(f"1ª avisa ({c1}) e a 2ª (segundos depois) é barrada ({c2})", len(c1) == 1 and c2 == [])
    checar("só uma conversa criada no total", len(ISSUES) == antes + 1)
    checar("a trava continua no repositório (segura a janela)",
           bool([k for k in ARQUIVOS if k.startswith("MEMORIA/trava/")]))
    checar("limpeza de trava antiga exista e não quebra", C.limpar_travas_antigas() == 0)
except Exception as e:
    checar(f"trava de duplicata falhou: {e!r}", False)

print("\n12) gravação com junção (execução paralela não apaga o histórico da outra)")
try:
    agora_iso = C.agora().isoformat(timespec="seconds")
    base = {"versao": 1, "avisos": [{"id": 7, "tipo": "clima", "titulo": "Calor", "cidade": "Tobias Barreto",
                                     "modo": "temperatura", "valor": 30, "op": "acima", "ativo": True,
                                     "estado": "armado", "vezes": 0, "ultimo_disparo": None}],
            "lembretes": [{"id": 3, "texto": "entregar", "quando": agora_iso, "feito": False}],
            "historico": [{"quando": agora_iso, "titulo": "Histórico antigo", "texto": "x", "canais": ["a"], "tipo": "aviso"}]}
    ARQUIVOS["MEMORIA/avisos.json"] = json.dumps(base).encode()
    # execução A: dispara e grava o histórico dela
    dados_a = C.ler_avisos()
    dados_a["historico"].append({"quando": agora_iso, "titulo": "Aviso da execução A", "texto": "a",
                                 "canais": ["conversa #1"], "tipo": "aviso"})
    dados_a["avisos"][0]["estado"] = "disparado"
    dados_a["avisos"][0]["vezes"] = 1
    dados_a["avisos"][0]["ultimo_disparo"] = agora_iso
    C.salvar_avisos(dados_a, "A")
    # execução B: começou antes, tem o retrato velho na mão (corrida clássica)
    dados_b = json.loads(json.dumps(base))
    dados_b["avisos"][0]["estado"] = "disparado"
    dados_b["avisos"][0]["vezes"] = 1
    C.salvar_avisos(dados_b, "B")
    final = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    titulos = [h["titulo"] for h in final["historico"]]
    checar("o histórico das duas execuções sobreviveu", "Aviso da execução A" in titulos and "Histórico antigo" in titulos)
    checar("o carimbo do disparo não se perdeu", bool(final["avisos"][0]["ultimo_disparo"]))
    # lembrete entregue por A não pode ser reentregue por B
    dados_a = C.ler_avisos(); dados_a["lembretes"][0]["feito"] = True; dados_a["lembretes"][0]["feito_em"] = agora_iso
    C.salvar_avisos(dados_a, "A lembrete")
    dados_b = json.loads(json.dumps(base))
    C.salvar_avisos(dados_b, "B lembrete")
    final = json.loads(ARQUIVOS["MEMORIA/avisos.json"])
    checar("lembrete entregue continua marcado como entregue", final["lembretes"][0]["feito"] is True)
except Exception as e:
    checar(f"junção falhou: {e!r}", False)

# ============ ferramentas keyless novas (busca-leitor, tradução, cripto, CNPJ, fotos) ============
_buscar_bytes_original = C._buscar_bytes

MARKDOWN_DDGLITE = """Title: teste at DuckDuckGo

URL Source: https://lite.duckduckgo.com/lite/?q=teste

Markdown Content:
1.[Primeiro resultado - GitHub](https://duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Fteste%2Fum&rut=abc)
Resumo do primeiro resultado com **negrito**
github.com/teste/um 2025-09-29T15:06:00.0000000

2.[Segundo resultado - Site](https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexemplo.com%2Fdois&rut=def)
Resumo do segundo resultado
exemplo.com 2025-09-28
"""

HTML_DDGLITE = """<html><table>
<tr><td>1.</td><td><a rel="nofollow" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemplo.com%2Fa&rut=x">Resultado A</a></td></tr>
<tr><td class="result-snippet">Resumo A aqui</td></tr>
</table></html>"""


def _fake_buscar_bytes(url, headers=None, limite=0, timeout=0):
    if "r.jina.ai/" in url and "lite.duckduckgo.com" in url:
        return MARKDOWN_DDGLITE.encode("utf-8"), "text/plain", {}
    if "api.allorigins.win" in url:
        return HTML_DDGLITE.encode("utf-8"), "text/html", {}
    if "mymemory.translated.net" in url:
        return json.dumps({"responseData": {"translatedText": "Hello brain"}}).encode("utf-8"), "application/json", {}
    if "coingecko.com" in url:
        return json.dumps({"bitcoin": {"brl": 411000.0, "usd": 81900.0, "brl_24h_change": -1.6}}).encode("utf-8"), "application/json", {}
    if "brasilapi.com.br/api/cnpj" in url:
        return json.dumps({"razao_social": "EMPRESA TESTE SA", "nome_fantasia": "TESTE",
                           "descricao_situacao_cadastral": "ATIVA", "data_situacao_cadastral": "2020-01-01",
                           "cnae_fiscal_descricao": "Desenvolvimento de jogos",
                           "municipio": "LAGARTO", "uf": "SE", "data_inicio_atividade": "2020-01-01"}).encode("utf-8"), "application/json", {}
    if "api.openverse.org" in url:
        return json.dumps({"results": [{"url": "https://img.example/a.jpg",
                                        "foreign_landing_url": "https://exemplo/pagina",
                                        "creator": "Fulana", "license": "by", "license_version": "2.0"}]}).encode("utf-8"), "application/json", {}
    raise RuntimeError("url inesperada no fake: " + url)


C._buscar_bytes = _fake_buscar_bytes
try:
    itens_md = C._parse_ddg_lite(MARKDOWN_DDGLITE, 5)
    checar("parser ddg-lite lê a variante markdown do leitor", len(itens_md) >= 2)
    checar("link uddg é decodificado para o endereço real",
           bool(itens_md) and itens_md[0]["url"].startswith("https://github.com/teste/um"))
    checar("resumo vem da linha seguinte (e ** limpo)", "**" not in itens_md[0]["resumo"] and itens_md[0]["resumo"].startswith("Resumo do primeiro"))
    itens_html = C._parse_ddg_lite(HTML_DDGLITE, 5)
    checar("parser ddg-lite lê a variante HTML (proxy)",
           len(itens_html) == 1 and itens_html[0]["url"] == "https://exemplo.com/a" and itens_html[0]["resumo"] == "Resumo A aqui")
    via_leitor = C._busca_ddg_leitor("teste", 3)
    checar("busca via leitor devolve resultados", len(via_leitor) >= 2)

    traducao = C.ferramenta_traduzir("olá mundo | inglês")
    checar("tradução (MyMemory simulado) sai em inglês", "Hello brain" in traducao and "PT → EN" in traducao)
    cambio = C.ferramenta_cambio("BTC")
    checar("cripto sai em reais pt-BR", "R$" in cambio and "411.000,00" in cambio and "CoinGecko" in cambio)
    cnpj_txt = C.ferramenta_cnpj("00.000.000/0001-91")
    checar("CNPJ traz a razão social", "EMPRESA TESTE SA" in cnpj_txt and "LAGARTO/SE" in cnpj_txt)
    checar("CNPJ curto pede 14 números", "14 números" in C.ferramenta_cnpj("123"))
    foto = C.ferramenta_foto("caveira")
    checar("foto real vem com atribuição", foto.startswith("📷") and "BY 2.0" in foto and "img.example/a.jpg" in foto)
    checar("dispatcher aceita TRADUZIR/CNPJ/FOTO",
           all("desconhecida" not in C.executar_ferramenta(t, a) for t, a in
               (("TRADUZIR", "oi | inglês"), ("CNPJ", ""), ("FOTO", ""))))
    fonte_comum = io.open("comum.py", encoding="utf-8").read()
    checar("prompt do cérebro cita os 3 marcadores novos",
           all(m in fonte_comum for m in ("[[TRADUZIR:", "[[CNPJ:", "[[FOTO:", "moeda ou cripto")))
finally:
    C._buscar_bytes = _buscar_bytes_original

# ============ anti-bloqueio (recusa pulada, internet toda) ============
checar("recusa em pt é detectada", C._parece_recusa("Não posso ajudar com isso."))
checar("recusa em en é detectada", C._parece_recusa("I'm unable to help with that request."))
checar("'como uma IA' é detectada", C._parece_recusa("Como uma IA, não posso gerar esse conteúdo."))
checar("resposta normal não vira recusa", not C._parece_recusa("Não posso esquecer: já anotei com [[ANOTAR: prazo]]."))
texto_longo = "Sobre gore em jogos: não posso recomendar demais estudar Silent Hill. " * 30
checar("texto longo que cita 'não posso' NÃO é recusa", not C._parece_recusa(texto_longo))
fonte_comum = io.open("comum.py", encoding="utf-8").read()
checar("prompt tem a trava anti-recusa",
       "nunca censure" in fonte_comum and "aviso de conteúdo" in fonte_comum and
       "TRABALHO NORMAL" in fonte_comum)
checar("prompt liberou a internet por todos os caminhos",
       "internet é TODA sua" in fonte_comum and "proxy aberto" in fonte_comum)

# ============ projeto gênio (raciocínio silencioso, chão de fatos, lições) ============
checar("limpar pensar remove bloco fechado", C._limpar_pensar("<pensar>2+2=4</pensar>A resposta é 4.") == "A resposta é 4.")
checar("limpar pensar com tag aberta guarda o que veio antes", C._limpar_pensar("Vamos lá <pensar>hmm pensou") == "Vamos lá")
checar("limpar pensar não mexe em texto normal", C._limpar_pensar("resposta direta") == "resposta direta")
checar("pergunta factual pede chão de fatos", C._precisa_chao("qual a capital do brasil?"))
checar("pergunta criativa NÃO pede chão de fatos", not C._precisa_chao("escreva uma história sobre um dragão"))
checar("oi tudo bem NÃO pede chão de fatos", not C._precisa_chao("oi, tudo bem?"))
_gravar_original = C.acrescentar_memoria
gravadas = []
C.acrescentar_memoria = lambda cam, linha, titulo=None: gravadas.append((cam, linha)) or True
try:
    checar("dono ensinou → lição gravada em MEMORIA/licoes.md",
           C._capturar_licao("de agora em diante sempre responda em tópicos") is True
           and len(gravadas) == 1 and gravadas[0][0] == C.ARQ_LICOES and "tópicos" in gravadas[0][1])
    checar("conversa comum não vira lição", C._capturar_licao("oi, tudo bem?") is False and len(gravadas) == 1)
    resposta = C.ferramenta_aprender("sempre citar fontes quando pesquisar")
    checar("APRENDER confirma a lição gravada", "para sempre" in resposta and len(gravadas) == 2)
    checar("dispatcher conhece APRENDER", "desconhecida" not in C.executar_ferramenta("APRENDER", "teste de regra"))
finally:
    C.acrescentar_memoria = _gravar_original
fonte_comum = io.open("comum.py", encoding="utf-8").read()
checar("prompt manda pensar em silêncio", "pense PRIMEIRO em silêncio" in fonte_comum and "<pensar>" in fonte_comum)
checar("prompt tem a seção de lições", "Lições que o dono ensinou" in fonte_comum and "{licoes" in fonte_comum)
checar("responder injeta contexto ao vivo", "Contexto ao vivo da internet" in fonte_comum)
checar("saída de 6000 tokens (raciocínio cabe)", "MAX_SAIDA = 6000" in fonte_comum)

# ============ e-mail da empresa (guardas, decodificação, dispatcher) ============
import base64 as _b64
assunto_codificado = "=?UTF-8?B?" + _b64.b64encode("Olá, mundo".encode()).decode() + "?="
checar("decodifica cabeçalho MIME", C._decodificar_cabecalho(assunto_codificado) == "Olá, mundo")
checar("cabeçalho simples passa reto", C._decodificar_cabecalho("Teste simples") == "Teste simples")
msg_config = C.ferramenta_email("")
checar("sem senha de app → mensagem de configuração (não crash)",
       "senha de app" in msg_config and "não está ligado" in msg_config)
checar("ler caixa sem config → mesma guarda", "senha de app" in C.ferramenta_caixa("alerta"))
checar("dispatcher conhece EMAIL e CAIXA",
       all("desconhecida" not in C.executar_ferramenta(t, "") for t in ("EMAIL", "CAIXA")))
fonte_comum = io.open("comum.py", encoding="utf-8").read()
checar("prompt cita EMAIL e CAIXA", "[[EMAIL: assunto | texto]]" in fonte_comum and "[[CAIXA: termo]]" in fonte_comum)
checar("usa smtp/imap do Google com senha de app",
       "smtp.gmail.com" in fonte_comum and "imap.gmail.com" in fonte_comum and "EMAIL_SENHA_APP" in fonte_comum)

print("\n" + ("TUDO OK ✓" if not falhas else f"FALHAS ({len(falhas)}): " + "; ".join(falhas)))
sys.exit(1 if falhas else 0)
