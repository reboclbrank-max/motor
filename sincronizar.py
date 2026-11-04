#!/usr/bin/env python3
"""Memória privada: versão-base, conflito explícito e falhas não silenciosas.

O manifesto local não contém conteúdo nem credenciais e não vai para o Git.
Não mescla versões divergentes, não apaga memória remota e não garante transação
entre arquivos. Escritas feitas diretamente pela API continuam canônicas.
"""
import base64
import fcntl
from contextlib import contextmanager
import hashlib
import json
import os
import stat
import sys
import tempfile
import time
import http.client
import urllib.request
import urllib.error

API = "https://api.github.com"
REPO_MEMORIA = (os.environ.get("REPO_MEMORIA") or "reboclbrank-max/agente").strip() or "reboclbrank-max/agente"
TOKEN = os.environ.get("PAT_MEMORIA", "").strip()
PASTA = os.environ.get("PASTA_MEMORIA", "MEMORIA").strip() or "MEMORIA"
RAMO = os.environ.get("RAMO_MEMORIA", "main").strip() or "main"
MANIFESTO = ".memoria-sync.json"
# Espera entre tentativas de leitura (teste zera para não dormir).
ESPERA_BASE = 0.5
ESPERA_MAX = 2.0
TRAVA_LOCAL = ".memoria-sync.lock"
# Cópias públicas distribuídas com o código, não memória produzida pelo runner.
# A exceção exige nome E conteúdo exatos; nova versão requer revisão desta lista.
SEMENTES_PUBLICAS = {
    "MEMORIA/exatidao-motores.json": "711735dd088028aa4b41e7b64a4e59996e906d05",
    "MEMORIA/prova-fogo.json": "9bf37eee0357813c9f3a7e678279ce65830a99d4",
}


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
            # 403 entra aqui porque o limite secundário do GitHub responde 403 (não 429) e, em
            # rajada de 250 downloads, é exatamente ele que aparece. Se for falta de permissão
            # de verdade, as três tentativas falham igual e o erro sobe como antes.
            if indice + 1 == tentativas or erro.code not in (403, 429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            # Queda no meio da resposta chega como RemoteDisconnected/IncompleteRead, que NÃO são
            # URLError: em 04/11 um único RemoteDisconnected em 254 arquivos derrubou o banco da
            # casa e o espelho da memória (runs 41819338210 e 41845953050). Repetir GET é seguro.
            if indice + 1 == tentativas:
                raise
        time.sleep(min(ESPERA_MAX, ESPERA_BASE * (2 ** indice)))


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


def _conferir_destino_download(remoto):
    """Reuso só com cópias idênticas; nunca decide descartar edição ou órfão."""
    sementes_ausentes = {}
    if not os.path.lexists(PASTA):
        return sementes_ausentes
    if os.path.islink(PASTA) or not os.path.isdir(PASTA):
        raise FalhaSync("destino_local_inseguro")
    def falhou(erro):
        raise erro
    for raiz, pastas, arquivos in os.walk(PASTA, followlinks=False, onerror=falhou):
        for nome in pastas + arquivos:
            caminho = os.path.join(raiz, nome).replace(os.sep, "/")
            modo = os.lstat(caminho).st_mode
            if stat.S_ISLNK(modo) or not (stat.S_ISDIR(modo) or stat.S_ISREG(modo)):
                raise FalhaSync("destino_local_inseguro")
            if stat.S_ISREG(modo):
                local = _sha(_ler_local(caminho))
                if PASTA == "MEMORIA" and SEMENTES_PUBLICAS.get(caminho) == local:
                    # Se não existe no privado, lembrar a versão local impede que
                    # subir confunda esta cópia pública com nova memória criada.
                    if caminho not in remoto:
                        sementes_ausentes[caminho] = local
                elif local != remoto.get(caminho):
                    raise FalhaSync("memoria_local_divergente_requer_revisao")
    return sementes_ausentes


def _baixar_sem_trava():
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
    try:
        # Pré-verificação integral antes de alterar qualquer arquivo da memória.
        # Cópia parcial idêntica pode retomar; divergência exige revisão/cópia limpa.
        sementes_ausentes = _conferir_destino_download(remoto)
    except Exception as e:
        codigo = e.codigo if isinstance(e, FalhaSync) else _motivo_seguro(e)
        log("download bloqueado; arquivos locais preservados:", codigo)
        return 1
    base, erros = dict(sementes_ausentes), 0
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
            # Antes saía só o tipo da exceção ("HTTPError"), sem caminho nem código: foi o que
            # deixou o laudo de 03/11 em aberto. Agora o arquivo e o status aparecem, sem conteúdo.
            codigo = getattr(e, "code", None)
            log("falha ao baixar arquivo:", _motivo_seguro(e),
                "->", caminho, ("HTTP %s" % codigo) if codigo else "(sem código)")
    # Sem base completa, um passo always() não deve enviar arquivos órfãos/antigos.
    if not erros:
        try:
            _salvar_base(base)
        except Exception as e:
            erros += 1
            log("falha no manifesto:", _motivo_seguro(e))
    log(f"baixados {len(base) - len(sementes_ausentes)}; falhas {erros} (conteúdo não impresso)")
    return int(bool(erros))


def _ler_local(caminho):
    """Lê apenas arquivo regular próprio, sem atravessar link no último nome."""
    # O_NONBLOCK evita espera infinita ao abrir FIFO antes da inspeção do tipo.
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(caminho, flags), "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise FalhaSync("arquivo_local_inseguro")
        atual = os.lstat(caminho)
        if (info.st_dev, info.st_ino) != (atual.st_dev, atual.st_ino):
            raise FalhaSync("arquivo_local_substituido")
        conteudo = f.read()
        depois = os.fstat(f.fileno())
        antes_versao = (info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        depois_versao = (depois.st_size, depois.st_mtime_ns, depois.st_ctime_ns)
        if antes_versao != depois_versao or len(conteudo) != info.st_size:
            raise FalhaSync("arquivo_local_alterado_durante_leitura")
        return conteudo


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


def _subir_sem_trava():
    if not os.path.lexists(PASTA):
        log("nada para subir")
        return 0
    try:
        # O caminho da pasta pode ter virado link após baixar. A validação por
        # realpath de cada arquivo não protege a raiz quando ela própria é link.
        if not stat.S_ISDIR(os.lstat(PASTA).st_mode):
            raise FalhaSync("raiz_local_insegura")
    except Exception as erro:
        log("envio bloqueado antes de ler a memória:",
            erro.codigo if isinstance(erro, FalhaSync) else _motivo_seguro(erro))
        return 1
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


@contextmanager
def _trava_local():
    """Exclusão mútua entre sincronizadores que compartilham este checkout.

    A trava é mantida por um descritor aberto durante a operação, inclusive
    depois de erro; uma falha do processo libera o flock automaticamente.
    Nunca remove nem substitui uma trava ocupada.
    """
    descritor = None
    try:
        descritor = os.open(
            TRAVA_LOCAL, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        info = os.fstat(descritor)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise FalhaSync("trava_local_insegura")
        fcntl.flock(descritor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        atual = os.lstat(TRAVA_LOCAL)
        if (atual.st_dev, atual.st_ino) != (info.st_dev, info.st_ino):
            raise FalhaSync("trava_local_substituida")
        yield
    finally:
        if descritor is not None:
            os.close(descritor)


def _executar_com_trava(operacao):
    try:
        with _trava_local():
            return operacao()
    except BlockingIOError:
        log("sincronização bloqueada:", "trava_local_em_uso")
    except FalhaSync as erro:
        log("sincronização bloqueada:", erro.codigo)
    except OSError as erro:
        log("sincronização bloqueada:", _motivo_seguro(erro))
    return 1


def baixar():
    return _executar_com_trava(_baixar_sem_trava)


def subir():
    return _executar_com_trava(_subir_sem_trava)


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

