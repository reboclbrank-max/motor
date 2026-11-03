#!/usr/bin/env python3
"""Contratos offline da outbox; armazenamento e destino são sintéticos."""
import base64
import copy
import json

import comum as C
import outbox as O

resultados = []


def checar(nome, condicao):
    resultados.append((nome, bool(condicao)))
    print(("PASS" if condicao else "FAIL") + " — " + nome)


def espera(erro, chamada, *args):
    try:
        chamada(*args)
    except erro:
        return True
    return False


class Repo:
    def __init__(self):
        self.dados = {}
        self.serial = 0
        self.falhar_depois_put = None

    def gh(self, metodo, caminho, corpo=None):
        path = caminho.split("/contents/", 1)[1]
        if metodo == "GET":
            if path not in self.dados:
                raise RuntimeError("GitHub API GET → HTTP 404: ausente")
            item = self.dados[path]
            return {"sha": item["sha"], "content": base64.b64encode(item["bruto"].encode()).decode()}
        if metodo == "PUT":
            atual = self.dados.get(path)
            esperado = corpo.get("sha")
            if atual and esperado != atual["sha"]:
                raise RuntimeError("GitHub API PUT → HTTP 409: conflito")
            if not atual and esperado:
                raise RuntimeError("GitHub API PUT → HTTP 422: ausente")
            bruto = base64.b64decode(corpo["content"]).decode()
            self.serial += 1
            sha = "sha" + str(self.serial)
            self.dados[path] = {"sha": sha, "bruto": bruto}
            if self.falhar_depois_put and self.falhar_depois_put(path, bruto):
                self.falhar_depois_put = None
                raise RuntimeError("GitHub API PUT → HTTP 500: resposta perdida")
            return {"content": {"sha": sha}}
        raise AssertionError("método inesperado")


class Cenario:
    def __init__(self, sufixo="1"):
        self.repo = Repo()
        C.gh = self.repo.gh
        self.remotos = []
        self.envios = 0
        self.args = ("comentario", {"repo": "sintetico", "conversa": 1},
                     {"marca": "a" + sufixo}, {"body": "resposta sintética " + sufixo})

    def enviar(self, payload, destino):
        self.envios += 1
        item = {"externo_id": "ext-" + str(self.envios), "body": payload["body"]}
        self.remotos.append(item)
        return {"externo_id": item["externo_id"]}

    def observar(self, registro):
        return [x for x in self.remotos if x["body"] == registro["payload"]["body"]]


# Mesma intenção é determinística; outra origem não compartilha a chave.
a = O.identidade("comentario", {"n": 1}, {"m": "a1"})
b = O.identidade("comentario", {"n": 1}, {"m": "a1"})
c = O.identidade("comentario", {"n": 1}, {"m": "a2"})
checar("identidade determinística e separada por origem", a == b and a != c and len(a) == 32)
checar("caminho rejeita traversal", espera(ValueError, O.caminho, "../segredo"))

# Fluxo feliz e reentrada: um único efeito.
s = Cenario()
r1 = O.executar(*s.args, enviar=s.enviar, observar=s.observar)
r2 = O.executar(*s.args, enviar=s.enviar, observar=s.observar)
checar("sucesso confirma e reentrada não duplica", s.envios == 1 and r1["enviado_agora"] and not r2["enviado_agora"])
reg, sha = O.carregar(a if False else O.identidade(*s.args[:3]))
checar("registro final confirmado com uma tentativa", reg["estado"] == "confirmado" and reg["tentativas"] == 1)

# Payload divergente para a mesma origem é recusado antes do destino.
args = list(s.args);args[3] = {"body": "conteúdo alterado"}
checar("payload imutável por chave", espera(O.ConflitoOutbox, lambda: O.executar(*args, enviar=s.enviar, observar=s.observar)) and s.envios == 1)

# Queda depois do efeito: reconciliação adota o remoto em vez de repetir.
s = Cenario("2")
def cair_depois(payload, destino):
    s.envios += 1
    s.remotos.append({"externo_id": "ext-pos", "body": payload["body"]})
    raise RuntimeError("conexão perdida")
checar("queda pós-efeito fica incerta", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=cair_depois, observar=s.observar)))
r = O.executar(*s.args, enviar=s.enviar, observar=s.observar)
checar("reconciliação adota efeito anterior sem duplicar", r["estado"] == "confirmado" and s.envios == 1)

