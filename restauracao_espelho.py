"""Ensaio offline de restauração: nunca sobrescreve uma pasta existente.

Lê um snapshot local de diretório do espelho, copia para destino novo e
confere hashes antes de devolver recibo. Não usa rede, PAT ou dados reais.
"""
import hashlib
import os
from pathlib import Path
import stat

from espelho import _fotografia


def _copiar_verificado(origem, destino, digest_esperado):
    leitura = os.open(origem, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    escrita = None
    try:
        antes = os.fstat(leitura)
        if not stat.S_ISREG(antes.st_mode) or antes.st_nlink != 1:
            raise RuntimeError("ensaio: fonte insegura")
        escrita = os.open(destino,
                          os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                          0o600)
        hash_lido = hashlib.sha256()
        while True:
            dados = os.read(leitura, 1024 * 1024)
            if not dados:
                break
            hash_lido.update(dados)
            posicao = 0
            while posicao < len(dados):
                escritos = os.write(escrita, dados[posicao:])
                if escritos <= 0:
                    raise OSError("ensaio: escrita incompleta")
                posicao += escritos
        os.fsync(escrita)
        depois = os.fstat(leitura)
        atual = os.lstat(origem)
        versao = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if hash_lido.hexdigest() != digest_esperado or versao(antes) != versao(depois) or versao(depois) != versao(atual):
            raise RuntimeError("ensaio: fonte mudou")
    finally:
        if escrita is not None:
            os.close(escrita)
        os.close(leitura)


def ensaiar_restauracao(origem, destino):
    """Somente destino INEXISTENTE; nunca limpa, reconcilia ou publica."""
    origem = Path(origem).absolute()
    destino = Path(destino).absolute()
    parent = destino.parent
    if not parent.is_dir() or parent.is_symlink():
        raise RuntimeError("ensaio: pasta pai insegura")
    realOrigem = os.path.realpath(origem)
    realDest = os.path.realpath(destino)
    if os.path.commonpath([realOrigem,realDest]) in (realOrigem,realDest):
        raise RuntimeError("ensaio: origem e destino sobrepostos")
    if os.path.lexists(destino):
        raise RuntimeError("ensaio: destino já existe")
    blobs, pastas = _fotografia(str(origem))
    if not blobs:
        raise RuntimeError("ensaio: origem vazia")
    os.mkdir(destino, mode=0o700)
    # Os testes verificam que falha mantém bytes parciais para revisão, sem
    # limpeza cega. Recusa diretórios extras mesmo vazios após reconstrução.
    for rel in sorted(pastas, key=lambda x:(x.count("/"),x)):
        os.mkdir(destino / rel, mode=0o700)
    for rel,digest in sorted(blobs.items()):
        alvo = destino / rel
        alvo.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        _copiar_verificado(origem / rel, alvo, digest)
    conferido, pastasConf = _fotografia(str(destino))
    origemAgora,pastasAgora = _fotografia(str(origem))
    if conferido != blobs or origemAgora != blobs or pastasAgora != pastas or pastasConf != pastas:
        raise RuntimeError("ensaio: verificacao de restauracao falhou")
    return {"arquivos_verificados":len(blobs),"pastas_verificadas":len(pastas)}
