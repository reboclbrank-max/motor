"""Outbox durável por efeito, sem retry cego.

Cada intenção tem arquivo próprio no repositório privado, identidade determinística,
payload imutável e escrita otimista pelo SHA. O efeito só é tentado após reconciliação.
Se o resultado for incerto, uma nova execução consulta o destino antes de qualquer envio.

Não há garantia exactly-once: APIs sem idempotência podem deixar casos incertos que
exigem reconciliação ou revisão. Este módulo ainda não chama nenhum destino real.
"""
import base64
import copy
import hashlib
import json
import re

import comum as C

PASTA = "MEMORIA/outbox"
ESTADOS = {"preparado", "em_envio", "enviado", "incerto", "confirmado"}


class ConflitoOutbox(RuntimeError):
    pass


class EfeitoIncerto(RuntimeError):
    pass


def _canon(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mapa(valor, nome):
    if not isinstance(valor, dict) or not valor:
        raise ValueError(nome + " precisa ser objeto não vazio")
    try:
        bruto = _canon(valor)
    except (TypeError, ValueError):
        raise ValueError(nome + " precisa ser serializável") from None
    if len(bruto) > 100000:
        raise ValueError(nome + " excede o limite da outbox")
    return copy.deepcopy(valor)


def identidade(tipo, destino, origem):
    if not isinstance(tipo, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,40}", tipo):
        raise ValueError("tipo de efeito inválido")
    base = {"versao": 1, "tipo": tipo,
            "destino": _mapa(destino, "destino"), "origem": _mapa(origem, "origem")}
    return hashlib.sha256(_canon(base).encode("utf-8")).hexdigest()[:32]


def caminho(ident):
    if not isinstance(ident, str) or not re.fullmatch(r"[a-f0-9]{32}", ident):
        raise ValueError("id de outbox inválido")
    return PASTA + "/" + ident + ".json"


def _http(erro, codigo):
    return re.search(r"HTTP " + str(codigo) + r"(?:\D|$)", str(erro)) is not None


def _validar(registro, ident):
    if not isinstance(registro, dict) or registro.get("versao") != 1 or registro.get("id") != ident:
        raise ValueError("registro de outbox incompatível")
    if registro.get("estado") not in ESTADOS or type(registro.get("tentativas")) is not int:
        raise ValueError("estado de outbox inválido")
    if registro["tentativas"] < 0:
        raise ValueError("contagem de tentativas inválida")
    tipo = registro.get("tipo")
    if identidade(tipo, registro.get("destino"), registro.get("origem")) != ident:
        raise ValueError("identidade da outbox não confere")
    if hashlib.sha256(_canon(registro.get("payload")).encode("utf-8")).hexdigest() != registro.get("payload_sha256"):
        raise ValueError("payload da outbox diverge do hash")


def carregar(ident, ausente=False):
    try:
        info = C.gh("GET", "/repos/" + C.REPO + "/contents/" + caminho(ident))
    except RuntimeError as erro:
        if ausente and _http(erro, 404):
            return None, None
        raise
    if not isinstance(info, dict) or not isinstance(info.get("content"), str) or not info.get("sha"):
        raise RuntimeError("outbox não observável")
    registro = json.loads(base64.b64decode(info["content"]).decode("utf-8"))
    _validar(registro, ident)
    return registro, info["sha"]


def _salvar(registro, sha=None):
    novo = copy.deepcopy(registro)
    novo["atualizado_em"] = C.agora().isoformat(timespec="seconds")
    bruto = json.dumps(novo, ensure_ascii=False, indent=2) + "\n"
    dados = {"message": "outbox: checkpoint transacional",
             "content": base64.b64encode(bruto.encode("utf-8")).decode("ascii")}
    if sha:
        dados["sha"] = sha
    info = C.gh("PUT", "/repos/" + C.REPO + "/contents/" + caminho(novo["id"]), dados)
    if not isinstance(info, dict) or not (info.get("content") or {}).get("sha"):
        raise RuntimeError("checkpoint da outbox não confirmado")
    return novo, info["content"]["sha"]


def _mesma_intencao(registro, tipo, destino, origem, payload):
    return all((_canon(registro.get("tipo")) == _canon(tipo),
                _canon(registro.get("destino")) == _canon(destino),
                _canon(registro.get("origem")) == _canon(origem),
                _canon(registro.get("payload")) == _canon(payload)))


def preparar(tipo, destino, origem, payload):
    """Cria uma intenção ou recupera exatamente a mesma, sem substituir payload."""
    destino = _mapa(destino, "destino")
    origem = _mapa(origem, "origem")
    payload = _mapa(payload, "payload")
    ident = identidade(tipo, destino, origem)
    existente, sha = carregar(ident, ausente=True)
    if existente is not None:
        if not _mesma_intencao(existente, tipo, destino, origem, payload):
            raise ConflitoOutbox("mesma chave com payload diferente; revisão necessária")
        return existente, sha, False
    digest = hashlib.sha256(_canon(payload).encode("utf-8")).hexdigest()
    agora = C.agora().isoformat(timespec="seconds")
    registro = {"versao": 1, "id": ident, "tipo": tipo, "destino": destino, "origem": origem,
                "payload": payload, "payload_sha256": digest, "estado": "preparado",
                "tentativas": 0, "resultado": None, "ultimo_erro": None,
                "criado_em": agora, "atualizado_em": agora,
                "historico": [{"estado": "preparado", "em": agora}]}
    try:
        novo, novo_sha = _salvar(registro)
        return novo, novo_sha, True
    except RuntimeError as erro:
        if not (_http(erro, 409) or _http(erro, 422)):
            raise
        # Outro escritor pode ter criado a mesma intenção; adotar só se for idêntica.
        existente, sha = carregar(ident)
        if not _mesma_intencao(existente, tipo, destino, origem, payload):
            raise ConflitoOutbox("corrida criou outra intenção com a mesma chave") from None
        return existente, sha, False


def _transicao(registro, sha, esperados, estado, **campos):
    if registro.get("estado") not in esperados:
        raise ConflitoOutbox("transição não permitida: " + str(registro.get("estado")) + " → " + estado)
    novo = copy.deepcopy(registro)
    novo.update(campos)
    novo["estado"] = estado
    novo.setdefault("historico", []).append(
        {"estado": estado, "em": C.agora().isoformat(timespec="seconds")})
    return _salvar(novo, sha)


def _observacao_unica(observada):
    if isinstance(observada, list):
        if len(observada) > 1:
            raise ConflitoOutbox("mais de um efeito remoto para a mesma chave")
        observada = observada[0] if observada else None
    if observada is None:
        return None
    if not isinstance(observada, dict) or not isinstance(observada.get("externo_id"), (str, int)):
        raise ValueError("evidência remota precisa de externo_id")
    return copy.deepcopy(observada)


def reconciliar(registro, sha, observar):
    """Adota evidência remota; nunca reenvia quando a confirmação está ausente."""
    observada = _observacao_unica(observar(copy.deepcopy(registro)))
    estado = registro["estado"]
    if observada is not None:
        anterior = (registro.get("resultado") or {}).get("externo_id")
        if estado == "confirmado" and anterior != observada["externo_id"]:
            raise ConflitoOutbox("evidência remota diverge do recibo confirmado")
        if estado == "confirmado":
            return registro, sha, "confirmado"
        novo, novo_sha = _transicao(registro, sha, ESTADOS, "confirmado",
                                    resultado=observada, ultimo_erro=None)
        return novo, novo_sha, "confirmado"
    if estado == "preparado":
        return registro, sha, "ausente"
    if estado in ("em_envio", "enviado"):
        novo, novo_sha = _transicao(registro, sha, {estado}, "incerto",
                                    ultimo_erro="envio_sem_evidencia_remota")
        return novo, novo_sha, "incerto"
    if estado == "incerto":
        return registro, sha, "incerto"
    raise EfeitoIncerto("efeito confirmado não foi encontrado; reenvio proibido")


def _recibo_envio(valor):
    if valor is None:
        return None
    if not isinstance(valor, dict) or not isinstance(valor.get("externo_id"), (str, int)):
        raise ValueError("retorno do envio precisa de externo_id")
    return {"externo_id": valor["externo_id"]}


def executar(tipo, destino, origem, payload, enviar, observar):
    """Executa no máximo uma tentativa por estado incerto.

    enviar(payload, destino) produz o efeito; observar(registro) apenas lê o destino.
    Ambos são injetados para manter os contratos offline e o destino desacoplado.
    """
    registro, sha, _ = preparar(tipo, destino, origem, payload)
    registro, sha, situacao = reconciliar(registro, sha, observar)
    if situacao == "confirmado":
        return {"id": registro["id"], "estado": "confirmado",
                "enviado_agora": False, "resultado": registro.get("resultado")}
    if situacao != "ausente":
        raise EfeitoIncerto("efeito continua incerto; nenhuma repetição cega")
    registro, sha = _transicao(registro, sha, {"preparado"}, "em_envio",
                               tentativas=registro["tentativas"] + 1, ultimo_erro=None)
    try:
        recibo = _recibo_envio(enviar(copy.deepcopy(registro["payload"]),
                                      copy.deepcopy(registro["destino"])))
    except Exception as erro:
        try:
            _transicao(registro, sha, {"em_envio"}, "incerto", ultimo_erro=type(erro).__name__)
        except Exception as checkpoint:
            raise EfeitoIncerto("falha no envio e no checkpoint; reconciliar antes de repetir") from checkpoint
        raise EfeitoIncerto("envio sem confirmação; reconciliar antes de repetir") from erro
    try:
        registro, sha = _transicao(registro, sha, {"em_envio"}, "enviado",
                                   resposta_envio=recibo, ultimo_erro=None)
        registro, sha, situacao = reconciliar(registro, sha, observar)
    except Exception as erro:
        raise EfeitoIncerto("envio já tentado; reconciliar antes de qualquer repetição") from erro
    if situacao != "confirmado":
        raise EfeitoIncerto("destino ainda não confirmou o envio; reenvio proibido")
    return {"id": registro["id"], "estado": "confirmado",
            "enviado_agora": True, "resultado": registro.get("resultado")}
