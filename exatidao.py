#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exatidão sem modelo: conta, data, conversão e conferência de número.

Por que existe: medimos os modelos pequenos errando aritmética (0,5B, 1,5B e 3B erraram
as três contas do teste do motor local), e o motor forte da casa é um só — o Groq. Conta
não é tarefa de linguagem: é conta. Aqui ela sai exata, offline, em microssegundos, sem
chave, sem cota e sem poder inventar.

O que este módulo NÃO faz: interpretar pergunta aberta. Ele só responde quando reconhece
uma operação verificável. Fora disso devolve None e a pergunta segue para o motor.
"""
import ast
import datetime as _dt
import operator
import re

# ---------------------------------------------------------------- conta
_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _avaliar(no):
    """Avalia só aritmética. Nome, chamada, atributo e string são recusados."""
    if isinstance(no, ast.Expression):
        return _avaliar(no.body)
    if isinstance(no, ast.Constant):
        if isinstance(no.value, (int, float)) and not isinstance(no.value, bool):
            return no.value
        raise ValueError("constante não numérica")
    if isinstance(no, ast.BinOp) and type(no.op) in _OPS:
        esquerda, direita = _avaliar(no.left), _avaliar(no.right)
        if isinstance(no.op, ast.Pow) and abs(direita) > 64:
            raise ValueError("potência grande demais")
        return _OPS[type(no.op)](esquerda, direita)
    if isinstance(no, ast.UnaryOp) and type(no.op) in _OPS:
        return _OPS[type(no.op)](_avaliar(no.operand))
    raise ValueError("expressão não permitida")


def calcular(expressao):
    """Devolve o número ou None. Aceita '847*39', '2+2', '(3+4)/2'."""
    limpa = expressao.strip().replace("×", "*").replace("x", "*").replace("÷", "/") \
        .replace("^", "**").replace(",", ".")
    limpa = re.sub(r"[^0-9+\-*/(). ]", "", limpa).strip()
    if not limpa or not re.search(r"\d", limpa):
        return None
    try:
        valor = _avaliar(ast.parse(limpa, mode="eval"))
    except Exception:
        return None
    return valor


def formatar_numero(valor):
    """Número do jeito que se escreve no Brasil: 33033 → 33.033."""
    if valor is None:
        return ""
    if isinstance(valor, float):
        if abs(valor - round(valor)) < 1e-9:
            valor = int(round(valor))
        else:
            return f"{valor:,.4f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,}".replace(",", ".")


# ---------------------------------------------------------------- reconhecimento
RE_CONTA = re.compile(
    r"(?:quanto\s+(?:é|e|vale|dá|da)|calcul[ae]|resultado\s+de|conta)\s*[:\-]?\s*"
    r"([0-9(][0-9\s,.()]*(?:\+|\-|\*|/|×|÷|\^)[0-9\s,.()+\-*/×÷^]+)", re.IGNORECASE)
RE_CONTA_PURA = re.compile(r"^\s*([0-9(][0-9\s,.()]*[+\-*/×÷^][0-9\s,.()+\-*/×÷^]+)\s*\??\s*$")
RE_PORCENTO = re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:de|do|da)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
RE_VARIACAO = re.compile(
    r"(?:de|entre)\s+(\d+(?:[.,]\d+)?)\s+(?:para|a)\s+(\d+(?:[.,]\d+)?)", re.IGNORECASE)


def _troca_x_por_vezes(pergunta):
    """'37 x 6' é multiplicação; 'x' entre dígitos nunca é letra."""
    return re.sub(r"(?<=[0-9])\s*[xX]\s*(?=[0-9(])", "*", pergunta)


def responder_conta(pergunta):
    """Conta reconhecida na pergunta → resposta exata. Senão None."""
    if not pergunta:
        return None
    pergunta = _troca_x_por_vezes(pergunta)
    achado = RE_CONTA.search(pergunta) or RE_CONTA_PURA.match(pergunta)
    if achado:
        bruto = achado.group(1)
        valor = calcular(bruto)
        if valor is not None:
            return (f"**{formatar_numero(valor)}**\n\n_(conta feita aqui, sem passar por "
                    f"modelo: `{bruto.strip()}`)_")
    achado = RE_PORCENTO.search(pergunta)
    if achado:
        taxa = float(achado.group(1).replace(",", "."))
        base = float(achado.group(2).replace(",", "."))
        valor = taxa * base / 100.0
        return (f"**{formatar_numero(valor)}** ({formatar_numero(taxa)}% de "
                f"{formatar_numero(base)})\n\n_(conta feita aqui, sem modelo)_")
    return None


def responder_variacao(pergunta):
    """'subiu de 40 para 52, quanto por cento?' → 30%."""
    if not pergunta or not re.search(r"por\s*cento|percentual|%", pergunta, re.IGNORECASE):
        return None
    achado = RE_VARIACAO.search(pergunta)
    if not achado:
        return None
    antes = float(achado.group(1).replace(",", "."))
    depois = float(achado.group(2).replace(",", "."))
    if antes == 0:
        return None
    variacao = (depois - antes) / antes * 100.0
    sentido = "aumento" if variacao >= 0 else "queda"
    return (f"**{formatar_numero(abs(variacao))}%** de {sentido} "
            f"({formatar_numero(antes)} → {formatar_numero(depois)})\n\n_(conta feita aqui, sem modelo)_")


# ---------------------------------------------------------------- data
RE_DIAS_ENTRE = re.compile(
    r"(?:quantos?\s+dias?)\s+(?:de|entre)\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+"
    r"(?:e|a|até)\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", re.IGNORECASE)
RE_DIA_SEMANA = re.compile(
    r"(?:que|qual)\s+dia\s+(?:da\s+semana|é|foi|cai)\D{0,12}(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?",
    re.IGNORECASE)
RE_FEVEREIRO = re.compile(r"fevereiro\s+de\s+(\d{4})", re.IGNORECASE)
_DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sábado", "domingo")


def _data(dia, mes, ano, padrao=None):
    ano = int(ano) if ano else (padrao or _dt.date.today().year)
    if ano < 100:
        ano += 2000
    return _dt.date(ano, int(mes), int(dia))


def responder_data(pergunta):
    """Data reconhecida → resposta exata. Senão None."""
    if not pergunta:
        return None
    achado = RE_DIAS_ENTRE.search(pergunta)
    if achado:
        try:
            inicio = _data(*achado.group(1, 2, 3))
            fim = _data(*achado.group(4, 5, 6), padrao=inicio.year)
        except ValueError:
            return None
        dias = (fim - inicio).days
        return (f"**{abs(dias)} dias**\n\n_({inicio.strftime('%d/%m/%Y')} → "
                f"{fim.strftime('%d/%m/%Y')}, contado aqui, sem modelo)_")
    achado = RE_DIA_SEMANA.search(pergunta)
    if achado:
        try:
            quando = _data(*achado.group(1, 2, 3))
        except ValueError:
            return None
        nome = _DIAS[quando.weekday()]
        return (f"**{nome}**\n\n_({quando.strftime('%d/%m/%Y')}, do calendário, sem modelo)_")
    achado = RE_FEVEREIRO.search(pergunta)
    if achado and re.search(r"quantos?\s+dias", pergunta, re.IGNORECASE):
        ano = int(achado.group(1))
        bissexto = (ano % 4 == 0 and ano % 100 != 0) or ano % 400 == 0
        return (f"**{29 if bissexto else 28} dias** (fevereiro de {ano}"
                f"{', ano bissexto' if bissexto else ''})\n\n_(calendário, sem modelo)_")
    return None


# ---------------------------------------------------------------- conversão
_CONVERSOES = {
    ("km", "milhas"): 0.621371, ("milhas", "km"): 1.609344,
    ("kg", "libras"): 2.204623, ("libras", "kg"): 0.4535924,
    ("metros", "pés"): 3.280840, ("pés", "metros"): 0.3048,
    ("litros", "galões"): 0.264172, ("galões", "litros"): 3.785412,
    ("horas", "minutos"): 60.0, ("minutos", "segundos"): 60.0,
    ("dias", "horas"): 24.0, ("semanas", "dias"): 7.0,
}
RE_CONVERSAO = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(km|quil[oô]metros?|milhas?|kg|quilos?|libras?|metros?|p[ée]s|"
    r"litros?|gal[õo]es|horas?|minutos?|segundos?|dias?|semanas?)\s+"
    r"(?:em|para|pra)\s+(km|quil[oô]metros?|milhas?|kg|quilos?|libras?|metros?|p[ée]s|"
    r"litros?|gal[õo]es|horas?|minutos?|segundos?|dias?|semanas?)", re.IGNORECASE)


def _normaliza_unidade(texto):
    t = texto.lower().rstrip("s")
    mapa = {"quilômetro": "km", "quilometro": "km", "km": "km", "milha": "milhas",
            "quilo": "kg", "kg": "kg", "libra": "libras", "metro": "metros",
            "pé": "pés", "pe": "pés", "litro": "litros", "galão": "galões",
            "galao": "galões", "hora": "horas", "minuto": "minutos",
            "segundo": "segundos", "dia": "dias", "semana": "semanas"}
    return mapa.get(t, t)


def responder_conversao(pergunta):
    if not pergunta:
        return None
    achado = RE_CONVERSAO.search(pergunta)
    if not achado:
        return None
    valor = float(achado.group(1).replace(",", "."))
    origem = _normaliza_unidade(achado.group(2))
    destino = _normaliza_unidade(achado.group(3))
    fator = _CONVERSOES.get((origem, destino))
    if fator is None:
        return None
    resultado = valor * fator
    return (f"**{formatar_numero(resultado)} {destino}** "
            f"({formatar_numero(valor)} {origem})\n\n_(conversão feita aqui, sem modelo)_")


# ---------------------------------------------------------------- temperatura
RE_TEMP = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:graus?\s*)?(°?\s*[cC])\s*(?:em|para|pra)\s*(°?\s*[fF])")


def responder_temperatura(pergunta):
    if not pergunta:
        return None
    achado = RE_TEMP.search(pergunta)
    if not achado:
        return None
    celsius = float(achado.group(1).replace(",", "."))
    fahrenheit = celsius * 9 / 5 + 32
    return (f"**{formatar_numero(fahrenheit)} °F** ({formatar_numero(celsius)} °C)\n\n"
            "_(conversão feita aqui, sem modelo)_")


# ---------------------------------------------------------------- porta única
def responder(pergunta):
    """Tenta todas as rotas exatas. Devolve texto pronto ou None."""
    for rota in (responder_conta, responder_variacao, responder_data,
                 responder_conversao, responder_temperatura):
        try:
            resposta = rota(pergunta)
        except Exception:
            resposta = None
        if resposta:
            return resposta
    return None


def precisa_exatidao(pergunta):
    """A pergunta é do tipo em que modelo pequeno erra e errar custa caro?"""
    if not pergunta:
        return False
    if any(rota(pergunta) for rota in (responder_conta, responder_variacao,
                                       responder_data, responder_conversao,
                                       responder_temperatura)):
        return False  # já resolvida aqui, nem chega no motor
    return bool(re.search(r"\d", pergunta)) and bool(
        re.search(r"quant[oa]s?|quanto|cálculo|calcula|média|soma|total|por cento|%",
                  pergunta, re.IGNORECASE))


def conferir(pergunta, resposta):
    """A resposta do motor bate com a conta que a casa sabe fazer?

    Devolve (ok, correta). Quando a pergunta pede uma conta e o texto traz um número
    diferente do exato, `ok` é False e `correta` é a resposta certa. É o antídoto para
    o modelo forte cair e o fraco inventar: o número não passa sem conferência.
    """
    exata = responder(pergunta)
    if not exata:
        return True, resposta  # não é conta: nada a conferir
    numero_certo = None
    primeiro = re.search(r"\*\*([\d.,]+)", exata)
    if primeiro:
        numero_certo = primeiro.group(1)
    if not numero_certo:
        return True, resposta
    limpo = resposta.replace(".", "").replace(",", "")
    if numero_certo.replace(".", "").replace(",", "") in limpo:
        return True, resposta
    return False, exata
