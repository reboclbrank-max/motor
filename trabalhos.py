"""Registro de trabalhos privado. Não é executor contínuo nem consciência.

Escrita otimista pelo SHA lido; conflito não sobrescreve outro escritor.
Evidência atesta arquivo existente, não qualidade nem veracidade do seu conteúdo.
"""
import base64
import json
import re
import uuid
import hashlib
from contextvars import ContextVar
from contextlib import contextmanager
import comum as C

PASTA = 'MEMORIA/trabalhos'


_ORIGEM = ContextVar('origem_do_trabalho', default=None)
_PEDIDO_SHA = ContextVar('sha_do_pedido', default=None)


@contextmanager
def contexto_mensagem(numero, marca, pedido=None):
    if type(numero) is not int or numero <= 0 or not isinstance(marca, str) or not re.fullmatch(r'[ac][0-9]+', marca):
        raise ValueError('origem de mensagem inválida')
    if pedido is not None and not isinstance(pedido, str):
        raise ValueError('pedido inválido')
    digest = hashlib.sha256(pedido.encode()).hexdigest() if pedido is not None else None
    token_sha = _PEDIDO_SHA.set(digest)
    token = _ORIGEM.set({'repositorio': C.REPO, 'conversa': numero, 'marca': marca})
    try:
        yield
    finally:
        _ORIGEM.reset(token)
        _PEDIDO_SHA.reset(token_sha)


def id_da_origem():
    origem = _ORIGEM.get()
    if origem is None:
        return None
    return hashlib.sha256(json.dumps(origem, sort_keys=True).encode()).hexdigest()[:32]


def recuperar_da_origem():
    ident = id_da_origem()
    if ident is None:
        return None
    try:
        registro, _ = carregar(ident)
    except RuntimeError as e:
        if re.search(r'HTTP 404(?:\D|$)', str(e)):
            return None
        raise
    if registro.get('origem') != _ORIGEM.get():
        raise ValueError('origem do registro não confere; não reutilizar')
    if _PEDIDO_SHA.get() is not None and registro.get('pedido_sha256') != _PEDIDO_SHA.get():
        raise ValueError('mensagem alterada: revisar plano antes de continuar')
    return registro


def instrucoes_da_origem():
    registro = recuperar_da_origem()
    if registro is None:
        return ''
    aviso = ''
    for etapa in registro['etapas']:
        if etapa['estado'] == 'pendente':
            candidato = inspecionar_etapa(registro, etapa['numero'])
            if candidato['disponivel']:
                aviso = (' Há um arquivo salvo sem checkpoint na etapa '+str(etapa['numero'])+
                         '. Antes de refazer, use TRABALHO/inspecionar_etapa para ler o conteúdo. '
                         'Se o resultado servir à etapa, registre usando arquivo e sha_esperado devolvidos. '
                         'Existência de arquivo não comprova qualidade ou conclusão.')
            break
    return ('Há trabalho persistido para ESTA mensagem. Não crie cópia nem refaça etapas com evidência. '
            'Use o ID abaixo, execute somente etapas pendentes e entregue quando terminar. '
            'Não invente execução ou conclusão. Estado observado: '+json.dumps(registro, ensure_ascii=False)+aviso)


def caminho(identificador):
    if not isinstance(identificador, str) or not re.fullmatch(r'[a-f0-9]{32}', identificador):
        raise ValueError('id de trabalho inválido; use o id devolvido ao criar')
    return f'{PASTA}/{identificador}.json'


def texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f'{campo} precisa de texto não vazio')
    return valor.strip()


def carregar(identificador):
    info = C.gh('GET', f'/repos/{C.REPO}/contents/{caminho(identificador)}')
    registro = json.loads(base64.b64decode(info['content']).decode('utf-8'))
    if registro.get('id') != identificador or registro.get('versao') != 1:
        raise ValueError('registro incompatível')
    return registro, info['sha']


def salvar(registro, sha=None):
    path = caminho(registro['id'])
    registro['atualizado_em'] = C.agora().isoformat(timespec='seconds')
    conteudo = json.dumps(registro, ensure_ascii=False, indent=2)+'\n'
    dados = {'message': 'trabalho: atualiza registro privado',
             'content': base64.b64encode(conteudo.encode()).decode()}
    if sha:
        dados['sha'] = sha
    resultado = C.gh('PUT', f'/repos/{C.REPO}/contents/{path}', dados)
    if not isinstance(resultado, dict) or not (resultado.get('content') or {}).get('sha'):
        raise RuntimeError('gravação de trabalho não confirmada')
    C._gravar_local_memoria(path, conteudo, estrito=True)
    return registro


