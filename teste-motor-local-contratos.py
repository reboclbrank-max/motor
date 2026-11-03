"""Regressões offline: configuração, contexto íntegro e cancelamento real."""
import json, os, sys, tempfile, time, types, unittest
from unittest.mock import patch
import motor_local as M
class Fake:
 def __init__(self, **kw): self.kw=kw;self.closed=False;self.messages=None
 def close(self):self.closed=True
 def tokenize(self, text):return list(range(len(text)//4))
 def create_chat_completion(self, **kw):self.messages=kw['messages'];return {'choices':[{'message':{'content':'ok'}}]}
class Local(unittest.TestCase):
 def setUp(self):
  for name,value in [('_llm',None),('_falhou',False),('_configuracao',None)]:
   p=patch.object(M,name,value);p.start();self.addCleanup(p.stop)
 def test_configuracao_muda_e_fecha_modelo_anterior(self):
  with patch.dict(sys.modules,{'llama_cpp':types.SimpleNamespace(Llama=Fake)}),patch.object(M,'baixar',return_value='/fixture'):
   primeiro=M._carregar(2048);self.assertIs(M._carregar(2048),primeiro)
   segundo=M._carregar(4096);self.assertIsNot(segundo,primeiro);self.assertTrue(primeiro.closed);self.assertEqual(segundo.kw['n_ctx'],4096)
   with patch.object(M,'ARQUIVO','outro.gguf'):self.assertIsNot(M._carregar(4096),segundo)
 def test_contexto_preserva_cauda_ou_recusa_sem_gerar(self):
  fake=Fake()
  with patch.object(M,'_carregar',return_value=fake):
   pergunta='x'*4500+'FIM';self.assertEqual(M._gerar(pergunta,'s'*2200,420,4096),('ok',None));self.assertEqual(fake.messages[-1]['content'],pergunta)
   fake.messages=None;r=M._gerar('x'*20000,'',420,2048);self.assertIsNone(r[0]);self.assertIn('não truncada',r[1]);self.assertIsNone(fake.messages)
 def test_timeout_mata_processo_antes_de_efeito_tardio(self):
  import subprocess
  with tempfile.TemporaryDirectory() as d:
   alvo=os.path.join(d,'nao-criar')
   comando=[sys.executable,'-c','import time,pathlib;time.sleep(0.3);pathlib.Path('+repr(alvo)+').write_text("erro")']
   inicio=time.monotonic()
   with self.assertRaises(subprocess.TimeoutExpired):M._executar_limitado(comando,b'',.05,{'PATH':os.environ['PATH']})
   self.assertLess(time.monotonic()-inicio,.3);time.sleep(.35);self.assertFalse(os.path.exists(alvo))
 def test_subprocesso_sem_segredos_e_sem_truncamento(self):
  with patch.dict(os.environ,{'GITHUB_TOKEN':'fixture-segredo','GEMINI_API_KEY':'fixture-segredo'}),patch.object(M,'_executar_limitado',return_value=['ok',None]) as proc:
   self.assertEqual(M.responder('X'*4500),('ok',None));args=proc.call_args.args
   self.assertNotIn('GITHUB_TOKEN',args[3]);self.assertNotIn('GEMINI_API_KEY',args[3]);self.assertEqual(len(json.loads(args[1])['pergunta']),4500);self.assertIn('-I',args[0])
 def test_limites_invalidos_nao_criam_processo(self):
  with patch.object(M,'_executar_limitado') as proc:
   for kw in [{'timeout_s':float('nan')},{'timeout_s':0},{'max_tokens':-1},{'contexto':8192}]:self.assertIsNone(M.responder('x',**kw)[0])
   proc.assert_not_called()
 def test_download_falho_preserva_arquivo_anterior(self):
  with tempfile.TemporaryDirectory() as d,patch.object(M,'CACHE',d),patch.object(M,'ARQUIVO','x.gguf'),patch.object(M,'MIN_BYTES',1),patch('urllib.request.urlopen',side_effect=OSError('falha')):
   self.assertIsNone(M.baixar());self.assertFalse(os.path.exists(os.path.join(d,'x.gguf')))
if __name__=='__main__':unittest.main()
