#!/usr/bin/env python3
"""Memória privada: versão-base, conflito explícito e falhas não silenciosas.

O manifesto local não contém conteúdo nem credenciais e não vai para o Git.
Não mescla versões divergentes, não apaga memória remota e não garante transação
entre arquivos. Escritas feitas diretamente pela API continuam canônicas.
"""
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
import urllib.error

API = "https://api.github.com"
REPO_MEMORIA = (os.environ.get("REPO_MEMORIA") or "reboclbrank-max/agente").strip() or "reboclbrank-max/agente"
TOKEN = os.environ.get("PAT_MEMORIA", "").strip()
PASTA = os.environ.get("PASTA_MEMORIA", "MEMORIA").strip() or "MEMORIA"
RAMO = os.environ.get("RAMO_MEMORIA", "main").strip() or "main"
MANIFESTO = ".memoria-sync.json"


def log(*partes):
    print("[memoria]", *partes, flush=True)


def _motivo_seguro(erro):
    """Somente o tipo/código HTTP; nunca imprimir URL, corpo, header ou token."""
    if isinstance(erro, urllib.error.HTTPError):
        return "http_" + str(erro.code)
    if isinstance(erro, urllib.error.URLError):
        return "rede_indisponivel"
    if isinstance(erro, TimeoutError):
        return "tempo_limite"
    return type(erro).__name__


def _http(metodo, caminho, corpo=None):
    if not TOKEN:
        raise RuntimeError("PAT_MEMORIA ausente")
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(API + caminho, data=dados, method=metodo)
    req.add_header("Authorization", "Bearer " + TOKEN)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "motor-rebocl")
    if dados is not None:
        req.add_header("Content-Type", "application/json")
    # Só leituras idempotentes podem ser repetidas. Nunca repetir PUT após
    # falha de transporte: a escrita pode ter sido aceita remotamente.
    tentativas = 3 if metodo == "GET" else 1
    for indice in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=60) as resposta:
                texto = resposta.read().decode("utf-8")
            return json.loads(texto) if texto else None
        except urllib.error.HTTPError as erro:
            if indice + 1 == tentativas or erro.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            if indice + 1 == tentativas:
                raise
        time.sleep(min(2, 0.5 * (2 ** indice)))


def _sha(conteudo):
    return hashlib.sha1(b"blob %d\0" % len(conteudo) + conteudo).hexdigest()


def _escopo():
    return {"repo": REPO_MEMORIA, "ramo": RAMO, "pasta": os.path.abspath(PASTA)}


def _atomico(caminho, conteudo):
    pasta = os.path.dirname(caminho) or "."
    os.makedirs(pasta, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".sync-", dir=pasta)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, caminho)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _salvar_base(arquivos):
    _atomico(MANIFESTO, json.dumps({"versao": 1, "escopo": _escopo(), "arquivos": arquivos}).encode())


