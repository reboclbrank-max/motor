#!/usr/bin/env python3
"""Ensaio offline de 10.000 tarefas com falhas injetadas, sem destino real."""
import base64
import json
import time
from collections import Counter

import comum as C
import outbox as O
import outbox_comentarios as A

TOTAL = 10000
C.REPO = "sintetico/carga"
C.DONO_GITHUB = "dono-sintetico"
C.ASSINATURA = "🤖 **Assistente Rebocl**"
C.MARCA_DO_ROBO = "<!--robo:"


class Repo:
    def __init__(self):
        self.dados = {}
        self.serial = 0
        self.falhar_estado = None

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
            estado = json.loads(bruto).get("estado")
            if self.falhar_estado == estado:
                self.falhar_estado = None
                raise RuntimeError("GitHub API PUT → HTTP 500: resposta perdida")
            return {"content": {"sha": sha}}
        raise AssertionError("método inesperado")


def numero_global(conversa):
    return 100000 + conversa


repo = Repo()
C.gh = repo.gh
comentarios = {}
chamadas_por_tarefa = Counter()
confirmadas = incertas = 0
ids = set()
inicio = time.monotonic()


def executar(indice, publicar):
    numero = indice + 1
    marca = "a" + str(numero)
    corpo = C.ASSINATURA + "\n\nresposta sintética " + str(numero) + "\n\n<!--resp:" + marca + "-->"
    return A.executar(numero, corpo, marca, shadow=False, publicar=publicar,
                      paginar=lambda conversa, pagina: comentarios.get(conversa, []))


for i in range(TOTAL):
    classe = i % 5
    numero = i + 1
    try:
        if classe == 0:
            def publicar(conversa, corpo, i=i):
                chamadas_por_tarefa[i] += 1
                item = {"id": numero_global(conversa), "body": corpo, "user": {"login": C.DONO_GITHUB}}
                comentarios.setdefault(conversa, []).append(item)
                return {"id": item["id"]}
            resultado = executar(i, publicar)
            confirmadas += 1
        elif classe == 1:
            def perder(conversa, corpo, i=i):
                chamadas_por_tarefa[i] += 1
                item = {"id": numero_global(conversa), "body": corpo, "user": {"login": C.DONO_GITHUB}}
                comentarios.setdefault(conversa, []).append(item)
                raise RuntimeError("resposta perdida depois do efeito")
            try:
                executar(i, perder)
                raise AssertionError("incerteza não sinalizada")
            except O.EfeitoIncerto:
                pass
            resultado = executar(i, perder)
            confirmadas += 1
        elif classe == 2:
            def falhar(conversa, corpo, i=i):
                chamadas_por_tarefa[i] += 1
                raise RuntimeError("falha antes do efeito")
            for _ in range(2):
                try:
                    executar(i, falhar)
                    raise AssertionError("incerteza não sinalizada")
                except O.EfeitoIncerto:
                    pass
            resultado = {"estado": "incerto"}
            incertas += 1
        elif classe == 3:
            repo.falhar_estado = "em_envio"
            def nao_chamar(conversa, corpo, i=i):
                chamadas_por_tarefa[i] += 1
                raise AssertionError("envio não deveria ocorrer")
            try:
                executar(i, nao_chamar)
                raise AssertionError("falha de checkpoint não sinalizada")
            except RuntimeError:
                pass
            try:
                executar(i, nao_chamar)
                raise AssertionError("incerteza não sinalizada")
            except O.EfeitoIncerto:
                pass
            resultado = {"estado": "incerto"}
            incertas += 1
        else:
            repo.falhar_estado = "enviado"
            def publicar(conversa, corpo, i=i):
                chamadas_por_tarefa[i] += 1
                item = {"id": numero_global(conversa), "body": corpo, "user": {"login": C.DONO_GITHUB}}
                comentarios.setdefault(conversa, []).append(item)
                return {"id": item["id"]}
            try:
                executar(i, publicar)
                raise AssertionError("falha de checkpoint não sinalizada")
            except O.EfeitoIncerto:
                pass
            resultado = executar(i, publicar)
            confirmadas += 1
    except Exception as erro:
        raise AssertionError(f"tarefa {i} classe {classe}: {type(erro).__name__}: {erro}") from erro
    if resultado["estado"] == "confirmado":
        ident = O.identidade(A.CRIAR, {"repo": C.REPO, "conversa": numero}, {"marca": "a" + str(numero), "classe": "final"})
        ids.add(ident)
        if len(comentarios.get(numero, [])) != 1:
            raise AssertionError("duplicidade/ausência externa na tarefa " + str(i))
    elif numero in comentarios:
        raise AssertionError("efeito externo indevido na tarefa " + str(i))
    if (i + 1) % 2000 == 0:
        print(f"PROGRESSO {i+1}/{TOTAL} em {time.monotonic()-inicio:.1f}s", flush=True)

marcadores = [A.marcador(O.identidade(A.CRIAR, {"repo": C.REPO, "conversa": n}, {"marca": "a" + str(n), "classe": "final"}))
              for n in comentarios]
checar_confirmadas = confirmadas == 6000
checar_incerts = incertas == 4000
checar_comentarios = len(comentarios) == 6000 and sum(len(v) for v in comentarios.values()) == 6000
checar_ids = len(ids) == 6000 and len(set(marcadores)) == 6000
checar_sem_repeticao = all(chamadas_por_tarefa[i] <= 1 for i in range(TOTAL))
estados = Counter(json.loads(v["bruto"])["estado"] for v in repo.dados.values())
checar_estados = estados["confirmado"] == 6000 and estados["incerto"] == 4000 and len(repo.dados) == TOTAL
metricas = {"tarefas": TOTAL, "confirmadas": confirmadas, "incertas_preservadas": incertas,
            "comentarios_sinteticos": sum(len(v) for v in comentarios.values()),
            "duplicidades_externas": 0 if checar_comentarios and checar_ids else 1,
            "estados_da_outbox": dict(estados), "segundos": round(time.monotonic() - inicio, 3)}
print("MÉTRICAS " + json.dumps(metricas, ensure_ascii=False, sort_keys=True))
resultados = [("6.000 confirmações reconciliadas", checar_confirmadas),
              ("4.000 incertezas preservadas sem efeito indevido", checar_incerts),
              ("nenhuma duplicidade externa", checar_comentarios and checar_ids),
              ("nenhuma tarefa reenviou após incerteza", checar_sem_repeticao),
              ("10.000 registros finais íntegros", checar_estados)]
for nome, ok in resultados:
    print(("PASS" if ok else "FAIL") + " — " + nome)
if not all(ok for _, ok in resultados):
    raise SystemExit("ensaio de carga reprovado")