def arquivo_da_etapa(identificador, numero):
    caminho(identificador)  # valida namespace
    if type(numero) is not int or numero <= 0:
        raise ValueError('etapa inválida')
    return f'MEMORIA/entregas/trabalho-{identificador}/etapa-{numero}.md'


def inspecionar_etapa(registro, numero):
    if type(numero) is not int or not 1 <= numero <= len(registro['etapas']):
        raise ValueError('etapa inválida')
    etapa = registro['etapas'][numero-1]
    ev = etapa.get('evidencia')
    path = ev['arquivo'] if ev else arquivo_da_etapa(registro['id'], numero)
    try:
        info = C.gh('GET', f'/repos/{C.REPO}/contents/{path}')
    except RuntimeError as e:
        if re.search(r'HTTP 404(?:\D|$)', str(e)) and not ev:
            return {'etapa': numero, 'arquivo': path, 'disponivel': False, 'checkpoint': False}
        raise
    if not isinstance(info, dict) or not info.get('sha') or not isinstance(info.get('content'), str):
        raise RuntimeError('artefato não observável')
    conteudo = base64.b64decode(info['content']).decode('utf-8')
    if not conteudo.strip():
        raise ValueError('artefato vazio; não recuperar como evidência')
    if ev and ev['sha_blob'] != info['sha']:
        raise ValueError('arquivo diverge da evidência registrada')
    return {'etapa': numero, 'arquivo': path, 'sha_esperado': info['sha'],
            'disponivel': True, 'checkpoint': bool(ev), 'conteudo': conteudo}


def gravar_entrega(identificador, etapa, conteudo):
    """Arquivo novo por etapa; reentrada aceita só o MESMO conteúdo já gravado."""
    path = arquivo_da_etapa(identificador, etapa)
    conteudo = texto(conteudo, 'conteudo')+'\n'
    try:
        info = C.gh('GET', f'/repos/{C.REPO}/contents/{path}')
    except RuntimeError as e:
        if 'HTTP 404' not in str(e):
            raise
        info = None
    if info is None:
        dados = {'message': 'trabalho: entrega privada por etapa',
                 'content': base64.b64encode(conteudo.encode()).decode()}
        resultado = C.gh('PUT', f'/repos/{C.REPO}/contents/{path}', dados)
        if not isinstance(resultado, dict) or not (resultado.get('content') or {}).get('sha'):
            raise RuntimeError('arquivo de entrega não confirmado')
        info = C.gh('GET', f'/repos/{C.REPO}/contents/{path}')
    if not isinstance(info, dict) or not info.get('content') or base64.b64decode(info['content']).decode() != conteudo:
        raise ValueError('conteúdo da entrega diverge; não sobrescrever evidência')
    C._gravar_local_memoria(path, conteudo, estrito=True)
    return path


