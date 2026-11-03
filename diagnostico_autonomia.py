"""Fotografia somente-leitura; ativo configurado não significa executor disponível."""
import re
import comum as C
import autonomia_reversivel as A

def avaliar(geral, agenda, componente, head):
    if not isinstance(geral,dict): return {'geral':'não observável','agenda':'não observável','componente':'não observável'}
    resultado={'geral':'ativa' if geral.get('ativo') is True else 'pausada'}
    for nome,p in [('agenda',agenda),('componente',componente)]:
        if not isinstance(p,dict): estado='não configurado'
        elif p.get('ativo') is not True: estado='pausado'
        elif geral.get('ativo') is not True: estado='bloqueado pela pausa geral'
        elif not re.fullmatch('[0-9a-f]{40}',str(head or '')): estado='versão do executor não observável'
        elif p.get('worker_sha')!=head: estado='bloqueado por versão; requer revisão do pin'
        else: estado='configurado; versão compatível, execução não comprovada'
        resultado[nome]=estado
    return resultado

def consultar():
    try:
        geral,_=A.ler(C.REPO,A.POLITICA_PATH)
        agenda,_=A.ler(C.REPO,'POLITICAS/agenda-manutencao.json')
        componente,_=A.ler(C.REPO,'POLITICAS/chat-componentes.json')
        head=C.gh('GET',f'/repos/{C.REPO_ROBO}/git/ref/heads/main')['object']['sha']
        return avaliar(geral,agenda,componente,head)
    except Exception:
        return {'geral':'não observável','agenda':'não observável','componente':'não observável'}

def texto():
    d=consultar()
    return '**Autonomia — configuração observada:**\n'+ '\n'.join('- '+k+': '+v for k,v in d.items())+'\nConfiguração não comprova entrega, disponibilidade ou qualidade.'
