"""CI independente no worker público. Projeto/saída continuam privados.
Token existe no controlador; nunca é passado ao container. Sem logs de código/saída.
"""
import base64,json,os,re,sys,time
import comum as C
import autonomia_reversivel as A
from execucao_isolada import executar,validar_arquivos

def avaliar(ident):
 if not re.fullmatch(r'[0-9a-f]{32}',ident):raise ValueError('id inválido')
 p=A.politica();s,_=A.ler(C.REPO,A.estado_path(ident))
 if not s or s.get('fase') not in ('ci_despachando','ci_aguardando'):raise ValueError('trabalho não aguarda CI')
 prior=A.opt(f"/repos/{C.REPO}/contents/{A.RAIZ}/{ident}/ci/{s['head']}.json")
 A.garantir_workflows(p);A.conferir_pr(s)
 run_id=int(os.environ['GITHUB_RUN_ID']);url=f'https://github.com/{C.REPO_ROBO}/actions/runs/{run_id}'
 if prior:
  b=base64.b64decode(prior['content']);assert A.sha(b)==prior['sha'];result=json.loads(b)
  if result.get('head')!=s['head'] or result.get('run_id')!=run_id or type(result.get('sucesso')) is not bool:raise ValueError('recibo anterior de outra origem; não repetir')
  if s.get('aceite') and result.get('aceite_sha256')!=A.S.digest(s['aceite']):raise ValueError('contrato do recibo divergente')
 else:
  tree=C.gh('GET',f'/repos/{C.REPO}/git/trees/{s["head"]}?recursive=1');fs={}
  if tree.get('truncated'):raise ValueError('árvore truncada')
  for e in tree['tree']:
   if e['type']=='blob' and e['path'].startswith(s['prefixo_projeto']):
    if e['mode']!='100644':raise ValueError('modo não permitido')
    nome=e['path'][len(s['prefixo_projeto']):];d=C.gh('GET',f'/repos/{C.REPO}/git/blobs/'+e['sha']);b=base64.b64decode(d['content']);assert A.sha(b)==e['sha'];fs[nome]=b.decode()
  validar_arquivos(fs)
  if s.get('aceite') and s.get('aceite_sha256')!=A.S.digest(s['aceite']):raise ValueError('contrato mudou depois do congelamento')
  C.gh('POST',f'/repos/{C.REPO}/statuses/'+s['head'],{'state':'pending','context':A.CONTEXTO_CI,'description':'Testando projeto em container sem rede/segredos','target_url':url})
  try:result=executar(fs,s.get('aceite'))
  except Exception as e:result={'sucesso':False,'testes':0,'detalhes':'Falha de isolamento/execução: '+type(e).__name__}
  if s.get('aceite'):result['aceite_sha256']=A.S.digest(s['aceite'])
  result.update(head=s['head'],run_id=run_id,workflow=A.WORKFLOW)
  A.gravar(C.REPO,A.RAIZ+'/'+ident+'/ci/'+s['head']+'.json',result)
 C.gh('POST',f'/repos/{C.REPO}/statuses/'+s['head'],{'state':'success' if result['sucesso'] else 'failure','context':A.CONTEXTO_CI,'description':'CI isolada passou' if result['sucesso'] else 'CI isolada falhou; não integrar','target_url':url})
 # Retomada fixa, não aceita workflow/ref/repo escolhidos pelo modelo.
 C.gh('POST',f'/repos/{C.REPO_ROBO}/dispatches',{'event_type':'mensagem','client_payload':{'pedido':'autonomia-retomada-'+ident}})
 print('CI de projeto isolado encerrada; sucesso='+str(result['sucesso'])+'; saída e código privados.')
 return 0 if result['sucesso'] else 1
def principal(ident):
 # Só retenta transporte HTTP ou leituras eventualmente inconsistentes do PR.
 # Nunca interpreta falha de teste como falha HTTP, nunca força diff/refs.
 for tentativa in range(3):
  try:return avaliar(ident)
  except (ValueError,RuntimeError,KeyError) as e:
   transiente=bool(re.search(r'HTTP (?:403|404|409|429|5[0-9]{2})\b',str(e))) or isinstance(e,A.Revisao) and str(e) in ('Diff não autorizado; não integrar.','SHA do PR mudou após proposta/CI.')
   if transiente and tentativa<2:
    print('CI: leitura/transporte temporário; repetição limitada, sem alterar permissões ou contrato.');time.sleep(15*(tentativa+1));continue
   print('CI bloqueada após conferência; nenhuma integração autorizada.');return 1
if __name__=='__main__':
 try:raise SystemExit(principal(sys.argv[1]))
 except IndexError:print('CI bloqueada: identificador ausente.');raise SystemExit(1)
