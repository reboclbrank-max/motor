#!/usr/bin/env python3
"""Contratos offline do adaptador shadow de comentários."""
import base64
import json

import comum as C
import outbox as O
import outbox_comentarios as A

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


class Repo:
    def __init__(self):
        self.dados = {}
        self.serial = 0

    def gh(self, metodo, caminho, corpo=None):
        path = caminho.split("/contents/", 1)[1]
        if metodo == "GET":
            if path not in self.dados:
                raise RuntimeError("GitHub API GET → HTTP 404: ausente")
            item = self.dados[path]
            return {"sha": item["sha"], "content": base64.b64encode(item["bruto"].encode()).decode()}
        if metodo == "PUT":
            atual = self.dados.get(path)
            if atual and corpo.get("sha") != atual["sha"]:
                raise RuntimeError("GitHub API PUT → HTTP 409: conflito")
            bruto = base64.b64decode(corpo["content"]).decode()
            self.serial += 1
            sha = "sha" + str(self.serial)
            self.dados[path] = {"sha": sha, "bruto": bruto}
            return {"content": {"sha": sha}}
        raise AssertionError("método inesperado")


class Cenario:
    def __init__(self, marca="a1"):
        self.repo = Repo()
        C.gh = self.repo.gh
        C.REPO = "sintetico/conversas"
        C.DONO_GITHUB = "dono-sintetico"
        C.ASSINATURA = "🤖 **Assistente Rebocl**"
        C.MARCA_DO_ROBO = "<!--robo:"
        self.marca = marca
        self.comentarios = []
        self.envios = 0
        self.edicoes = 0
        self.paginas_lidas = 0

    @property
    def corpo(self):
        return C.ASSINATURA + "\n\nresposta sintética\n\n<!--resp:" + self.marca + "-->"

    def publicar(self, numero, corpo):
        self.envios += 1
        item = {"id": 1000 + self.envios, "body": corpo,
                "user": {"login": C.DONO_GITHUB}}
        self.comentarios.append(item)
        return {"id": item["id"]}

    def editar(self, ident, corpo):
        self.edicoes += 1
        for item in self.comentarios:
            if item["id"] == ident:
                item["body"] = corpo
                return {"id": ident}
        raise RuntimeError("comentário ausente")

    def paginar(self, numero, pagina):
        self.paginas_lidas += 1
        inicio = (pagina - 1) * 100
        return self.comentarios[inicio:inicio + 100]

    def executar(self, **kwargs):
        return A.executar(1, self.corpo, self.marca, shadow=False,
                          publicar=self.publicar, editar_comentario=self.editar,
                          paginar=self.paginar, **kwargs)


# Shadow é o padrão e não toca armazenamento, paginação ou publicador.
s = Cenario()
plano = A.executar(1, s.corpo, s.marca, publicar=lambda *_: (_ for _ in ()).throw(AssertionError("envio")),
                   paginar=lambda *_: (_ for _ in ()).throw(AssertionError("leitura")))
checar("shadow puro não consulta nem produz efeito", plano["estado"] == "shadow" and not s.repo.dados and s.envios == 0)
checar("plano shadow traz marcador determinístico", A.marcador(plano["id"]) in plano["payload"]["body"])

# Criação, reentrada e evidência com hash do conteúdo.
s = Cenario()
r1 = s.executar();r2 = s.executar()
checar("criação confirmada e reentrada sem duplicar", s.envios == 1 and r1["enviado_agora"] and not r2["enviado_agora"])
checar("evidência contém id e SHA-256", len(r1["resultado"]["sha256"]) == 64 and r1["resultado"]["externo_id"] == 1001)

# Resposta perdida depois da publicação: reconciliar adota sem novo POST.
s = Cenario("a2")
def perder_resposta(numero, corpo):
    s.envios += 1
    s.comentarios.append({"id": 2001, "body": corpo, "user": {"login": C.DONO_GITHUB}})
    raise RuntimeError("resposta perdida")
checar("queda pós-publicação é incerta", espera(O.EfeitoIncerto, lambda: A.executar(1, s.corpo, s.marca, shadow=False, publicar=perder_resposta, paginar=s.paginar)))
r = s.executar()
checar("reconciliação de comentário não duplica", r["estado"] == "confirmado" and s.envios == 1 and r["resultado"]["externo_id"] == 2001)

