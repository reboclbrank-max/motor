"""Agenda determinística de manutenção. Política privada, sem LLM; transporte autenticado já existente.
Acorda no worker existente. Não escreve código, não publica mensagens fora do privado,
não cria contas, não envia e-mail e não escolhe workflows a partir de texto livre.
"""
import base64,datetime,hashlib,json,os,re,time
import comum as C
import autonomia_reversivel as A
POLITICA='POLITICAS/agenda-manutencao.json'
ESTADO='MEMORIA/agenda-manutencao/estado.json'
MARCA='<!--agenda-manutencao:diario-v1-->'
TESTES='.github/workflows/testes.yml'
CI='.github/workflows/projeto-autonomo.yml'

def epoch(texto):
 return datetime.datetime.fromisoformat(texto.replace('Z','+00:00')).timestamp()

def politica():
 p,_=A.ler(C.REPO,POLITICA)
 if not p or p.get('ativo') is not True:return None
 if p.get('versao')!=1 or p.get('aprovacao')!='dono-manutencao-privada-r0-v1' or p.get('dono')!=C.DONO_GITHUB or p.get('repo_privado')!=C.REPO or p.get('orcamento_reais')!=0 or p.get('publicacoes')!='somente_codigo_tecnico_aprovado':raise A.Revisao('Política de agenda incompatível.')
 if not re.fullmatch('[0-9a-f]{40}',p.get('worker_sha','')) or type(p.get('iniciar_apos')) not in (int,float):raise A.Revisao('Pin/ativação da agenda inválidos.')
 if os.environ.get('GITHUB_SHA')!=p['worker_sha']:raise A.Revisao('Worker mudou; agenda aguarda revisão do pin, sem efeitos.')
 A.politica()
 return p

def guardar(p):
 if C.gh('GET',f'/repos/{C.REPO_ROBO}/git/ref/heads/main')['object']['sha']!=p['worker_sha']:raise A.Revisao('Main mudou; revisar pin antes de efeitos da agenda.')
 if politica()!=p:raise A.Revisao('Política mudou; interromper agenda.')
 A.garantir_workflows(A.politica())

def salvar(s,p):
 guardar(p);old=s.pop('_sha',None);s['_sha']=A.gravar(C.REPO,ESTADO,s,old)

def marcadores(p,numero=None):
 encontrados=[]
 for page in range(1,6):
  path=f'/repos/{C.REPO}/issues/{numero}/comments?per_page=100&page={page}' if numero else f'/repos/{C.REPO}/issues?state=all&per_page=100&page={page}'
  rows=C.gh('GET',path) or [];encontrados.extend(rows)
  if len(rows)<100:return encontrados
 raise A.Revisao('Diário excedeu janela de conferência; não duplicar registros.')

def diario(s,p):
 if s.get('diario'):return s['diario']
 rows=[i for i in marcadores(p) if not i.get('pull_request') and MARCA in (i.get('body') or '') and (i.get('user') or {}).get('login')==C.DONO_GITHUB]
 if len(rows)>1:raise A.Revisao('Mais de um diário; requer conferência.')
 if rows:s['diario']=rows[0]['number'];salvar(s,p);return s['diario']
 if s.get('criacao_incerta'):raise A.Revisao('Criação do diário sem recibo; não repetir POST incerto.')
 s['criacao_incerta']=True;salvar(s,p);guardar(p)
 v=C.gh('POST',f'/repos/{C.REPO}/issues',{'title':'🛠 Agenda privada de manutenção do Chat','body':'🤖 Agenda autorizada pelo dono para manter o Chat. Prioridades: recuperar CI técnica segura, acompanhar incidentes e verificar regressões diariamente. R$0, sem marketing, mensagens externas, contas, credenciais, exclusões ou autoedição de executores. O relógio existente acorda a agenda; silêncio não prova saúde. '+MARCA})
 if type((v or {}).get('number')) is not int:raise A.Revisao('Diário criado sem recibo válido.')
 s['diario']=v['number'];s.pop('criacao_incerta',None);salvar(s,p);return s['diario']

def registrar(s,p,chave,texto):
 numero=diario(s,p);marca='<!--agenda-evento:'+hashlib.sha256(chave.encode()).hexdigest()[:24]+'-->'
 if s.get('eventos',{}).get(chave)=='enviado':return
 # Reconcilia POST com resposta incerta, em vez de repeti-lo.
 if s.get('eventos',{}).get(chave)=='incerto':
  if any(marca in (c.get('body') or '') and (c.get('user') or {}).get('login')==C.DONO_GITHUB for c in marcadores(p,numero)):
   s['eventos'][chave]='enviado';salvar(s,p);return
  raise A.Revisao('Registro sem recibo; não duplicar mensagem privada.')
 if len(s.get('eventos',{}))>=500:raise A.Revisao('Limite de eventos atingido; preservar sem truncar histórico.')
 s.setdefault('eventos',{})[chave]='incerto';salvar(s,p);guardar(p)
 v=C.gh('POST',f'/repos/{C.REPO}/issues/{numero}/comments',{'body':'🤖 **Agenda de manutenção**\n\n'+texto+'\n\n'+marca})
 if not (v or {}).get('id'):raise A.Revisao('Comentário sem recibo.')
 s['eventos'][chave]='enviado';salvar(s,p)

def permitido(r,p):
 return r.get('event')=='workflow_dispatch' and r.get('head_sha')==p['worker_sha'] and (r.get('actor') or {}).get('login')==C.DONO_GITHUB and r.get('path') in (TESTES,CI) and epoch(r['created_at'])>=p['iniciar_apos']

