"""Executa SOMENTE projeto isolado em Docker, nunca Python gerado no host."""
import json,os,pathlib,re,subprocess,tempfile,uuid
IMAGEM='python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159'
HARNESS='''import ast,json,pathlib,unittest,sys,io
p=pathlib.Path('/projeto');fs=list(p.rglob('*.py'))
for f in fs:ast.parse(f.read_text(),filename=str(f))
sys.path.insert(0,str(p));s=unittest.defaultTestLoader.discover(str(p),pattern='test_*.py');n=s.countTestCases()
if n<1:raise RuntimeError('nenhum teste executável')
b=io.StringIO();r=unittest.TextTestRunner(stream=b,verbosity=1).run(s)
print('RESULTADO_CI:'+json.dumps({'testes':n,'sucesso':r.wasSuccessful(),'detalhes':b.getvalue()[-6000:]}))
sys.exit(0 if r.wasSuccessful() else 1)
'''
def validar_arquivos(fs):
 if not isinstance(fs,dict) or not 2<=len(fs)<=12:raise ValueError('projeto exige 2 a 12 arquivos')
 if sum(len(str(v).encode()) for v in fs.values())>100000:raise ValueError('projeto grande demais')
 for n,v in fs.items():
  if not isinstance(n,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,60}\.(py|md|json|txt)',n) or n in ('sitecustomize.py','usercustomize.py'):raise ValueError('caminho não permitido')
  if not isinstance(v,str) or not v.strip() or len(v)>40000:raise ValueError('conteúdo inválido')
 if not any(n.startswith('test_') and n.endswith('.py') for n in fs):raise ValueError('exige unittest test_*.py')
 if not any(n.endswith('.py') and not n.startswith('test_') for n in fs):raise ValueError('falta implementação')
 return fs

def _container(fs,harness=HARNESS):
 validar_arquivos(fs)
 env={k:os.environ[k] for k in ('PATH','HOME','LANG') if k in os.environ}
 # A daemon/socket Docker nunca entra no container. Ambiente do host não é passado.
 with tempfile.TemporaryDirectory(prefix='projeto-autonomo-') as td:
  p=pathlib.Path(td);p.chmod(0o755);src=p/'projeto';src.mkdir(mode=0o755)
  for n,v in fs.items():(src/n).write_text(v);(src/n).chmod(0o644)
  h=p/'avaliar.py';h.write_text(harness);h.chmod(0o644)
  subprocess.run(['docker','pull',IMAGEM],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=120)
  nome='autonomia-'+uuid.uuid4().hex
  cmd=['docker','run','--name',nome,'--rm','--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534','--pids-limit=64','--memory=256m','--cpus=1','--tmpfs','/tmp:rw,noexec,nosuid,size=32m','--mount',f'type=bind,src={src},dst=/projeto,readonly','--mount',f'type=bind,src={h},dst=/avaliar.py,readonly','--env','PYTHONDONTWRITEBYTECODE=1',IMAGEM,'python','-B','/avaliar.py']
  # Não capturar stdout sem limite em memória: processo tem 45s e arquivo limitado por ulimit.
  log=p/'saida.txt'
  try:
   with log.open('wb') as f:
    r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=45,preexec_fn=_limite_saida)
   with log.open('rb') as f:out=f.read(65536).decode('utf-8','replace')
  except subprocess.TimeoutExpired:
   return {'sucesso':False,'testes':0,'detalhes':'tempo limite de 45s'}
  finally:
   subprocess.run(['docker','rm','-f',nome],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
  linhas=[l[len('RESULTADO_CI:'):] for l in out.splitlines() if l.startswith('RESULTADO_CI:')]
  if not linhas:return {'sucesso':False,'testes':0,'detalhes':out[-6000:]}
  try:v=json.loads(linhas[-1])
  except (ValueError,TypeError):return {'sucesso':False,'testes':0,'detalhes':'resultado inválido'}
  return {'sucesso':r.returncode==0 and v.get('sucesso') is True and type(v.get('testes')) is int and v['testes']>0,'testes':v.get('testes',0),'detalhes':str(v.get('detalhes',''))[-6000:],**({'observacoes':v['observacoes']} if 'observacoes' in v else {})}

def _limite_saida():
 import resource
 resource.setrlimit(resource.RLIMIT_FSIZE,(65536,65536))


def executar(fs,aceite=None):
 if aceite is not None:
  import aceite_semantico as S
  S.validar(aceite,fs)
 r=_container(fs)
 if aceite is None:return r
 r['aceite_sha256']=S.digest(aceite)
 if not r['sucesso']:return r
 bruto=_container(fs,S.harness(aceite))
 verificacao=S.comparar(aceite,bruto.get('observacoes')) if bruto['sucesso'] else {'sucesso':False,'casos':0,'falhas':['execução de aceite falhou: '+bruto['detalhes']]}
 r['aceite']=verificacao;r['sucesso']=r['sucesso'] and verificacao['sucesso']
 if not verificacao['sucesso']:r['detalhes']='Aceite semântico rejeitado: '+str(verificacao['falhas'])[-5500:]
 return r
