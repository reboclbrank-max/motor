#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Contrato offline dos workflows críticos do Assistente.

Não executa Actions, não acessa rede e não lê segredos. Protege apenas o
formato estático que evita tags mutáveis, permissões implícitas/amplas,
contexto ``pull_request_target`` e passos YAML perdidos por chaves repetidas.
"""
from pathlib import Path
import re
import sys

RAIZ = Path(__file__).resolve().parent
CHECKOUT = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4"
SETUP_PYTHON = "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5"

# Orçamento deliberado do estado atual: toda ampliação de escopo precisa ser
# revisada junto do contrato, em vez de aparecer silenciosamente em um YAML.
PERMISSOES_ESPERADAS = {
    # Orçamento do repositório PÚBLICO (motor). Todos leem o código e escrevem na memória
    # do privado pela API, com o PAT em secret — nenhum precisa de escrita aqui.
    # Ampliar qualquer um destes exige revisar este contrato de propósito, não por descuido.
    "auditoria-uso.yml": {"contents": "read"},
    "banco.yml": {"contents": "read"},
    "batente.yml": {"contents": "read"},
    "boletim.yml": {"contents": "read"},
    "caca-motores.yml": {"contents": "read"},
    "chat.yml": {"contents": "read"},
    "checkup.yml": {"contents": "read"},
    "confirmar-contas.yml": {"contents": "read"},
    "espelho.yml": {"contents": "read"},
    "estudo.yml": {"contents": "read"},
    "inspire.yml": {"contents": "read"},
    "manutencao.yml": {"contents": "read"},
    "melhoria-continua.yml": {"contents": "read"},
    "motor-local.yml": {"contents": "read"},
    "motores.yml": {"contents": "read"},
    "oficina.yml": {"contents": "read"},
    "piloto.yml": {"contents": "read"},
    "relatorio-semanal.yml": {"contents": "read"},
    "rotina.yml": {"contents": "read"},
    "sentinela.yml": {"contents": "read"},
    "testes.yml": {"contents": "read"},
    "varredura-motores.yml": {"contents": "read"},
    "vitrine.yml": {"contents": "read"},
    "prova-de-fogo.yml": {"contents": "read"},
    "testa-ferramentas.yml": {"contents": "read"},
}

ok = True


def checar(nome, condicao):
    global ok
    print(("  ✓ " if condicao else "  ✗ FALHOU ") + nome)
    ok = ok and condicao


def ler(relativo):
    return (RAIZ / relativo).read_text(encoding="utf-8")


def chaves_repetidas_de_steps(fonte):
    """Encontra chaves repetidas no mesmo item de ``steps`` sem parser externo.

    O contrato cobre a estrutura usada pelos dois workflows críticos: uma lista
    de passos com propriedades no nível imediatamente interno. Blocos de shell,
    ``env`` e ``with`` ficam mais profundos e não são confundidos com chaves do
    passo.
    """
    repetidas = []
    passos_indentacao = None
    passo_indentacao = None
    chaves = set()

    def finalizar_passo():
        nonlocal chaves
        chaves = set()

    for numero, linha in enumerate(fonte.splitlines(), start=1):
        sem_quebra = linha.lstrip()
        indentacao = len(linha) - len(sem_quebra)
        visivel = sem_quebra.strip()

        if re.match(r"^\s*steps:\s*$", linha):
            finalizar_passo()
            passos_indentacao = indentacao
            passo_indentacao = None
            continue

        if passos_indentacao is None:
            continue
        if visivel and not visivel.startswith("#") and indentacao <= passos_indentacao:
            finalizar_passo()
            passos_indentacao = None
            passo_indentacao = None
            continue

        if indentacao == passos_indentacao + 2 and re.match(r"^-\s+", sem_quebra):
            finalizar_passo()
            passo_indentacao = indentacao
            candidato = sem_quebra[2:]
        elif passo_indentacao is not None and indentacao == passo_indentacao + 2:
            candidato = sem_quebra
        else:
            continue

        chave = re.match(r"([A-Za-z0-9_-]+):", candidato)
        if not chave:
            continue
        nome = chave.group(1)
        if nome in chaves:
            repetidas.append((nome, numero))
        else:
            chaves.add(nome)

    return repetidas


def permissoes_declaradas(fonte):
    """Lê o bloco simples de permissões raiz sem depender de parser externo.

    Retorna ``None`` se o bloco estiver ausente, malformado ou repetir uma
    chave. Os workflows vigentes usam somente ``escopo: read|write|none`` no
    primeiro nível, deliberadamente fácil de auditar.
    """
    inicio = None
    for indice, linha in enumerate(fonte.splitlines()):
        if linha == "permissions:":
            inicio = indice + 1
            break
    if inicio is None:
        return None

    permissao = {}
    for linha in fonte.splitlines()[inicio:]:
        if not linha.strip():
            continue
        achado = re.match(r"^  ([a-z-]+):\s*(read|write|none)\s*$", linha)
        if not achado:
            break
        escopo, nivel = achado.groups()
        if escopo in permissao:
            return None
        permissao[escopo] = nivel
    return permissao or None


def tem_permissoes_explicitas(fonte):
    """Exige o bloco ``permissions`` no nível raiz do workflow."""
    return permissoes_declaradas(fonte) is not None


def tem_gatilho_proibido(fonte):
    """Bloqueia o contexto de PR que disponibiliza token/base privilegiados."""
    return bool(re.search(r"^\s*pull_request_target\s*:", fonte, re.MULTILINE))


worker = ler(".github/workflows/chat.yml")
testes = ler(".github/workflows/testes.yml")

for nome, fonte in (("worker", worker), ("barreira", testes)):
    checar(nome + " fixa checkout em SHA", CHECKOUT in fonte)
    checar(nome + " fixa setup-python em SHA", SETUP_PYTHON in fonte)
    checar(nome + " não usa tag mutável das Actions", not re.search(
        r"actions/(?:checkout|setup-python)@v\d+", fonte
    ))

CACHE = "actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830"  # v4, pinado por SHA

REFERENCIAS_PERMITIDAS = {
    CHECKOUT.split(" #", 1)[0],
    SETUP_PYTHON.split(" #", 1)[0],
    CACHE,
}
caminhos_workflows = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
checar(
    "orçamento de permissões cobre exatamente os workflows atuais",
    {caminho.name for caminho in caminhos_workflows} == set(PERMISSOES_ESPERADAS),
)
for caminho in caminhos_workflows:
    fonte = caminho.read_text(encoding="utf-8")
    referencias = re.findall(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", fonte, re.MULTILINE)
    checar(
        "workflow " + caminho.name + " fixa Actions conhecidas",
        all(referencia in REFERENCIAS_PERMITIDAS for referencia in referencias),
    )
    declaradas = permissoes_declaradas(fonte)
    checar(
        "workflow " + caminho.name + " declara permissões explicitamente",
        tem_permissoes_explicitas(fonte),
    )
    checar(
        "workflow " + caminho.name + " preserva orçamento exato de permissões",
        declaradas == PERMISSOES_ESPERADAS.get(caminho.name),
    )
    checar(
        "workflow " + caminho.name + " não usa pull_request_target",
        not tem_gatilho_proibido(fonte),
    )
    checar(
        "workflow " + caminho.name + " não concede write-all",
        not re.search(r"^permissions:\s*write-all\s*$", fonte, re.MULTILINE),
    )
    checar(
        "workflow " + caminho.name + " não repete chaves no mesmo passo",
        not chaves_repetidas_de_steps(fonte),
    )

amostra_permissoes = "permissions:\n  contents: read\n"
amostra_permissoes_duplicadas = "permissions:\n  contents: read\n  contents: write\n"
checar(
    "detector exige bloco de permissões explícito",
    tem_permissoes_explicitas(amostra_permissoes)
    and not tem_permissoes_explicitas("name: sem-permissoes\n"),
)
checar(
    "detector lê orçamento exato e rejeita permissão repetida",
    permissoes_declaradas(amostra_permissoes) == {"contents": "read"}
    and permissoes_declaradas(amostra_permissoes_duplicadas) is None,
)
checar(
    "detector identifica pull_request_target sem executar workflow",
    tem_gatilho_proibido("on:\n  pull_request_target:\n"),
)
checar(
    "detector identifica permissions write-all sem executar workflow",
    bool(re.search(r"^permissions:\s*write-all\s*$", "permissions: write-all\n", re.MULTILINE)),
)

amostra_repetida = "steps:\n  - name: exemplo\n    run: primeiro\n    run: segundo\n"
checar(
    "detector identifica run repetido sem executar workflow",
    chaves_repetidas_de_steps(amostra_repetida) == [("run", 4)],
)

# O pacote crítico virou um laço (roda as 14 suítes e conta falhas). O contrato passa a
# exigir que cada suíte crítica apareça UMA vez no laço, e que o laço exista.
bloco_laco = re.search(r"for t in ([^;]+?); do", testes, re.MULTILINE)
checar("pacote crítico usa um único bloco YAML run", bloco_laco is not None)
if bloco_laco:
    lista = bloco_laco.group(1)
    for arquivo in ("teste-cerebro.py", "teste-caca.py", "teste-chat.py"):
        checar("pacote crítico executa " + arquivo, lista.count(arquivo) == 1)

checar(
    "contrato offline entra na barreira",
    "python3 teste-workflow-seguranca.py" in testes,
)

print("teste-workflow-seguranca:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
