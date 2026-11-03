#!/usr/bin/env python3
"""Contratos offline da fiação opcional da outbox no respondedor."""
import os

import comum as C
import outbox as O
import outbox_comentarios as A
import responder as R

resultados = []


def checar(nome, condicao):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome)


def espera(erro, chamada):
    try:
        chamada()
    except erro:
        return True
    return False


def modo(valor):
    if valor is None:
        os.environ.pop("REBOCL_OUTBOX_COMENTARIOS", None)
    else:
        os.environ["REBOCL_OUTBOX_COMENTARIOS"] = valor


C.REPO = "sintetico/conversas"
C.DONO_GITHUB = "dono-sintetico"
C.ASSINATURA = "🤖 **Assistente Rebocl**"
C.MARCA_DO_ROBO = "<!--robo:"
R._parar_batida = lambda: None
C.comentarios_da_conversa_verificados = lambda numero: []

# Sem opt-in, o caminho legado permanece exatamente ativo.
modo(None)
legado = []
C.comentar = lambda numero, corpo: legado.append((numero, corpo)) or {"id": 1}
A.executar = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("outbox sem opt-in"))
R.responder(1, "resposta", "a1")
checar("padrão preserva publicador legado", len(legado) == 1 and "<!--resp:a1-->" in legado[0][1])

# Valores vagos não ativam a nova rota.
modo("true")
R.responder(1, "resposta", "a2")
checar("apenas o valor explícito 1 ativa outbox", len(legado) == 2)

# Opt-in: captura a fiação sem chamar qualquer destino.
modo("1")
captura = {}
def fake_executar(*args, **kwargs):
    captura["args"] = args
    captura.update(kwargs)
    return {"estado": "confirmado", "enviado_agora": True}
A.executar = fake_executar
chamadas = []
def gh(metodo, caminho, corpo=None):
    chamadas.append((metodo, caminho, corpo))
    if metodo == "POST":
        return {"id": 123}
    return []
C.gh = gh
C.comentar = lambda *args: (_ for _ in ()).throw(AssertionError("fallback legado proibido"))
R.responder(1, "resposta outbox", "a3")
checar("opt-in usa shadow=False e não chama publicador legado", captura["shadow"] is False and captura["args"][:3] == (1, C.ASSINATURA + "\n\nresposta outbox\n\n<!--resp:a3-->", "a3"))
retorno = captura["publicar"](1, "payload-byte-a-byte")
checar("POST da fiação preserva payload exato", retorno["id"] == 123 and chamadas[-1][2] == {"body": "payload-byte-a-byte"})
captura["paginar"](1, 2)
checar("paginação da fiação consulta página pedida", chamadas[-1][0] == "GET" and "page=2" in chamadas[-1][1])

# Pendente existente usa edição e mantém o mesmo id.
C.comentarios_da_conversa_verificados = lambda numero: [{"id": 77, "body": C.ASSINATURA + "\n\n<!--pendente:a4-->", "user": {"login": C.DONO_GITHUB}}]
editado = []
C.editar_comentario = lambda ident, corpo: editado.append((ident, corpo)) or True
R.responder(1, "ainda pendente", "a4", pendente=True)
checar("pendente usa operação de edição no id existente", captura["editar"] == 77 and captura["pendente"] is True)
captura["editar_comentario"](77, "novo payload")
checar("editor da fiação confirma o mesmo comentário", editado == [(77, "novo payload")])

# Incerteza não pode cair no POST legado.
A.executar = lambda *args, **kwargs: (_ for _ in ()).throw(O.EfeitoIncerto("incerto"))
checar("incerteza não faz fallback para publicação legada", espera(O.EfeitoIncerto, lambda: R.responder(1, "não repetir", "a5")))

modo(None)
falhas = [nome for nome, ok in resultados if not ok]
print(f"\n{len(resultados)-len(falhas)}/{len(resultados)} contratos PASS")
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