# Falha antes do efeito não libera retry cego.
s = Cenario("3")
def falhar_antes(payload, destino):
    s.envios += 1
    raise RuntimeError("falha antes da rede")
checar("falha de envio vira incerteza", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=falhar_antes, observar=s.observar)))
checar("incerto sem evidência não reenvia", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)) and s.envios == 1)

# Resposta do checkpoint em_envio perdida: efeito ainda não ocorreu, mas fica bloqueado.
s = Cenario("4")
def depois_em_envio(path, bruto):
    return json.loads(bruto)["estado"] == "em_envio"
s.repo.falhar_depois_put = depois_em_envio
checar("checkpoint inicial incerto impede envio", espera(RuntimeError, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)) and s.envios == 0)
checar("reentrada sem evidência continua sem envio", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)) and s.envios == 0)

# Resposta do checkpoint enviado perdida: remoto é adotado na próxima rodada.
s = Cenario("5")
def depois_enviado(path, bruto):
    return json.loads(bruto)["estado"] == "enviado"
s.repo.falhar_depois_put = depois_enviado
checar("falha de checkpoint pós-envio é incerta", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)))
r = O.executar(*s.args, enviar=s.enviar, observar=s.observar)
checar("recuperação pós-checkpoint não duplica", r["estado"] == "confirmado" and s.envios == 1)

# Leitura remota indisponível antes da primeira tentativa impede qualquer efeito.
s = Cenario("6")
def leitura_falha(registro):
    raise RuntimeError("destino não observável")
checar("falha de reconciliação prévia impede envio", espera(RuntimeError, lambda: O.executar(*s.args, enviar=s.enviar, observar=leitura_falha)) and s.envios == 0)

# Evidência confirmada que desaparece não autoriza reenvio.
s = Cenario("7")
O.executar(*s.args, enviar=s.enviar, observar=s.observar)
s.remotos.clear()
checar("recibo confirmado ausente não reenvia", espera(O.EfeitoIncerto, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)) and s.envios == 1)

# Corrida na criação: PUT gravou, mas a resposta 409 chegou; adotar registro idêntico.
s = Cenario("8")
s.repo.falhar_depois_put = lambda path, bruto: True
# O fake devolve 500 acima; usar 409 específico para exercitar a adoção.
original = s.repo.gh
def perder_create(metodo, caminho, corpo=None):
    if metodo == "PUT" and not s.repo.dados:
        try:
            return original(metodo, caminho, corpo)
        finally:
            pass
    return original(metodo, caminho, corpo)
# Substituição simples: primeiro PUT grava e informa 409.
def create_409(metodo, caminho, corpo=None):
    if metodo == "PUT" and not s.repo.dados:
        path = caminho.split("/contents/", 1)[1]
        bruto = base64.b64decode(corpo["content"]).decode()
        s.repo.dados[path] = {"sha": "corrida", "bruto": bruto}
        raise RuntimeError("GitHub API PUT → HTTP 409: já existe")
    return original(metodo, caminho, corpo)
s.repo.falhar_depois_put = None
C.gh = create_409
reg, sha, criado = O.preparar(*s.args)
checar("corrida na criação adota a mesma intenção", not criado and reg["estado"] == "preparado")

# Escrita otimista não sobrescreve outro escritor.
s = Cenario("9")
reg, sha, _ = O.preparar(*s.args)
reg2, sha2 = O._transicao(reg, sha, {"preparado"}, "incerto", ultimo_erro="outro")
checar("SHA antigo falha sem apagar versão nova", espera(RuntimeError, lambda: O._transicao(reg, sha, {"preparado"}, "em_envio")))
atual, _ = O.carregar(reg["id"])
checar("versão concorrente preservada", atual["estado"] == "incerto" and atual["ultimo_erro"] == "outro")

# Duplicidade remota é incidente de reconciliação, nunca motivo para terceiro envio.
s = Cenario("10")
s.remotos = [{"externo_id": "a", "body": s.args[3]["body"]}, {"externo_id": "b", "body": s.args[3]["body"]}]
checar("duplicidade remota bloqueia nova tentativa", espera(O.ConflitoOutbox, lambda: O.executar(*s.args, enviar=s.enviar, observar=s.observar)) and s.envios == 0)

falhas = [nome for nome, ok in resultados if not ok]
print(f"\n{len(resultados)-len(falhas)}/{len(resultados)} contratos PASS")
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