def executar(argumento):
    dados = json.loads(argumento)
    if not isinstance(dados, dict):
        raise ValueError('TRABALHO precisa de objeto JSON')
    acao = dados.get('acao')
    if acao == 'criar':
        existente = recuperar_da_origem()
        if existente is not None:
            return json.dumps(existente, ensure_ascii=False)
        objetivo = texto(dados.get('objetivo'), 'objetivo')
        etapas = dados.get('etapas')
        if not isinstance(etapas, list) or not etapas:
            raise ValueError('planeje ao menos uma etapa antes de criar')
        registro = {'versao': 1, 'id': id_da_origem() or uuid.uuid4().hex, 'objetivo': objetivo,
                    'estado': 'planejado', 'criado_em': C.agora().isoformat(timespec='seconds'),
                    'etapas': [{'numero': i+1, 'descricao': texto(e, 'etapa'), 'estado': 'pendente'}
                               for i, e in enumerate(etapas)], 'bloqueio': None}
        if _ORIGEM.get() is not None:
            registro['origem'] = dict(_ORIGEM.get())
            registro['pedido_sha256'] = _PEDIDO_SHA.get()
        salvar(registro)
    else:
        registro, sha = carregar(dados.get('id'))
        if acao == 'status':
            return json.dumps(registro, ensure_ascii=False)
        if acao == 'inspecionar_etapa':
            return json.dumps(inspecionar_etapa(registro, dados.get('etapa')), ensure_ascii=False)
        if registro['estado'] == 'entregue_para_revisao':
            raise ValueError('trabalho já entregue para revisão; registro preservado')
        if acao == 'registrar_etapa':
            numero = dados.get('etapa')
            if type(numero) is not int or not 1 <= numero <= len(registro['etapas']):
                raise ValueError('etapa inválida')
            etapa = registro['etapas'][numero-1]
            if etapa['estado'] != 'pendente':
                raise ValueError('etapa já registrada; evidência anterior preservada')
            if 'conteudo' in dados:
                path = gravar_entrega(registro['id'], numero, dados['conteudo'])
            else:
                path = texto(dados.get('arquivo'), 'arquivo')
            if not path.startswith('MEMORIA/') or any(x in ('', '.', '..') for x in path.split('/')) or '?' in path or '#' in path or '\\' in path:
                raise ValueError('evidência deve ser caminho privado em MEMORIA/')
            info = C.gh('GET', f'/repos/{C.REPO}/contents/{path}')
            if not isinstance(info, dict) or not info.get('sha') or not info.get('content'):
                raise ValueError('evidência não observável')
            if not base64.b64decode(info['content']).strip():
                raise ValueError('arquivo de evidência vazio')
            esperado = dados.get('sha_esperado')
            if 'conteudo' not in dados and path == arquivo_da_etapa(registro['id'], numero) and not esperado:
                raise ValueError('inspecione o arquivo recuperado e informe sha_esperado')
            if esperado is not None and esperado != info['sha']:
                raise ValueError('artefato mudou após inspeção; não confirmar checkpoint')
            if path == arquivo_da_etapa(registro['id'], numero):
                C._gravar_local_memoria(path, base64.b64decode(info['content']).decode('utf-8'), estrito=True)
            etapa.update(estado='evidencia_registrada', evidencia={'arquivo': path, 'sha_blob': info['sha']})
            registro.update(estado='em_execucao', bloqueio=None)
        elif acao == 'bloquear':
            registro.update(estado='bloqueado', bloqueio=texto(dados.get('motivo'), 'motivo'))
        elif acao == 'retomar':
            registro.update(estado='em_execucao', bloqueio=None)
        elif acao == 'entregar':
            if any(e['estado'] != 'evidencia_registrada' for e in registro['etapas']):
                raise ValueError('existem etapas sem evidência; não entregar como terminado')
            # Reconfere o SHA: o arquivo atual não pode ter mudado desde a etapa.
            for e in registro['etapas']:
                ev = e['evidencia']
                info = C.gh('GET', f'/repos/{C.REPO}/contents/{ev["arquivo"]}')
                if info.get('sha') != ev['sha_blob']:
                    raise ValueError('evidência mudou; entrega não confirmada')
            registro.update(estado='entregue_para_revisao', bloqueio=None,
                            resultado=texto(dados.get('resultado'), 'resultado'))
        else:
            raise ValueError('ação desconhecida: criar/status/inspecionar_etapa/registrar_etapa/bloquear/retomar/entregar')
        salvar(registro, sha)
    return json.dumps(registro, ensure_ascii=False)


def recibo(identificador):
    registro, _sha = carregar(identificador)
    if registro.get('estado') != 'entregue_para_revisao':
        raise ValueError('trabalho ainda não entregue para revisão')
    linhas = [f"**Recibo do trabalho `{identificador}`**", 'Estado: entregue para revisão.']
    for etapa in registro['etapas']:
        ev = etapa['evidencia']
        info = C.gh('GET', f'/repos/{C.REPO}/contents/{ev["arquivo"]}')
        if info.get('sha') != ev['sha_blob']:
            raise ValueError('arquivo diverge da evidência registrada')
        linhas.append(f"- Etapa {etapa['numero']}: [{ev['arquivo']}](https://github.com/{C.REPO}/blob/main/{ev['arquivo']})")
    linhas.append('Arquivos conferidos no repositório; conteúdo entregue para revisão, não aprovação automática.')
    return '\n'.join(linhas)