def _ler_base():
    with open(MANIFESTO, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("versao") != 1 or d.get("escopo") != _escopo() or not isinstance(d.get("arquivos"), dict):
        raise ValueError("manifesto de outro escopo ou inválido")
    return d["arquivos"]


def _caminho_seguro(caminho):
    alvo, raiz = os.path.realpath(caminho), os.path.realpath(PASTA)
    return alvo != raiz and os.path.commonpath([alvo, raiz]) == raiz


def listar_remoto():
    try:
        arvore = _http("GET", f"/repos/{REPO_MEMORIA}/git/trees/{RAMO}?recursive=1")
        if not isinstance(arvore, dict) or not isinstance(arvore.get("tree"), list) or arvore.get("truncated"):
            raise ValueError("árvore incompleta")
        return {t["path"]: t["sha"] for t in arvore["tree"]
                if t.get("type") == "blob" and t["path"].startswith(PASTA + "/")}
    except Exception as e:
        log("não consegui listar:", _motivo_seguro(e))
        return None


def baixar():
    # Invalida a base anterior antes de uma nova tentativa, inclusive se a rede cair.
    try:
        if os.path.lexists(MANIFESTO):
            os.unlink(MANIFESTO)
    except OSError:
        log("não consegui invalidar manifesto")
        return 1
    remoto = listar_remoto()
    if remoto is None:
        return 1
    base, erros = {}, 0
    for caminho, sha in sorted(remoto.items()):
        try:
            if not _caminho_seguro(caminho):
                raise ValueError("caminho fora da memória")
            dados = _http("GET", f"/repos/{REPO_MEMORIA}/git/blobs/{sha}")
            conteudo = base64.b64decode(dados["content"])
            if _sha(conteudo) != sha:
                raise ValueError("blob divergente")
            _atomico(caminho, conteudo)
            base[caminho] = sha
        except Exception as e:
            erros += 1
            log("falha ao baixar arquivo:", _motivo_seguro(e))
    # Sem base completa, um passo always() não deve enviar arquivos órfãos/antigos.
    if not erros:
        try:
            _salvar_base(base)
        except Exception as e:
            erros += 1
            log("falha no manifesto:", _motivo_seguro(e))
    log(f"baixados {len(base)}; falhas {erros} (conteúdo não impresso)")
    return int(bool(erros))


def _ler_local(caminho):
    with open(caminho, "rb") as f:
        return f.read()


class FalhaSync(ValueError):
    def __init__(self,codigo):self.codigo=codigo;super().__init__(codigo)

def _id_caminho(caminho):return hashlib.sha256(caminho.encode()).hexdigest()[:16]

def preservar_conflito(caminho,conteudo,anterior,remoto):
    """Cópia privada imutável e verificável; nunca altera o arquivo em conflito."""
    local=_sha(conteudo)
    destino=f'{PASTA}/conflitos-sync/{_id_caminho(caminho)}-{local}.json'
    registro={'versao':1,'arquivo':caminho,'sha_base':anterior,'sha_remoto_observado':remoto,
              'sha_local':local,'conteudo_base64':base64.b64encode(conteudo).decode('ascii'),
              'estado':'revisao_necessaria','politica':'preservar_ambos_sem_reexecutar_acao'}
    try:existente=_http('GET',f'/repos/{REPO_MEMORIA}/contents/{destino}?ref={RAMO}')
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        existente=None
    if existente:
        salvo=json.loads(base64.b64decode(existente['content']))
        if salvo.get('arquivo')!=caminho or salvo.get('sha_local')!=local or salvo.get('conteudo_base64')!=registro['conteudo_base64']:
            raise FalhaSync('copia_privada_divergente')
        return destino
    conteudo_registro=json.dumps(registro,ensure_ascii=False,sort_keys=True).encode()
    recibo=_http('PUT',f'/repos/{REPO_MEMORIA}/contents/{destino}',{'message':'memoria: preserva conflito sem sobrescrever origem',
                 'branch':RAMO,'content':base64.b64encode(conteudo_registro).decode('ascii')})
    if not isinstance(recibo,dict) or recibo.get('content',{}).get('sha')!=_sha(conteudo_registro):
        raise FalhaSync('copia_privada_sem_recibo')
    return destino

def _relatar_falha(caminho,erro):
    codigo=erro.codigo if isinstance(erro,FalhaSync) else ('http_'+str(erro.code) if isinstance(erro,urllib.error.HTTPError) else type(erro).__name__)
    log('arquivo não confirmado:', 'id='+_id_caminho(caminho), 'motivo='+codigo)


def subir():
    if not os.path.isdir(PASTA):
        log("nada para subir")
        return 0
    try:
        base = _ler_base()
    except Exception as e:
        log("base não confirmada; nenhum envio:", _motivo_seguro(e))
        return 1
    remoto = listar_remoto()
    if remoto is None:
        return 1
    enviados, iguais, erros = 0, 0, 0
    for raiz, pastas, arquivos in os.walk(PASTA, followlinks=False):
        pastas[:] = [d for d in pastas if not os.path.islink(os.path.join(raiz, d))]
        for nome in sorted(arquivos):
            caminho = os.path.join(raiz, nome).replace(os.sep, "/")
            conteudo=anterior=existente=None
            try:
                if not _caminho_seguro(caminho) or os.path.islink(caminho):
                    raise FalhaSync("caminho_inseguro")
                conteudo = _ler_local(caminho)
                local, existente, anterior = _sha(conteudo), remoto.get(caminho), base.get(caminho)
                if local == existente:
                    iguais += 1
                    base[caminho] = local
                    continue
                if anterior is not None and local == anterior:
                    # O runner não editou: preserve o remoto novo, inclusive remoção.
                    iguais += 1
                    continue
                if existente != anterior:
                    try:
                        preservar_conflito(caminho,conteudo,anterior,existente)
                        log('conflito preservado privadamente:', 'id='+_id_caminho(caminho), 'sha_local='+local)
                    except Exception as backup_erro:
                        _relatar_falha(caminho,backup_erro)
                        raise FalhaSync('conflito_sem_copia_confirmada') from None
                    raise FalhaSync('versoes_divergentes_origem_preservada_copia_confirmada')
                corpo = {"message": "memoria: sincroniza alteração do runner", "content": base64.b64encode(conteudo).decode("ascii"), "branch": RAMO}
                if existente:
                    corpo["sha"] = existente
                resposta = _http("PUT", f"/repos/{REPO_MEMORIA}/contents/{caminho}", corpo)
                if not isinstance(resposta, dict) or resposta.get("content", {}).get("sha") != local:
                    raise FalhaSync("recibo_de_escrita_divergente")
                base[caminho] = local
                enviados += 1
            except Exception as e:
                erros += 1
                if isinstance(e,urllib.error.HTTPError) and e.code==409 and conteudo is not None:
                    try:
                        preservar_conflito(caminho,conteudo,anterior,existente)
                        e=FalhaSync('corrida_http409_copia_privada_confirmada')
                    except Exception as backup_erro:
                        _relatar_falha(caminho,backup_erro)
                        e=FalhaSync('corrida_http409_sem_copia_confirmada')
                _relatar_falha(caminho,e)
    try:
        _salvar_base(base)
    except Exception as e:
        erros += 1
        log("falha no manifesto:", _motivo_seguro(e))
    log(f"subidos {enviados}; sem edição necessária {iguais}; falhas/conflitos {erros}")
    return int(bool(erros))


def main(argv):
    acao = (argv[1] if len(argv) > 1 else "baixar").lower()
    if acao == "baixar":
        return baixar()
    if acao == "subir":
        return subir()
    log("ação desconhecida (use baixar|subir)")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
