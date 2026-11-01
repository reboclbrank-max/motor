"""Ensaio interno autorizado: três runners, modelo/API reais e interrupção de processo.

Só uma Issue sintética, fechada e marcada; nunca cancela atendimento ou publica fora
GitHub. Log do subprocesso não é publicado. Não representa queda da infraestrutura.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import comum as C
import trabalhos as T
import responder as R

MARCA = '<!--ensaio-retomada:isolado-->'
PEDIDO = '''Trabalho interno de triagem, sem marketing, sem pesquisa e sem ações externas.
Use TRABALHO para criar UM trabalho com DUAS etapas: analisar ocorrências e redigir relatório.
Execute usando registrar_etapa com conteudo e depois entregar. Não fique só na promessa.
Dados fornecidos: A: importação falhou por credencial recusada, prioridade alta;
B: backup terminou com sucesso, sem intervenção; C: leitura falhou por timeout, prioridade média.
Priorize A antes de C; separe sucesso de falha; indique próximos passos propostos, sem alegar executá-los.
Na retomada não recrie trabalho nem refaça etapa com evidência: continue as pendentes.
Só use a ferramenta TRABALHO neste ensaio. O resultado esperado são DOIS arquivos com texto em português e recibo final.
'''


def registro(numero):
    with T.contexto_mensagem(numero, f'a{numero}', (MARCA+'\n'+PEDIDO).strip()):
        return T.recuperar_da_origem()


def conferir_issue(numero):
    i=C.gh('GET',f'/repos/{C.REPO}/issues/{numero}')
    if i.get('state')!='closed' or not i.get('body','').startswith(MARCA) or i.get('user',{}).get('login')!=C.DONO_GITHUB:
        raise ValueError('Issue não é ensaio fechado do dono')
    return i


def filho(fase, numero):
    issue=conferir_issue(numero)
    Path('evento-ensaio.json').write_text(json.dumps({'action':'opened','issue':issue}))
    os.environ.update(GITHUB_EVENT_NAME='issues',GITHUB_EVENT_PATH=str(Path('evento-ensaio.json').resolve()),REFORCO_RELEVANCIA='0')
    # Isola efeitos auxiliares de atendimento: não drena pedidos de usuários,
    # não dispara avisos, nem ensina/cacheia dados fictícios na memória global.
    C.ARQ_FILA_RESPOSTAS=f'MEMORIA/ensaios/retomada-{numero}/fila.json'
    R.drenar_fila_respostas=lambda **kwargs: None
    C.checar_avisos_rapido=lambda: {}
    C.registrar_diario=lambda *args,**kwargs: True
    C.registrar_conversa=lambda *args,**kwargs: True
    C.registrar_placar=lambda *args,**kwargs: True
    C.registrar_resposta_cache=lambda *args,**kwargs: False
    with T.contexto_mensagem(numero,f'a{numero}',issue['body']):id_isolado=T.id_da_origem()
    C._capturar_licao=lambda texto: False  # não ensinar dados fictícios à memória real
    C._precisa_chao=lambda texto: False  # nenhum pedido de pesquisa externa no ensaio
    contagem={'modelo_chamadas':0,'ferramentas':0,'motores':[]}
    def salvar():Path('contagem-ensaio.json').write_text(json.dumps(contagem))
    modelo=C.chamar_llm
    def medido(*args,**kwargs):
        contagem['modelo_chamadas']+=1;salvar();kwargs['preferir']='gemini1' if any(p['id']=='gemini1' for p in C.montar_provedores()) else 'mistral'
        resposta=modelo(*args,**kwargs)
        if resposta[1]:contagem['motores'].append(resposta[1])
        salvar();return resposta
    C.chamar_llm=medido
    executar=C.executar_ferramenta
    def limitado(tipo, argumento):
        if T.id_da_origem()!=id_isolado:return 'Origem fora do ensaio isolado; operação bloqueada.'
        if tipo!='TRABALHO':return 'Ensaio interno: use somente TRABALHO, sem efeitos externos.'
        dados=json.loads(argumento)
        if dados.get('acao')=='criar' and (not isinstance(dados.get('etapas'),list) or len(dados['etapas'])!=2):
            return 'O pedido exige exatamente DUAS etapas: analisar ocorrências e redigir relatório. Refaça a chamada criar; não crie metas de marketing.'
        if dados.get('acao')!='criar' and dados.get('id')!=id_isolado:
            return 'Use somente o ID desta mensagem; não toque em outros trabalhos.'
        contagem['ferramentas']+=1;salvar();resultado=executar(tipo,argumento)
        if fase=='interromper' and dados.get('acao')=='registrar_etapa' and dados.get('etapa')==1:
            r=registro(numero)
            if r and r['etapas'][0]['estado']=='evidencia_registrada':os._exit(23)
        return resultado
    C.executar_ferramenta=limitado
    salvar()
    return R.principal()


def saida(chave, valor):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write(f'{chave}={valor}\n')


def executar(fase, numero):
    # Um processo novo por fase. Nos Actions, cada fase também está em outro job/runner.
    with tempfile.TemporaryDirectory(prefix='ensaio-') as tmp:
        proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'filho',fase,str(numero)],cwd=tmp,capture_output=True,timeout=540)
        f=Path(tmp)/'contagem-ensaio.json';contagem=json.loads(f.read_text()) if f.exists() else {}
    return proc.returncode,contagem


def main(fase, numero=None):
    if fase=='iniciar':
        issue=C.gh('POST',f'/repos/{C.REPO}/issues',{'title':'Ensaio isolado de retomada — '+os.environ.get('GITHUB_RUN_ID','local'),'body':MARCA+'\n'+PEDIDO})
        numero=issue['number'];saida('issue',numero)
        C.gh('PATCH',f'/repos/{C.REPO}/issues/{numero}',{'state':'closed'})
        conferir_issue(numero)
        contagem={}
        for tentativa in range(3):
            code,contagem=executar('interromper',numero)
            if code==23:break
        r=registro(numero)
        assert code==23, f'interrupção esperada23, obtida{code}; chamadas={contagem.get("modelo_chamadas",0)}'
        assert r and len(r['etapas'])==2 and r['etapas'][0]['estado']=='evidencia_registrada' and r['etapas'][1]['estado']=='pendente'
        assert contagem.get('modelo_chamadas',0)>0
        saida('etapa1',r['etapas'][0]['evidencia']['sha_blob']);saida('trabalho',r['id'])
        print(json.dumps({'fase':fase,'interrupcao_processo':23,'etapa1_salva':True,'etapa2_pendente':True,'modelo':contagem},ensure_ascii=False))
    else:
        conferir_issue(numero);antes=registro(numero);assert antes
        sha1=antes['etapas'][0]['evidencia']['sha_blob']
        if fase=='retomar':assert sha1==os.environ['SHA_ETAPA1']
        comentarios=C.comentarios_da_conversa_verificados(numero)
        contagem={}
        for tentativa in range(3 if fase=='retomar' else 1):
            code,contagem=executar('normal',numero);r=registro(numero)
            if code==0 and r and r.get('estado')=='entregue_para_revisao':break
        assert code==0 and r['id']==antes['id'] and r['estado']=='entregue_para_revisao'
        assert r['etapas'][0]['evidencia']['sha_blob']==sha1
        recibo=T.recibo(r['id']);assert 'Etapa 2' in recibo
        finais=[c for c in C.comentarios_da_conversa_verificados(numero) if C.comentario_e_resposta_final(c) and f'<!--resp:a{numero}-->' in c.get('body','')]
        assert len(finais)==1
        textos=[]
        for etapa in r['etapas']:
            info=C.gh('GET',f'/repos/{C.REPO}/contents/{etapa["evidencia"]["arquivo"]}')
            b=base64.b64decode(info['content']);assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==etapa['evidencia']['sha_blob']
            assert len(b)>60;textos.append(b.decode())
        if fase=='conferir':
            assert contagem.get('modelo_chamadas',0)==0 and contagem.get('ferramentas',0)==0
            assert len(comentarios)==len(C.comentarios_da_conversa_verificados(numero))
        print(json.dumps({'fase':fase,'mesmo_trabalho':True,'etapa1_preservada':True,'estado':r['estado'],'arquivos_conferidos':len(textos),'respostas_finais':len(finais),'modelo':contagem},ensure_ascii=False))

if __name__=='__main__':
    try:
        if sys.argv[1]=='filho':sys.exit(filho(sys.argv[2],int(sys.argv[3])))
        main(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else None)
    except Exception as e:
        # Sem corpo de resposta, prompt, URL de autenticação ou mensagem de exceção em log.
        print('ensaio não aprovado:',type(e).__name__);sys.exit(1)
