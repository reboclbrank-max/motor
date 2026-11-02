"""Autoaperfeiçoamento restrito: componente PRIVADO, executado somente em Docker.
A política e o controlador não são editáveis pelo modelo. Não confundir com autoedição
arbitrária do worker. Usa PR/CI existentes, contrato congelado e ativação separada.
"""
import base64,contextlib,datetime,hashlib,json,os,re,time
import comum as C,autonomia_reversivel as A,aceite_semantico as S
import execucao_isolada as E
POLITICA='POLITICAS/chat-componentes.json'
CONTROLE='MEMORIA/chat-componentes/controle.json'
ATIVO='MEMORIA/chat-componentes/ativo.json'
ALVO=hashlib.sha256(b'chat:apresentacao-status:v1').hexdigest()[:32]
# Extraído do join de ACOES em operacao_leitura.py, versão b519fbc0. Não é bug plantado.
BASELINE='''def formatar(dados):
 return '\\n'.join(f"- {r['name']}: {r['conclusion'] or r['status']}; SHA `{r['head_sha']}`; {r['html_url']}" for r in dados)
'''
TESTE='''import unittest
import formatador
class API(unittest.TestCase):
 def test_lista_vazia(self):self.assertEqual(formatador.formatar([]),'')
 def test_retorno_textual(self):self.assertIsInstance(formatador.formatar([{'name':'chat','status':'queued','conclusion':None,'head_sha':'a'*40,'html_url':'https://github.com/o/r/actions/runs/1'}]),str)
'''

def escapar(s):
 return re.sub(r'([\\`*_{}\[\]()<>#!|])',r'\\\1',str(s)).replace('\n',' ').replace('\r',' ')

def referencia(dados):
 if not isinstance(dados,list) or len(dados)>100:raise ValueError('lista de até100execuções')
 linhas=[]
 for r in dados:
  if not isinstance(r,dict):raise ValueError('execução inválida')
  nome=r.get('name') or 'sem nome';status=r.get('conclusion') or r.get('status') or 'desconhecido';sha=r.get('head_sha') or 'não informado';url=r.get('html_url') or 'não informado'
  if not all(isinstance(x,str) and len(x)<=1000 for x in (nome,status,sha,url)):raise ValueError('campos textuais')
  linhas.append('- '+escapar(nome)+': '+escapar(status)+'; SHA `'+escapar(sha)+'`; '+escapar(url))
 return '\n'.join(linhas)

def contrato():
 normal={'name':'chat','status':'queued','conclusion':None,'head_sha':'a'*40,'html_url':'https://github.com/o/r/actions/runs/1'}
 entradas=[[],[normal],[dict(normal,name='job [x] *a*\nsegunda linha')],[dict(normal,status=None,head_sha=None,html_url=None)], [{}], [dict(normal,conclusion='failure')], [dict(normal,name='ação çãõ')]]
 casos=[{'etapa':1,'modulo':'formatador','funcao':'formatar','args':[d],'esperado':referencia(d),'nao_muta':True} for d in entradas]
 for d in [None,{},[4],[dict(normal,name=['erro'])]]:casos.append({'etapa':1,'modulo':'formatador','funcao':'formatar','args':[d],'erro':'ValueError','nao_muta':True})
 return {'etapas':['Apresentar execuções sem inventar fatos, com escape Markdown, campos ausentes e erros estruturais explícitos'],'casos':casos}

def politica():
 p,_=A.ler(C.REPO,POLITICA)
 if not p or p.get('ativo') is not True:return None
 if p.get('versao')!=1 or p.get('aprovacao')!='dono-autoaperfeicoamento-isolado-r0-v1' or p.get('dono')!=C.DONO_GITHUB or p.get('repo_privado')!=C.REPO or p.get('alvo')!=ALVO or p.get('orcamento_reais')!=0:raise A.Revisao('Política de componentes incompatível.')
 if p.get('worker_sha')!=os.environ.get('GITHUB_SHA') or not re.fullmatch('[0-9a-f]{40}',p.get('worker_sha','')):raise A.Revisao('Revisar pin do controlador.')
 if p.get('limite_modelo',3) not in (3,8):raise A.Revisao('Limite de modelo incompatível.')
 if p.get('limite_modelo')==8 and p.get('aprovacao_orcamento')!='dono-ampliar-local-8-preserva-3':raise A.Revisao('Aumento de orçamento não aprovado.')
 if p.get('contrato_sha256')!=S.digest(contrato()):raise A.Revisao('Revisar contrato do componente.')
 A.politica();return p