# A evidência continua encontrada mesmo depois de 205 comentários em três páginas.
antes = [{"id": 3000 + i, "body": "outros", "user": {"login": "alguem"}} for i in range(100)]
depois = [{"id": 4000 + i, "body": "outros", "user": {"login": "alguem"}} for i in range(104)]
s.comentarios = antes + s.comentarios + depois
s.paginas_lidas = 0
r = s.executar()
checar("reconciliação percorre todas as páginas", s.paginas_lidas == 3 and s.envios == 1 and r["estado"] == "confirmado")

# Marcador forjado por terceiro não confirma nem impede a entrega legítima.
s = Cenario("a3")
op = A.operacao(1, s.corpo, s.marca)
s.comentarios.append({"id": 50, "body": op["payload"]["body"], "user": {"login": "intruso"}})
r = s.executar()
checar("forja de terceiro não vira evidência", s.envios == 1 and r["resultado"]["externo_id"] == 1001)

# Mesmo autor com corpo divergente é conflito, não uma nova publicação.
s = Cenario("a4");op = A.operacao(1, s.corpo, s.marca)
s.comentarios.append({"id": 60, "body": op["payload"]["body"] + "\nalterado", "user": {"login": C.DONO_GITHUB}})
checar("conteúdo divergente do mesmo autor bloqueia", espera(O.ConflitoOutbox, s.executar) and s.envios == 0)

# Duplicidade remota já existente bloqueia outra tentativa.
s = Cenario("a5");op = A.operacao(1, s.corpo, s.marca)
for ident in (71, 72):
    s.comentarios.append({"id": ident, "body": op["payload"]["body"], "user": {"login": C.DONO_GITHUB}})
checar("duplicidade de comentários é incidente", espera(O.ConflitoOutbox, s.executar) and s.envios == 0)

# Edição usa o mesmo id e também é idempotente.
s = Cenario("a6")
s.comentarios.append({"id": 99, "body": C.ASSINATURA + "\n\npensando", "user": {"login": C.DONO_GITHUB}})
r1 = s.executar(editar=99);r2 = s.executar(editar=99)
checar("edição reentrante não republica nem reedita", s.edicoes == 1 and s.envios == 0 and r1["enviado_agora"] and not r2["enviado_agora"])

# Pendente e final têm identidades distintas; edição tem destino próprio.
s = Cenario("a7")
p = A.operacao(1, s.corpo, s.marca, pendente=True)
f = A.operacao(1, s.corpo, s.marca, pendente=False)
e = A.operacao(1, s.corpo, s.marca, editar=99)
checar("classe e operação separam identidades", len({p["id"], f["id"], e["id"]}) == 3)

# Página repetida é erro fechado e impede envio.
s = Cenario("a8")
pagina = [{"id": 1, "body": "x", "user": {"login": "alguem"}}] * 100
def repetida(numero, numero_pagina):
    return pagina
checar("paginação repetida não vira ausência", espera(RuntimeError, lambda: A.executar(1, s.corpo, s.marca, shadow=False, publicar=s.publicar, paginar=repetida)) and s.envios == 0)

# Pendente preserva a marca de robô que C.comentar acrescentava no fluxo legado.
s = Cenario("a9")
corpo_pendente = C.ASSINATURA + "\n\naguardando\n\n<!--pendente:a9-->"
op = A.operacao(1, corpo_pendente, s.marca, pendente=True)
checar("payload pendente preserva marca de robô uma única vez", op["payload"]["body"].count(C.MARCA_DO_ROBO) == 1 and A.marcador(op["id"]) in op["payload"]["body"])

# Entrada inválida não chega à outbox.
checar("origem e conversa inválidas são recusadas", espera(ValueError, lambda: A.operacao(0, s.corpo, "x")))

falhas = [nome for nome, ok in resultados if not ok]
print(f"\n{len(resultados)-len(falhas)}/{len(resultados)} contratos PASS")
if falhas:
    raise SystemExit("Falhas: " + "; ".join(falhas))
