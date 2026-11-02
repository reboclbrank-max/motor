"""Contrato declarativo congelado. Comparação no controlador, não no código gerado.
Não é oráculo semântico universal: casos derivados por modelo também podem errar.
"""
import json,re,ast

def digest(v):
 import hashlib
 return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()).hexdigest()

def validar(v,fs):
 if not isinstance(v,dict) or set(v)!={'etapas','casos'}:raise ValueError('aceite exige apenas etapas e casos')
 etapas=v['etapas'];casos=v['casos']
 if not isinstance(etapas,list) or not 1<=len(etapas)<=5 or any(not isinstance(t,str) or not 3<=len(t)<=400 for t in etapas):raise ValueError('1 a 5 subtarefas textuais são obrigatórias')
 if not isinstance(casos,list) or not 1<=len(casos)<=12:raise ValueError('aceite exige 1 a 12 casos')
 if len(json.dumps(v,ensure_ascii=False,allow_nan=False).encode())>20000:raise ValueError('contrato de aceite grande demais')
 for c in casos:
  if not isinstance(c,dict) or set(c)-{'etapa','modulo','funcao','args','kwargs','esperado','erro','nao_muta','script','entrada','codigo'}:raise ValueError('campos de caso não permitidos')
  if type(c.get('etapa')) is not int or not 1<=c['etapa']<=len(etapas):raise ValueError('etapa de caso inválida')
  if 'script' in c:
   if set(c)-{'etapa','script','args','entrada','esperado','codigo'} or c['script'] not in fs or not c['script'].endswith('.py') or c['script'].startswith('test_'):raise ValueError('script fora da implementação')
   if not isinstance(c.get('args',[]),list) or any(not isinstance(a,str) for a in c.get('args',[])) or not isinstance(c.get('entrada',''),str) or not isinstance(c.get('esperado'),str) or type(c.get('codigo',0)) is not int or not 0<=c.get('codigo',0)<=255:raise ValueError('CLI exige args textuais, entrada/esperado texto e código0a255')
  else:
   if not isinstance(c.get('modulo'),str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}',c['modulo']) or c['modulo'].startswith('test_') or c['modulo']+'.py' not in fs:raise ValueError('módulo fora da implementação proposta')
   if not isinstance(c.get('funcao'),str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}',c['funcao']):raise ValueError('função pública inválida')
   if not any(isinstance(n,ast.FunctionDef) and n.name==c['funcao'] for n in ast.parse(fs[c['modulo']+'.py']).body):raise ValueError('função pública não está definida no módulo proposto')
   if not isinstance(c.get('args'),list) or not isinstance(c.get('kwargs',{}),dict) or any(not isinstance(k,str) or not k.isidentifier() or k.startswith('_') for k in c.get('kwargs',{})):raise ValueError('argumentos inválidos')
   if ('esperado' in c)==('erro' in c):raise ValueError('use esperado OU erro')
   if 'erro' in c and c['erro'] not in ('ValueError','TypeError','KeyError','IndexError','ZeroDivisionError'):raise ValueError('exceção de aceite não permitida')
  if type(c.get('nao_muta',False)) is not bool:raise ValueError('nao_muta precisa ser booleano')
 if {c['etapa'] for c in casos}!=set(range(1,len(etapas)+1)):raise ValueError('cada subtarefa precisa de caso observável')
 return v

def chamadas(v):
 # Nunca enviar esperado/erro ao programa avaliado.
 return [{k:c[k] for k in ('modulo','funcao','args','kwargs','script','entrada') if k in c} for c in v['casos']]

def comparar(v,observados):
 if not isinstance(observados,list) or len(observados)!=len(v['casos']):return {'sucesso':False,'casos':0,'falhas':['quantidade de observações divergente']}
 falhas=[]
 for i,(c,o) in enumerate(zip(v['casos'],observados),1):
  if not isinstance(o,dict):falhas.append(f'caso{i}: observação inválida');continue
  ok=(o.get('saida')==c['esperado'] and o.get('codigo')==c.get('codigo',0)) if 'script' in c else o.get('erro')==c['erro'] if 'erro' in c else 'retorno' in o and 'erro' not in o and digest(o['retorno'])==digest(c['esperado'])
  if not ok:falhas.append(f'caso{i}: resultado diverge do contrato; esperado='+json.dumps({k:c[k] for k in ('esperado','erro') if k in c},ensure_ascii=False)+'; observado='+json.dumps(o,ensure_ascii=False)[:1500])
  if c.get('nao_muta') and (digest(o.get('args_depois'))!=digest(c['args']) or digest(o.get('kwargs_depois'))!=digest(c.get('kwargs',{}))):falhas.append(f'caso{i}: argumentos alterados')
 return {'sucesso':not falhas,'casos':len(observados),'falhas':falhas}

# O processo supervisor no container não importa módulos do projeto.
# Cada chamada de função/CLI roda num subprocesso; expectativas ficam no host.
FUNCAO = """import json,sys,importlib,contextlib,io
c=json.loads(sys.stdin.read());args=c['args'];kwargs=c.get('kwargs',{})
with contextlib.redirect_stdout(io.StringIO()):
 try:
  sys.path.insert(0,'/projeto');f=getattr(importlib.import_module(c['modulo']),c['funcao'])
 except Exception as e:o={'falha_estrutura':'importacao '+type(e).__name__}
 else:
  try:o={'retorno':f(*args,**kwargs)}
  except Exception as e:o={'erro':type(e).__name__}
  else:
   try:json.dumps(o,allow_nan=False)
   except Exception as e:o={'falha_estrutura':'retorno nao JSON '+type(e).__name__}
o.update(args_depois=args,kwargs_depois=kwargs)
print(json.dumps(o,allow_nan=False))
"""
HARNESS="""import json,sys,subprocess
chamadas=json.loads(PAYLOAD)
observados=[]
for c in chamadas:
 try:
  if 'script' in c:
   r=subprocess.run([sys.executable,'-B','/projeto/'+c['script']]+c.get('args',[]),input=c.get('entrada',''),text=True,capture_output=True,timeout=40,cwd='/tmp')
   o={'saida':r.stdout,'codigo':r.returncode}
  else:
   r=subprocess.run([sys.executable,'-B','-c',FUNCAO],input=json.dumps(c),text=True,capture_output=True,timeout=40,cwd='/tmp')
   o=json.loads(r.stdout) if r.returncode==0 else {'erro':'ProcessoFalhou'}
 except Exception as e:o={'erro':type(e).__name__}
 observados.append(o)
print('RESULTADO_CI:'+json.dumps({'sucesso':True,'testes':len(observados),'observacoes':observados},allow_nan=False))
"""

def harness(v):
 return HARNESS.replace('FUNCAO',repr(FUNCAO)).replace('PAYLOAD',repr(json.dumps(chamadas(v),ensure_ascii=False,allow_nan=False)))