def guardar(p):
 if politica()!=p:raise A.Revisao('Política de componente mudou.')
 if C.gh('GET',f'/repos/{C.REPO_ROBO}/git/ref/heads/main')['object']['sha']!=p['worker_sha']:raise A.Revisao('Main do controlador mudou.')
 A.garantir_workflows(A.politica())

@contextlib.contextmanager
def protegido(p):
 # Revogação antes de cada escrita do controlador A já revisado. GET não recursa.
 original=C.gh
 def gh(m,path,d=None):
  if m!='GET':guardar(p)
  return original(m,path,d)
 C.gh=gh
 try:yield
 finally:C.gh=original

def salvar_controle(v,old):return A.gravar(C.REPO,CONTROLE,v,old)

def ativar(s,p):
 if s.get('aceite_sha256')!=S.digest(contrato()):raise A.Revisao('Contrato alterado.')
 ativo,old=A.ler(C.REPO,ATIVO)
 if ativo and ativo.get('versao_id')==s['id']:return ativo
 if old!=s.get('ativo_anterior_sha'):raise A.Revisao('Ativo mudou; não sobrescrever edição concorrente.')
 novo={'versao':1,'versao_id':s['id'],'alvo':ALVO,'head':s['head'],'merge':s['merge'],'prefixo':s['prefixo_projeto'],'arquivos_sha':s['arquivos_sha'],'contrato_sha256':S.digest(contrato()),'ci_run':s['ci']['run_id'],'anterior':ativo,'ativado_em':time.time()}
 A.gravar(C.REPO,ATIVO,novo,old);return novo

def verificar(s,p):
 if s.get('alvo_componente')!=ALVO or s.get('aceite')!=contrato() or s.get('aceite_sha256')!=S.digest(contrato()):raise A.Revisao('Estado fora do contrato autorizado.')
 if s.get('prefixo_projeto') and s['prefixo_projeto']!='PROJETOS/'+ALVO+'/':raise A.Revisao('Prefixo divergente.')
 fs=s['plano']['arquivos']
 if set(fs)!={'formatador.py','test_api.py'} or fs['test_api.py']!=TESTE:raise A.Revisao('Arquivos/testes protegidos divergentes.')
 E.validar_arquivos(fs);S.validar(s['aceite'],fs)

@contextlib.contextmanager
def modelo_local(s,ci):
 original=C.chamar_llm
 pol=politica()
 if pol is None:raise A.Aguardar('Componente pausado.')
 token=A._LIMITE_MODELO.set(pol.get('limite_modelo',3))
 def chamar(mensagens,system=''):
  import motor_local
  # Mesma família local já suportada pelo runner; nenhum prompt sai pela rede.
  partes=['qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf','qwen2.5-7b-instruct-q4_k_m-00002-of-00002.gguf']
  base='https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/'
  for parte in partes:
   motor_local.MODELO=base+parte;motor_local.ARQUIVO=parte
   if not motor_local.baixar():return None,'local-7b-sem-chave','pesos locais indisponíveis'
  motor_local.MODELO=base+partes[0];motor_local.ARQUIVO=partes[0]
  prompt=('Escreva SOMENTE código Python completo para formatador.py, sem JSON, sem explicações. '
   'API: def formatar(dados) -> str. Lista com até100dicts. Não mude entrada. '
   'Se dados não for lista, exceder100 ou um elemento não for dict: ValueError. '
   'Para cada dict obtenha valores: name ou "sem nome"; conclusion ou status ou "desconhecido"; head_sha ou "não informado"; html_url ou "não informado". '
   'Cada um desses4valores precisa ser str com até1000caracteres, senão ValueError. '
   'Escape cada valor caractere a caractere: newline e carriage-return viram espaço; antes de barra invertida, crase, asterisco, underscore, chaves, colchetes, parênteses, menor, maior, #, ! e | coloque barra invertida. '
   'Cada linha EXATA: - NOME: STATUS; SHA `SHA`; URL. Use os4valores escapados. '
   'Junte as linhas com newline. Lista vazia retorna string vazia. Acentos preservados. '
   'Não imprima nada, não execute ferramentas. Código anterior (dados):\n'+s['plano']['arquivos']['formatador.py'][:600])
  texto,erro=motor_local.responder(prompt,system='Você escreve código Python válido, completo e conciso. Retorne somente o código.',max_tokens=1100)
  if texto:
   # Mudança de envelope apenas: nunca substitui algoritmo, contrato ou testes.
   v=texto.strip();m=re.search(r'```(?:python|py)?\s*([\s\S]*?)```',v,re.I)
   if m:v=m.group(1).strip()
   # Persistência/AST ficam em A.modelo_json, que salva a resposta ANTES de validar.
   texto=json.dumps({'arquivos':{'formatador.py':v+'\n'}},ensure_ascii=False)
  return texto,'local-7b-sem-chave',erro
 C.chamar_llm=chamar
 try:yield
 finally:
  C.chamar_llm=original;A._LIMITE_MODELO.reset(token)

