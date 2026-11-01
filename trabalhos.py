"""Registro de trabalhos privado. Não é executor contínuo nem consciência.

Escrita otimista pelo SHA lido; conflito não sobrescreve outro escritor.
Evidência atesta arquivo existente, não qualidade nem veracidade do seu conteúdo.
"""
import base64
import json
import re
import uuid
import comum as C

PASTA = 'MEMORIA/trabalhos'


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


def executar(argumento):
    dados = json.loads(argumento)
    if not isinstance(dados, dict):
        raise ValueError('TRABALHO precisa de objeto JSON')
    acao = dados.get('acao')
    if acao == 'criar':
        objetivo = texto(dados.get('objetivo'), 'objetivo')
        etapas = dados.get('etapas')
        if not isinstance(etapas, list) or not etapas:
            raise ValueError('planeje ao menos uma etapa antes de criar')
        registro = {'versao': 1, 'id': uuid.uuid4().hex, 'objetivo': objetivo,
                    'estado': 'planejado', 'criado_em': C.agora().isoformat(timespec='seconds'),
                    'etapas': [{'numero': i+1, 'descricao': texto(e, 'etapa'), 'estado': 'pendente'}
                               for i, e in enumerate(etapas)], 'bloqueio': None}
        salvar(registro)
    else:
        registro, sha = carregar(dados.get('id'))
        if acao == 'status':
            return json.dumps(registro, ensure_ascii=False)
        if registro['estado'] == 'entregue_para_revisao':
            raise ValueError('trabalho já entregue para revisão; registro preservado')
        if acao == 'registrar_etapa':
            numero = dados.get('etapa')
            if type(numero) is not int or not 1 <= numero <= len(registro['etapas']):
                raise ValueError('etapa inválida')
            etapa = registro['etapas'][numero-1]
            if etapa['estado'] != 'pendente':
                raise ValueError('etapa já registrada; evidência anterior preservada')
            path = texto(dados.get('arquivo'), 'arquivo')
            if not path.startswith('MEMORIA/') or any(x in ('', '.', '..') for x in path.split('/')) or '?' in path or '#' in path or '\\' in path:
                raise ValueError('evidência deve ser caminho privado em MEMORIA/')
            info = C.gh('GET', f'/repos/{C.REPO}/contents/{path}')
            if not isinstance(info, dict) or not info.get('sha') or not info.get('content'):
                raise ValueError('evidência não observável')
            if not base64.b64decode(info['content']).strip():
                raise ValueError('arquivo de evidência vazio')
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
            raise ValueError('ação desconhecida: criar/status/registrar_etapa/bloquear/retomar/entregar')
        salvar(registro, sha)
    return json.dumps(registro, ensure_ascii=False)