def seguro_retomar(r,p):
 if not permitido(r,p) or r.get('status')!='completed' or r.get('conclusion')!='failure' or not 1<=int(r.get('run_attempt',1))<3:return False
 if r['path']==TESTES:return True
 m=re.search(r'\b([0-9a-f]{32})\b',r.get('display_title',''))
 if not m:return False
 ident=m.group(1);st,_=A.ler(C.REPO,A.estado_path(ident))
 if not st or st.get('fase') not in ('ci_despachando','ci_aguardando') or epoch(r['created_at'])<st.get('dispatch_em',0)-5:return False
 A.conferir_pr(st);ci,_=A.ler(C.REPO,A.RAIZ+'/'+ident+'/ci/'+st['head']+'.json')
 # Falha de código já tem o seu reparador; não refazer testes cegamente.
 return ci is None or ci.get('sucesso') is True and ci.get('run_id')==r['id'] and ci.get('head')==st['head'] and (not st.get('aceite') or ci.get('aceite_sha256')==A.S.digest(st['aceite']))

def executar():
 p=politica()
 if p is None:return {'ativo':False}
 s,old=A.ler(C.REPO,ESTADO)
 if s is None:s={'versao':1,'acoes':{},'eventos':{},'ultima_verificacao':0,'pendente':None}
 elif s.get('versao')!=1:raise A.Revisao('Estado da agenda incompatível.')
 s['_sha']=old;now=time.time();dia=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).date().isoformat()
 runs=C.gh('GET',f'/repos/{C.REPO_ROBO}/actions/runs?per_page=100')['workflow_runs']
 pend=s.get('pendente')
 if pend:
  matches=[r for r in runs if permitido(r,p) and (r['id']==pend['run'] if pend.get('run') else r['path']==TESTES and epoch(r['created_at'])>=pend['em']-5)]
  if len(matches)>1 and not pend.get('run'):raise A.Revisao('Mais de uma execução na janela; não inventar correlação.')
  r=matches[0] if matches else None
  if r is None or int(r.get('run_attempt',1))<pend.get('attempt',1):
   if now-pend['em']>1800:
    registrar(s,p,'incerto-'+pend['chave'],'Envio sem execução confirmada após30min. Não repeti o efeito; requer conferência.')
    # O aviso já está registrado e a execução não vai mais aparecer (ex.: pin do worker trocado,
    # que muda o head_sha aceito por `permitido`). Sem isto o pendente fica órfão e a agenda
    # responde "aguardando" para sempre, nunca mais escolhendo prioridade. Encerrar não repete efeito.
    if s.get('eventos',{}).get('incerto-'+pend['chave'])=='enviado':
     s['pendente']=None;salvar(s,p);return {'incerto_encerrado':pend['chave']}
   return {'aguardando':True,'incerto':r is None}
  if r['status']!='completed':return {'aguardando':True,'run':r['id']}
  registrar(s,p,'resultado-'+pend['chave'],'Execução técnica '+str(r['id'])+' terminou '+str(r.get('conclusion'))+'. Evidência: https://github.com/'+C.REPO_ROBO+'/actions/runs/'+str(r['id'])+'. Não equivale a correção semântica universal.')
  if r['path']==TESTES:s['ultima_verificacao']=now
  s['pendente']=None;salvar(s,p)
  return {'observado':r['id'],'conclusao':r.get('conclusion')}
 if s.get('dia')!=dia:s['dia']=dia;s['usados']=0
 # Primeiro as falhas novas da infraestrutura aprovada, nunca o histórico anterior à ativação.
 candidatos=[r for r in runs if seguro_retomar(r,p) and 'retry-'+str(r['id'])+'-'+str(r.get('run_attempt',1)) not in s['acoes']]
 if candidatos:
  r=sorted(candidatos,key=lambda x:x['created_at'])[0];chave='retry-'+str(r['id'])+'-'+str(r.get('run_attempt',1));kind='retomar';endpoint=f'/repos/{C.REPO_ROBO}/actions/runs/{r["id"]}/rerun-failed-jobs';body=None;run=r['id'];attempt=int(r.get('run_attempt',1))+1
 elif now-s.get('ultima_verificacao',0)>=86400:
  chave='verificar-'+dia+'-'+p['worker_sha'][:12]
  if chave in s['acoes']:return {'sem_acao':True}
  kind='verificar';endpoint=f'/repos/{C.REPO_ROBO}/actions/workflows/testes.yml/dispatches';body={'ref':'main'};run=None;attempt=1
 else:return {'sem_acao':True}
 if s.get('usados',0)>=2:return {'orcamento_esgotado':True}
 diario(s,p)
 s['acoes'][chave]={'tipo':kind,'em':now};s['usados']=s.get('usados',0)+1;s['pendente']={'chave':chave,'tipo':kind,'em':now,'run':run,'attempt':attempt}
 salvar(s,p);guardar(p)
 # Resposta incerta deixa pendente para reconciliação; nunca reenviar automaticamente.
 C.gh('POST',endpoint,body)
 registrar(s,p,'inicio-'+chave,'Prioridade selecionada automaticamente: '+kind+'. Efeito técnico limitado, orçamento reservado antes do envio. Máximo2ações/dia; sem modelos, dinheiro ou publicação de dados.')
 return {'acao':kind,'aguardando':True}