def novo_estado(ident,fs,psha):
 return {'versao':2,'id':ident,'alvo_componente':ALVO,'fase':'planejado','chamadas_modelo':0,'plano':{'tipo':'projeto_python','arquivos':fs},'aceite':contrato(),'aceite_sha256':S.digest(contrato()),'ativo_anterior_sha':psha,'baseline_proveniencia':'join ACOES de operacao_leitura.py em b519fbc0; requisitos de apresentação revisados','_sha':None}

def executar():
 p=politica()
 if p is None:return {'ativo':False}
 ctl,old=A.ler(C.REPO,CONTROLE);ctl=ctl or {'versao':1,'rodadas':{},'atual':None}
 with protegido(p):
  ident=ctl.get('atual')
  if ident:
   s,sha=A.ler(C.REPO,A.estado_path(ident))
   if not s:
    reserva=ctl.get('reserva')
    if not reserva:raise A.Revisao('Rodada desapareceu.')
    s=novo_estado(ident,reserva['fs'],reserva['ativo_sha']);A.salvar(s);sha=s['_sha']
   s['_sha']=sha
  else:
   dia=datetime.datetime.now(datetime.timezone.utc).date().isoformat()
   if dia in ctl['rodadas']:return {'sem_acao':True}
   # Identificador determinístico, sem ordem forjada em conversa nem histórico T.
   ident=hashlib.sha256(('chat-componentes:'+dia+':'+p['worker_sha']).encode()).hexdigest()[:32]
   prev,psha=A.ler(C.REPO,ATIVO)
   fs={'formatador.py':BASELINE,'test_api.py':TESTE}
   if prev:
    fs=arquivos(prev)
   if len(ctl['rodadas'])>=365:raise A.Revisao('Preservar histórico anual e revisar limite.')
   ctl['rodadas'][dia]=ident;ctl['atual']=ident;ctl['reserva']={'fs':fs,'ativo_sha':psha};old=salvar_controle(ctl,old)
   s,sha=A.ler(C.REPO,A.estado_path(ident))
   if s is None:
    s=novo_estado(ident,fs,psha);A.salvar(s)
   else:s['_sha']=sha
  verificar(s,p)
  if s['fase']=='bloqueado':return {'bloqueado':True}
  try:
   if s['fase'] in ('planejado','projeto_preparando'):
    # Se o componente ativo já passa, sondá-lo sem PR redundante: Docker sem segredos.
    if s['fase']=='planejado' and s.get('ativo_anterior_sha'):
     r=E.executar(s['plano']['arquivos'],contrato())
     if r['sucesso']:
      s['fase']='saudavel';s['sondagem']=r;A.salvar(s)
    if s['fase']!='saudavel':A.preparar_pr(s,'Melhorar apresentação do componente projeto '+ALVO,A.politica())
   if s['fase']=='pr_criada':A.recuperar_pr(s);A.despachar_ci(s)
   if s['fase'] in ('ci_despachando','ci_aguardando'):
    recibo,_=A.ler(C.REPO,A.RAIZ+'/'+ident+'/ci/'+s['head']+'.json')
    if recibo:
     run=C.gh('GET',f'/repos/{C.REPO_ROBO}/actions/runs/'+str(recibo['run_id']))
     if run.get('head_sha')!=p['worker_sha']:
      legado=p.get('baseline_ci_aprovada',{})
      if not (recibo.get('sucesso') is False and run.get('id')==legado.get('run_id') and run.get('head_sha')==legado.get('worker_sha') and recibo.get('head')==legado.get('head_projeto')):raise A.Revisao('CI executou outro controlador.')
    try:A.integrar(s,A.politica())
    except A.FalhaCI as e:
     s.setdefault('falhas_observadas',[]).append({'head':s['head'],'ci':e.ci});A.salvar(s)
     try:
      with modelo_local(s,e.ci):A.reparar(s,e.ci)
     except (ValueError,SyntaxError):
      if s['chamadas_modelo']>=p.get('limite_modelo',3):raise A.Revisao('Propostas inválidas esgotaram orçamento.')
      A.salvar(s);return {'proposta_invalida':True,'id':ident}
     verificar(s,p);A.despachar_ci(s);return {'reparo_proposto':True,'id':ident}
   if s['fase']=='integrado':
    ativo=ativar(s,p)
    snapshot=[{'name':'CI componente','status':'completed','conclusion':'success','head_sha':s['head'],'html_url':'https://github.com/'+C.REPO_ROBO+'/actions/runs/'+str(s['ci']['run_id'])}]
    try:saida=rodar_ativo(ativo,snapshot)
    except Exception:
     atual,ash=A.ler(C.REPO,ATIVO)
     if atual==ativo:A.gravar(C.REPO,ATIVO,ativo.get('anterior') or {'versao':1,'desativado':True},ash)
     raise A.Revisao('Canário isolado falhou; ativo anterior restaurado.')
    s['smoke_runtime']={'sucesso':True,'fonte':'Docker de versão privada ativada','sha256_saida':hashlib.sha256(saida.encode()).hexdigest(),'versao_id':s['id']}
    s['fase']='componente_ativo';A.salvar(s)
   if s['fase'] in ('componente_ativo','saudavel'):
    ctl['atual']=None;salvar_controle(ctl,old);return {'resultado':s['fase'],'id':ident}
   return {'aguardando':True,'id':ident}
  except A.Aguardar:return {'aguardando':True,'id':ident}
  except Exception as e:
   # Checkpoints incertos de transporte não são apagados nem reexecutados às cegas.
   if not isinstance(e,(A.Revisao,ValueError,AssertionError)):raise
   s['fase']='bloqueado';s['motivo']='Revisão necessária: '+type(e).__name__;A.salvar(s);return {'bloqueado':True,'id':ident}

