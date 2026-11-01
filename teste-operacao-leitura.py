import base64,json,os,tempfile,unittest
from unittest.mock import patch
import comum as C,trabalhos as T,operacao_leitura as O,responder as R,varrer as V
PEDIDO=O.PREFIXO+'\nObjetivo: auditar dependências. Leia REPO site/.github/workflows/postagem-diaria.yml. Critério de aceite: relatório com versões.'
YAML='''- name: Dependências
  run: pip install Pillow==12.0.0 PyYAML==6.0.2
- name: Barreira offline de autonomia e marca
  run: python3 tools/testes-gif-com-selo.py
'''
class Operacao(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.cwd=os.getcwd();os.chdir(self.tmp.name);self.addCleanup(os.chdir,self.cwd);self.addCleanup(self.tmp.cleanup);self.store={};self.writes=[];self.reads=[]
  self.patch=patch.object(C,'gh',side_effect=self.api);self.patch.start();self.addCleanup(self.patch.stop)
 def api(self,m,p,d=None):
  if m=='GET' and '/git/ref/heads/main' in p:return {'object':{'sha':'a'*40}}
  if m=='GET' and '/site/contents/' in p:
   self.reads.append(p);b=YAML.encode();return {'sha':O.sha(b),'content':base64.b64encode(b).decode()}
  if '/contents/' not in p:raise AssertionError(p)
  key=p.split('/contents/',1)[1].split('?',1)[0]
  if m=='GET':
   if key not in self.store:raise RuntimeError('HTTP 404')
   b=self.store[key];return {'sha':O.sha(b),'content':base64.b64encode(b).decode()}
  self.assertEqual(m,'PUT');self.assertTrue(p.startswith('/repos/'+C.REPO+'/contents/MEMORIA/'))
  old=self.store.get(key)
  self.assertEqual(d.get('sha'),O.sha(old) if old is not None else None)
  b=base64.b64decode(d['content']);self.store[key]=b;self.writes.append(key);return {'content':{'sha':O.sha(b)}}
 def test_fatos_antes_de_evidencia_e_reentrada_sem_repetir(self):
  with T.contexto_mensagem(94,'a94',PEDIDO),patch.object(C,'chamar_llm') as llm,patch.object(C,'comentar') as publicar:
   recibo=O.executar(PEDIDO);r,_=T.carregar(T.id_da_origem());n=len(self.writes);leituras=len(self.reads)
   self.assertEqual(r['estado'],'entregue_para_revisao');self.assertEqual(r['executor'],O.EXECUTOR);self.assertIn('Arquivos conferidos',recibo)
   b=self.store[r['evidencia_operacional']['arquivo']];self.assertIn(b'12.0.0',b);self.assertIn(b'6.0.2',b)
   O.executar(PEDIDO);self.assertEqual(len(self.writes),n);self.assertEqual(len(self.reads),leituras);llm.assert_not_called();publicar.assert_not_called()
 def test_revisao_preserva_registro_e_artefato_anteriores(self):
  with T.contexto_mensagem(94,'a94',PEDIDO):
   r=json.loads(T.executar(json.dumps({'acao':'criar','objetivo':'antigo','etapas':['anterior']})))
   T.executar(json.dumps({'acao':'registrar_etapa','id':r['id'],'etapa':1,'conteudo':'conteudo sem leitura real'}));old=self.store[T.caminho(r['id'])];old_art=self.store[T.arquivo_da_etapa(r['id'],1)]
   O.executar(PEDIDO);r,_=T.carregar(r['id']);archive=r['revisoes_anteriores'][0]['registro']['arquivo'];self.assertEqual(self.store[archive],old);self.assertEqual(self.store[T.arquivo_da_etapa(r['id'],1)],old_art);self.assertEqual(r['estado'],'entregue_para_revisao')
 def test_fonte_indisponivel_nao_gera_evidencia(self):
  api=self.api
  def indisponivel(m,p,d=None):
   if '/site/' in p:raise RuntimeError('HTTP 503')
   return api(m,p,d)
  with T.contexto_mensagem(94,'a94',PEDIDO),patch.object(C,'gh',side_effect=indisponivel):
   with self.assertRaises(RuntimeError):O.executar(PEDIDO)
  self.assertEqual(self.writes,[])
 def test_escopo_nao_adivinha_ou_amplia_fontes(self):
  with T.contexto_mensagem(94,'a94',PEDIDO):
   with self.assertRaises(ValueError):O.fontes_do_pedido(O.PREFIXO+' faça algo')
   with self.assertRaises(PermissionError):C._autorizar_leitura_operacional('REPO','site/../segredo')
 def test_resposta_antiga_sem_comprovacao_nao_e_aceite(self):
  antigo={'body':C.ASSINATURA+'\ntexto\n<!--resp:a94-->','user':{'login':C.DONO_GITHUB}}
  with T.contexto_mensagem(94,'a94',PEDIDO),patch.object(C,'comentarios_da_conversa_verificados',return_value=[antigo]):self.assertFalse(R.ja_respondida(94,'a94'))
  novo=dict(antigo,body=antigo['body']+'\n'+O.marcador('a94'))
  with T.contexto_mensagem(94,'a94',PEDIDO),patch.object(C,'comentarios_da_conversa_verificados',return_value=[novo]):self.assertTrue(R.ja_respondida(94,'a94'))
 def test_varredura_retoma_entrega_antiga_invalida_sem_apagar(self):
  i={'number':94,'body':PEDIDO,'user':{'login':C.DONO_GITHUB}};c={'body':C.ASSINATURA+'\ntexto\n<!--resp:a94-->','user':{'login':C.DONO_GITHUB}}
  def gh(m,p):return [c] if '/comments?' in p else [i]
  with patch.object(C,'gh',side_effect=gh):self.assertEqual(V.pendentes(),[(i,None)])
  c['body']+='\n'+O.marcador('a94')
  with patch.object(C,'gh',side_effect=gh):self.assertEqual(V.pendentes(),[])
 def test_rota_restrita_antecede_avisos_e_modelos(self):
  dados={'numero':94,'marca':'a94','texto':PEDIDO,'origem':'nova conversa'}
  with T.contexto_mensagem(94,'a94',PEDIDO),patch.object(R,'ja_respondida',side_effect=[False,False,True]),patch.object(O,'executar',return_value='recibo'),patch.object(R,'responder'),patch.object(C,'fila_respostas_carregar',return_value=[]),patch.object(C,'checar_avisos') as avisos,patch.object(C,'responder_com_ferramentas') as modelo:
   self.assertEqual(R._principal_com_origem(dados),0);avisos.assert_not_called();modelo.assert_not_called()
if __name__=='__main__':unittest.main()
