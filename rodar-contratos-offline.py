"""Uma suíte por cópia, sem segredos herdados nem rede externa. Não publica nada."""
from pathlib import Path
import os,re,shutil,subprocess,sys,tempfile
GUARDA='''import socket
_original=socket.socket.connect
def conectar(self,address):
 if isinstance(address,tuple) and str(address[0]) not in ('127.0.0.1','localhost','::1'):raise RuntimeError('CONTRATO_REDE_EXTERNA_BLOQUEADA')
 return _original(self,address)
socket.socket.connect=conectar
'''
def rodar(nome):
 raiz=Path(__file__).resolve().parent
 if not re.fullmatch(r'teste-[a-z0-9-]+\.py',nome) or nome=='teste-chat.py' or not (raiz/nome).is_file():raise ValueError('suíte não permitida')
 with tempfile.TemporaryDirectory(prefix='motor-contrato-') as d:
  d=Path(d);copia=d/'motor';shutil.copytree(raiz,copia,ignore=shutil.ignore_patterns('.git','MEMORIA','.memoria-sync*','__pycache__','.env','.token*','node_modules'))
  g=d/'guarda';g.mkdir();(g/'sitecustomize.py').write_text(GUARDA)
  env={k:os.environ[k] for k in ['HOME','PATH','LANG','LC_ALL','TMPDIR'] if k in os.environ};env['PYTHONPATH']=str(g)
  return subprocess.run([sys.executable,str(copia/nome)],cwd=copia,env=env,timeout=100).returncode
if __name__=='__main__':
 try:sys.exit(rodar(sys.argv[1]))
 except (ValueError,IndexError,subprocess.TimeoutExpired) as e:print('Contrato não aprovado:',type(e).__name__);sys.exit(1)
