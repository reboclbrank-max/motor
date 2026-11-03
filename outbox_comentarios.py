"""Adaptador de comentários para a outbox; shadow é o padrão e não tem efeitos.

Nenhuma função deste módulo escolhe credenciais ou destinos reais. Envio e paginação
são injetados pelo chamador. A integração com o respondedor pertence a outro corte.
"""
import copy
import hashlib
import re

import comum as C
import outbox as O

CRIAR = "comentario_criar"
EDITAR = "comentario_editar"


def marcador(ident):
    O.caminho(ident)
    return "<!--outbox:" + ident + "-->"


def operacao(numero, corpo, marca, pendente=False, editar=None):
    if type(numero) is not int or numero <= 0:
        raise ValueError("conversa inválida")
    if not isinstance(marca, str) or not re.fullmatch(r"[ac][0-9]+", marca):
        raise ValueError("marca de origem inválida")
    if type(pendente) is not bool or not isinstance(corpo, str) or not corpo.strip():
        raise ValueError("payload de comentário inválido")
    if not corpo.startswith(C.ASSINATURA):
        raise ValueError("comentário sem assinatura verificável da casa")
    if editar is not None and (type(editar) is not int or editar <= 0):
        raise ValueError("comentário de edição inválido")
    # Preserva a transformação legada de C.comentar, mas antes de fixar o payload.
    corpo_base = corpo.rstrip()
    if C.MARCA_DO_ROBO not in corpo_base and "<!--resp:" not in corpo_base:
        corpo_base += "\n\n" + C.MARCA_DO_ROBO + "casa-->"
    tipo = EDITAR if editar is not None else CRIAR
    destino = {"repo": C.REPO, "conversa": numero}
    if editar is not None:
        destino["comentario_id"] = editar
    origem = {"marca": marca, "classe": "pendente" if pendente else "final"}
    ident = O.identidade(tipo, destino, origem)
    marca_outbox = marcador(ident)
    if marca_outbox in corpo_base:
        raise ValueError("payload já contém marcador da outbox")
    corpo_final = corpo_base + "\n\n" + marca_outbox
    if len(corpo_final) > 65000:
        raise ValueError("comentário excede o limite seguro")
    return {"id": ident, "tipo": tipo, "destino": destino, "origem": origem,
            "payload": {"body": corpo_final, "marcador": marca_outbox}}


def _id_valido(valor):
    return isinstance(valor, (str, int)) and type(valor) is not bool and bool(str(valor))


def observar_comentarios(registro, comentarios):
    if not isinstance(comentarios, list):
        raise RuntimeError("comentários não observáveis")
    tipo = registro.get("tipo")
    if tipo not in (CRIAR, EDITAR):
        raise ValueError("tipo de registro não pertence ao adaptador")
    esperado = registro["payload"]["marcador"]
    if esperado != marcador(registro["id"]):
        raise ValueError("marcador diverge da identidade")
    corpo_esperado = registro["payload"]["body"]
    encontrados = []
    for comentario in comentarios:
        if not isinstance(comentario, dict):
            raise RuntimeError("comentário remoto inválido")
        corpo = comentario.get("body") or ""
        if esperado not in corpo:
            continue
        autor = (comentario.get("user") or {}).get("login")
        if autor not in (C.DONO_GITHUB, "github-actions[bot]"):
            continue  # marcador copiado por terceiro não é evidência
        if not _id_valido(comentario.get("id")):
            raise O.ConflitoOutbox("comentário da casa sem id observável")
        if tipo == EDITAR and comentario["id"] != registro["destino"].get("comentario_id"):
            raise O.ConflitoOutbox("marcador apareceu em comentário diferente do destino")
        if not corpo.startswith(C.ASSINATURA) or corpo != corpo_esperado:
            raise O.ConflitoOutbox("marcador da casa com conteúdo divergente; revisão necessária")
        encontrados.append({"externo_id": comentario["id"],
                            "sha256": hashlib.sha256(corpo.encode("utf-8")).hexdigest()})
    return encontrados


def observar_paginas(registro, paginar):
    """Lê todas as páginas; erro ou repetição não equivale a ausência."""
    numero = registro["destino"]["conversa"]
    todos, anterior = [], None
    for pagina in range(1, 1001):
        dados = paginar(numero, pagina)
        if not isinstance(dados, list):
            raise RuntimeError("página de comentários não observável")
        if dados and dados == anterior:
            raise RuntimeError("paginação sem progresso")
        todos.extend(dados)
        if len(dados) < 100:
            return observar_comentarios(registro, todos)
        anterior = copy.deepcopy(dados)
    raise RuntimeError("limite defensivo de páginas atingido")


def executar(numero, corpo, marca, pendente=False, editar=None, shadow=True,
             publicar=None, editar_comentario=None, paginar=None):
    """Shadow apenas monta o plano. Fora dele, todas as dependências são explícitas."""
    op = operacao(numero, corpo, marca, pendente=pendente, editar=editar)
    if shadow:
        return {"estado": "shadow", **op}
    if not callable(paginar):
        raise ValueError("paginação obrigatória para reconciliação")
    if op["tipo"] == CRIAR and not callable(publicar):
        raise ValueError("publicador obrigatório fora de shadow")
    if op["tipo"] == EDITAR and not callable(editar_comentario):
        raise ValueError("editor obrigatório fora de shadow")

    def enviar(payload, destino):
        if op["tipo"] == CRIAR:
            resposta = publicar(destino["conversa"], payload["body"])
            externo = resposta.get("id") if isinstance(resposta, dict) else None
            if not _id_valido(externo):
                raise RuntimeError("publicação sem id observável")
            return {"externo_id": externo}
        resposta = editar_comentario(destino["comentario_id"], payload["body"])
        if resposta is False or resposta is None:
            raise RuntimeError("edição não confirmada pelo adaptador")
        return {"externo_id": destino["comentario_id"]}

    return O.executar(op["tipo"], op["destino"], op["origem"], op["payload"],
                      enviar=enviar, observar=lambda registro: observar_paginas(registro, paginar))