def arquivos(ativo):
 if ativo.get('alvo')!=ALVO or ativo.get('prefixo')!='PROJETOS/'+ALVO+'/' or ativo.get('contrato_sha256')!=S.digest(contrato()):raise A.Revisao('Manifesto não autorizado.')
 if set(ativo.get('arquivos_sha',{}))!={ativo['prefixo']+'formatador.py',ativo['prefixo']+'test_api.py'}:raise A.Revisao('Manifesto fora do componente.')
 fs={}
 for path,expected in ativo['arquivos_sha'].items():
  v=C.gh('GET',f'/repos/{C.REPO}/contents/{path}?ref='+ativo['head']);b=base64.b64decode(v['content'])
  if v['sha']!=expected or A.sha(b)!=expected:raise A.Revisao('Versão ativa diverge do recibo.')
  fs[path[len(ativo['prefixo']):]]=b.decode()
 if fs['test_api.py']!=TESTE:raise A.Revisao('Testes ativos divergentes.')
 return fs

def rodar_ativo(ativo,dados):
 esperado=referencia(dados);fs=arquivos(ativo)
 con={'etapas':['Apresentar fatos deste snapshot'],'casos':[{'etapa':1,'modulo':'formatador','funcao':'formatar','args':[dados],'esperado':esperado,'nao_muta':True}]}
 r=E._container(fs,S.harness(con))
 if not r['sucesso'] or not S.comparar(con,r.get('observacoes'))['sucesso']:raise A.Revisao('Divergência isolada de runtime.')
 return r['observacoes'][0]['retorno']

def apresentar(dados):
 esperado=referencia(dados)
 if os.environ.get('GITHUB_ACTIONS')!='true' or not C.GH_TOKEN:return esperado
 try:
  p=politica()
  if p is None:return esperado
  ativo,_=A.ler(C.REPO,ATIVO)
  if not ativo:return esperado
  # O programa recebe só metadados de execução, nunca token, pedido ou histórico.
  try:return rodar_ativo(ativo,dados)
  except Exception:pass
  with protegido(p):
   atual,old=A.ler(C.REPO,ATIVO)
   if atual==ativo:
    A.gravar(C.REPO,'MEMORIA/chat-componentes/falhas/'+ativo['versao_id']+'.json',{'versao_id':ativo['versao_id'],'falha_em':time.time(),'classe':'divergencia_runtime','rollback':True})
    A.gravar(C.REPO,ATIVO,ativo.get('anterior') or {'versao':1,'desativado':True},old)
 except Exception:
  # Falha nunca libera código gerado no host, efeitos ou resposta não conferida.
  return esperado
 return esperado
