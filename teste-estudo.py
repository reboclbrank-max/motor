#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste local do estudo autodidata — sem rede e sem tocar no GitHub de verdade."""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum as C  # noqa
import estudo as E  # noqa

store = {}
gravadas = []
C.ler_remoto = lambda caminho, padrao="": store.get(caminho, padrao)
C.escrever_remoto = lambda caminho, conteudo, mensagem="": store.update({caminho: conteudo}) or True
C.acrescentar_memoria = lambda caminho, linha, titulo=None: gravadas.append((caminho, linha)) or True
C.buscar_web = lambda consulta, quantos=6: (
    [{"titulo": "Guia de terror", "url": "https://exemplo.com/terror", "resumo": "guia"},
     {"titulo": "Outro guia", "url": "https://exemplo.com/dois", "resumo": "guia 2"}], "Fonte de Teste")
C.abrir_url = lambda url, limite_texto=6000: "Material de estudo suficiente para destilar lições práticas. " * 20
C.chamar_llm = lambda mensagens, system=None, **kw: ("lição um\nlição dois\nlição três\nlição quatro\nlição cinco", "Motor Falso", None)

ok = True


def checar(nome, cond):
    global ok
    print(("  ✓ " if cond else "  ✗ FALHOU ") + nome)
    ok = ok and cond


def liberar_dia():
    st = E._estado_carregar()
    st["ultimo_dia"] = "01/01/2000"
    store[E.ARQ_ESTUDO_ESTADO] = json.dumps(st, ensure_ascii=False)


r1 = E.estudar()
checar("primeiro dia estuda o primeiro tema", "marketing-indie" in r1 and "✅" in r1)
checar("lições foram para o caderno", len(gravadas) == 1 and gravadas[0][0] == E.arq_estudo_hoje() and "lição um" in gravadas[0][1])
estado = E._estado_carregar()
checar("estado avança o índice e marca o dia", estado["indice"] == 1 and estado["ultimo_tema"] == "marketing-indie")

r2 = E.estudar()
checar("mesmo dia não estuda de novo", "volto amanhã" in r2 and len(gravadas) == 1)

liberar_dia()
r3 = E.estudar()
checar("dia seguinte segue para o próximo tema (grade nova)", "marketing-ganchos" in r3 and len(gravadas) == 2)

r4 = E.estudar("folclore-norte")
checar("tema pedido à mão estuda fora da fila", "folclore-norte" in r4 and len(gravadas) == 3)
r5 = E.estudar("tema-inexistente")
checar("tema desconhecido avisa a lista", "Não conheço" in r5)

C.chamar_llm = lambda mensagens, system=None, **kw: (None, None, "sem motor")
liberar_dia()
r6 = E.estudar()
checar("sem motor → mensagem mansa, sem crash", "Nenhum motor" in r6)

C.buscar_web = lambda consulta, quantos=6: ([], None)
liberar_dia()
r7 = E.estudar()
checar("busca vazia → tenta amanhã", "tento de novo amanhã" in r7)

# ---- caixa do Gmail virando conhecimento ----
import autocritica as A

C.ferramenta_caixa = lambda termo="": ("📬 1 e-mail(s) novo(s):\n✉️ Novo jogo de terror brasileiro\n"
                                       "  https://exemplo.com/noticia-terror texto da novidade")
C.chamar_llm = lambda mensagens, system=None, **kw: ("lição um\nlição dois\nlição três\nlição quatro\nlição cinco", "Motor Falso", None)
liberar_dia()
r8 = E.estudar_caixa()
checar("caixa: novidade estudada e guardada no caderno",
       "✅ Estudei a novidade da caixa" in r8 and len(gravadas) == 4 and "da caixa do Gmail" in gravadas[-1][1] and "lição um" in gravadas[-1][1])
C.ferramenta_caixa = lambda termo="": "📬 Caixa de entrada sem e-mails novos"
checar("caixa vazia → mensagem mansa", "nada para estudar" in E.estudar_caixa())
C.ferramenta_caixa = lambda termo="": ("📬 1 e-mail(s) novo(s):\n✉️ Sem link útil aqui\n  só texto, nada")
checar("caixa sem link → avisa", "não tinham link" in E.estudar_caixa())

# ---- autocrítica diária ----
store[C.ARQ_DIARIO] = "- 12:00 respondi pergunta sobre save\n- 13:00 postei no canal"
store[C.ARQ_RESPOSTAS] = json.dumps([{"pergunta": "meu save quebrou", "ruim": True}])
C.chamar_llm = lambda mensagens, system=None, **kw: ("- revisar saves com backup rotativo\n- testar respostas antes de enviar", "Motor Falso", None)
r9 = A.autocriticar()
checar("autocrítica grava lições assinadas (auto) em licoes.md",
       "Autocrítica gravada" in r9 and len(gravadas) == 5 and gravadas[-1][0] == C.ARQ_LICOES
       and "(auto)" in gravadas[-1][1])
store[C.ARQ_DIARIO] = ""
store[C.ARQ_RESPOSTAS] = "[]"
checar("sem material → sem autocrítica forçada", "Sem material" in A.autocriticar())

# ---- modo máximo no comum (motor novo, agilidade, olhos) ----
fonte_comum = io.open("comum.py", encoding="utf-8").read()
checar("motor grátis provado GLM-5.3-Flash na fila", '"GLM-5.3-Flash"' in fonte_comum)
checar("agilidade: motor lento vai pro fim aos 30s", "> 30000" in fonte_comum)
checar("olhos: dispatcher e prompt", '"OLHAR"' in fonte_comum and "[[OLHAR:" in fonte_comum)
checar("olhos: cena (BLIP) e OCR previstos", "blip-image-captioning" in fonte_comum and "pytesseract" in fonte_comum)
checar("dispatcher aceita OLHAR (guarda de URL)", "endereço da imagem" in C.executar_ferramenta("OLHAR", ""))

# ---- modo contínuo 24h (forcar ignora o freio diário) ----
C.chamar_llm = lambda mensagens, system=None, **kw: ("lição um\nlição dois\nlição três\nlição quatro\nlição cinco", "Motor Falso", None)
C.buscar_web = lambda consulta, quantos=6: ([{"titulo": "Guia", "url": "https://exemplo.com/g", "resumo": "g"}], "Fonte")
C.abrir_url = lambda url, limite_texto=6000: "Material de estudo suficiente. " * 30
liberar_dia()
antes = len(gravadas)
r_c1 = E.estudar(forcar=True)
r_c2 = E.estudar(forcar=True)
checar("modo contínuo: estuda seguido sem freio diário",
       "✅" in r_c1 and "✅" in r_c2 and len(gravadas) == antes + 2)
st = E._estado_carregar()
checar("modo contínuo avança a rodada de temas", st["indice"] != 0 or st["ultimo_tema"] != "marketing-indie")

print("\nTESTE ESTUDO:", "TUDO OK ✓" if ok else "FALHOU ✗")
sys.exit(0 if ok else 1)
