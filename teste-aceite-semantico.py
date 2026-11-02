import unittest,json,copy,base64,pathlib,tempfile,subprocess,sys,os,importlib.util
from unittest.mock import patch
import aceite_semantico as S,execucao_isolada as E,autonomia_reversivel as A,comum as C,trabalhos as T
FS={'main.py':'def contar(xs):return {"total":len(xs)}\n','test_main.py':'import unittest\nclass Test(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n'}
CON={'etapas':['Contar itens e preservar entrada'],'casos':[{'etapa':1,'modulo':'main','funcao':'contar','args':[[]],'esperado':{'total':0},'nao_muta':True}]}
class Aceite(unittest.TestCase):
 def test_campos_de_autoridade_e_modulos_externos_rejeitados(self):
  for change in [{'workflow':'roubar'}, {'shell':'x'}, {'repo':'x'}]:
   with self.assertRaises(ValueError):S.validar(dict(CON,**change),FS)
  for mod in ['os','../main','test_main','main.x']:
   v=copy.deepcopy(CON);v['casos'][0]['modulo']=mod
   with self.assertRaises(ValueError):S.validar(v,FS)
 def test_todas_subtarefas_precisam_cobertura(self):
  v=copy.deepcopy(CON);v['etapas'].append('Outra tarefa')
  with self.assertRaises(ValueError):S.validar(v,FS)
 def test_nao_envia_expectativas_ao_codigo(self):
  self.assertEqual(set(S.chamadas(CON)[0]),{'modulo','funcao','args'})
  self.assertNotIn('esperado',S.harness(CON));self.assertNotIn('nao_muta',S.harness(CON))
 def test_comparador_rejeita_exatamente_bug_vazio_anterior(self):
  r=S.comparar(CON,[{'retorno':{},'args_depois':[[]],'kwargs_depois':{}}]);self.assertFalse(r['sucesso'])
  r=S.comparar(CON,[{'retorno':{'total':0},'args_depois':[[]],'kwargs_depois':{}}]);self.assertTrue(r['sucesso'])
 def test_rejeita_mutacao_excecao_ausente_e_tipos_diferentes(self):
  self.assertFalse(S.comparar(CON,[{'retorno':{'total':False},'args_depois':[[]],'kwargs_depois':{}}])['sucesso'])
  self.assertFalse(S.comparar(CON,[{'retorno':{'total':0},'args_depois':[['alterado']],'kwargs_depois':{}}])['sucesso'])
  v=copy.deepcopy(CON);v['casos'][0].pop('esperado');v['casos'][0]['erro']='ValueError'
  self.assertTrue(S.comparar(v,[{'erro':'ValueError','args_depois':[[]],'kwargs_depois':{}}])['sucesso'])
  self.assertFalse(S.comparar(v,[{'retorno':None,'args_depois':[[]],'kwargs_depois':{}}])['sucesso'])
 def test_sucesso_de_unittest_nao_substitui_aceite(self):
  with patch.object(E,'_container',side_effect=[{'sucesso':True,'testes':1,'detalhes':'ok'},{'sucesso':True,'testes':1,'detalhes':'ok','observacoes':[{'retorno':{},'args_depois':[[]],'kwargs_depois':{}}]}]) as run:
   r=E.executar(FS,CON);self.assertFalse(r['sucesso']);self.assertEqual(r['aceite_sha256'],S.digest(CON));self.assertEqual(run.call_count,2)
 def test_passagem_de_aceite_observada(self):
  with patch.object(E,'_container',side_effect=[{'sucesso':True,'testes':1,'detalhes':'ok'},{'sucesso':True,'testes':1,'detalhes':'ok','observacoes':[{'retorno':{'total':0},'args_depois':[[]],'kwargs_depois':{}}]}]):
   r=E.executar(FS,CON);self.assertTrue(r['sucesso']);self.assertEqual(r['aceite']['casos'],1)
 def test_falha_do_container_ou_falta_de_observacoes_fecham(self):
  for raw in [{'sucesso':False,'testes':0,'detalhes':'timeout'},{'sucesso':True,'testes':99,'detalhes':'resultado forjado sem observações'}]:
   with patch.object(E,'_container',side_effect=[{'sucesso':True,'testes':1,'detalhes':'ok'},raw]):self.assertFalse(E.executar(FS,CON)['sucesso'])
 def test_ci_recibo_sem_hash_do_contrato_nao_aprova(self):
  with patch.object(A,'ler',return_value=({'head':'a'*40,'run_id':1,'sucesso':True},'x')),patch.object(C,'gh') as gh:
   with self.assertRaises(A.Revisao):A.ci_observavel({'id':'b'*32,'head':'a'*40,'aceite':CON,'aceite_sha256':S.digest(CON)})
   gh.assert_not_called()
 def test_ci_sem_casos_apesar_hash_correto_nao_aprova(self):
  ci={'head':'a'*40,'run_id':1,'sucesso':True,'aceite_sha256':S.digest(CON)}
  with patch.object(A,'ler',return_value=(ci,'x')),patch.object(C,'gh') as gh:
   with self.assertRaises(A.Revisao):A.ci_observavel({'id':'b'*32,'head':'a'*40,'aceite':CON,'aceite_sha256':S.digest(CON)})
   gh.assert_not_called()
 def test_harness_apenas_com_fixture_confiavel_nao_codigo_de_modelo(self):
  # Fixture estática desta suíte. NÃO constitui fallback do executor de produção.
  for fonte,ok in [(FS['main.py'],True),('def contar(xs):return {}\n',False)]:
   with tempfile.TemporaryDirectory() as td:
    pathlib.Path(td,'main.py').write_text(fonte);h=S.harness(CON).replace('/projeto',td);r=subprocess.run([sys.executable,'-c',h],capture_output=True,text=True,timeout=5,env={'PATH':os.environ['PATH']});self.assertEqual(r.returncode,0);v=json.loads(r.stdout.split('RESULTADO_CI:')[1]);self.assertEqual(S.comparar(CON,v['observacoes'])['sucesso'],ok)
 def test_cli_sem_shell_com_saida_e_exit_observados(self):
  fs={'app.py':'import sys\nprint(sys.stdin.read().upper(),end="")\n','test_app.py':FS['test_main.py']};v={'etapas':['Converter entrada'],'casos':[{'etapa':1,'script':'app.py','args':[],'entrada':'ola','esperado':'OLA','codigo':0}]};S.validar(v,fs)
  self.assertNotIn('esperado',S.harness(v))
  with tempfile.TemporaryDirectory() as td:
   pathlib.Path(td,'app.py').write_text(fs['app.py']);h=S.harness(v).replace('/projeto',td);r=subprocess.run([sys.executable,'-c',h],capture_output=True,text=True,timeout=5);self.assertEqual(r.returncode,0);raw=json.loads(r.stdout.split('RESULTADO_CI:')[1]);self.assertTrue(S.comparar(v,raw['observacoes'])['sucesso']);raw['observacoes'][0]['codigo']=1;self.assertFalse(S.comparar(v,raw['observacoes'])['sucesso'])
 def test_cli_nao_escolhe_interpretador_shell_ou_arquivo_externo(self):
  v={'etapas':['Converter entrada'],'casos':[{'etapa':1,'script':'../../etc/passwd','esperado':'x'}]}
  with self.assertRaises(ValueError):S.validar(v,FS)
  v['casos'][0]={'etapa':1,'script':'main.py','esperado':'x','shell':'bash'}
  with self.assertRaises(ValueError):S.validar(v,FS)
 def test_marcadores_no_dado_nao_sao_template(self):
  v=copy.deepcopy(CON);v['casos'][0]['args']=[['FUNCAO','PAYLOAD']]
  tree=__import__('ast').parse(S.harness(v));assign=next(n for n in tree.body if isinstance(n,__import__('ast').Assign));self.assertEqual(json.loads(assign.value.args[0].value),S.chamadas(v))
 def test_erro_de_importacao_ou_serializacao_nao_e_excecao_da_funcao(self):
  v=copy.deepcopy(CON);v['casos'][0].pop('esperado');v['casos'][0]['erro']='ValueError'
  for src in ['raise ValueError("importacao")\ndef contar(xs):return 0\n','def contar(xs):return float("nan")\n','def contar(xs):raise ValueError("entrada")\n']:
   with tempfile.TemporaryDirectory() as td:
    pathlib.Path(td,'main.py').write_text(src);r=subprocess.run([sys.executable,'-c',S.harness(v).replace('/projeto',td)],capture_output=True,text=True,timeout=5);raw=json.loads(r.stdout.split('RESULTADO_CI:')[1]);self.assertEqual(S.comparar(v,raw['observacoes'])['sucesso'],'raise ValueError("entrada")' in src)
 def test_interface_para_revisor_nao_inclui_corpos_docstrings_ou_testes(self):
  fs={'main.py':'def contar(xs):\n "segredo_de_corpo"\n return {"total":999}\n','test_main.py':FS['test_main.py']};data=json.dumps(S.interfaces(fs));self.assertIn('contar',data);self.assertNotIn('999',data);self.assertNotIn('segredo_de_corpo',data);self.assertNotIn('test_main',data);self.assertIn('xs',data)
 def test_atualizar_reconhecido(self):
  self.assertTrue(A.eh_objetivo('Atualize projeto '+'a'*32));self.assertTrue(A.eh_objetivo('Atualizar projeto '+'a'*32))
 def test_teto_de_chamadas_preservado(self):
  with patch.object(A,'politica',return_value={}),patch.object(A,'salvar') as save,patch.object(C,'chamar_llm') as llm:
   with self.assertRaises(A.Revisao):A.modelo_json({'chamadas_modelo':3},'x')
   llm.assert_not_called();save.assert_not_called()
# Fixture de API privada compartilhada; nenhuma rede ou chamada de modelo real.
spec=importlib.util.spec_from_file_location('fixture_fluxo_aceite',pathlib.Path(__file__).with_name('teste-autonomia-reversivel.py'));F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
REAL_PREPARAR=A.preparar_aceite
CON_SOMA={'etapas':['Somar inteiros'],'casos':[{'etapa':1,'modulo':'main','funcao':'somar','args':[2,3],'esperado':5,'nao_muta':True}]}
class Fluxo(unittest.TestCase):
 setUp=F.Autonomia.setUp
 api=F.Autonomia.api
 def state(self):return {'id':T.id_da_origem(),'origem':T._ORIGEM.get(),'pedido_sha256':__import__('hashlib').sha256(self.goal.encode()).hexdigest(),'versao':2,'fase':'planejado','plano':copy.deepcopy(F.PLAN),'chamadas_modelo':1}
 def test_revisor_recebe_original_congela_e_nao_reexecuta_na_retomada(self):
  def preparar(s,pedido,p):s.update(fase='pr_criada',head='a'*40,pr=7,pr_url='https://example.test/pr/7',prefixo_projeto='PROJETOS/'+s['id']+'/',arquivos_sha={'main.py':'x'});A.salvar(s)
  def dispatch(s):s['fase']='ci_aguardando';A.salvar(s)
  with T.contexto_mensagem(123,'a123',self.goal),patch.object(C,'chamar_llm',return_value=(json.dumps(CON_SOMA),'revisor-fixture',None)) as llm:
   state=self.state();REAL_PREPARAR(state,self.goal);self.assertEqual(state['chamadas_modelo'],2);self.assertEqual(state['aceite_sha256'],S.digest(CON_SOMA));self.assertIn(self.goal,llm.call_args.args[0][0]['content']);self.assertNotIn('def somar',llm.call_args.args[0][0]['content']);self.assertNotIn('self.assertEqual',llm.call_args.args[0][0]['content']);self.assertEqual(state['subtarefas'][0]['estado'],'aguarda_execucao')
   self.review.stop()
   with patch.object(A,'preparar_pr',side_effect=preparar),patch.object(A,'despachar_ci',side_effect=dispatch),patch.object(A,'integrar',side_effect=A.Aguardar('CI em andamento')):
    for _ in range(2):
     with self.assertRaises(A.Aguardar):A.executar(self.goal)
   self.assertEqual(llm.call_count,1)
 def test_revisor_invalido_tenta_corrigir_so_o_esquema_sem_abrir_pr(self):
  with T.contexto_mensagem(123,'a123',self.goal),patch.object(C,'chamar_llm',return_value=(json.dumps({'shell':'x'}),'fixture',None)),patch.object(A,'preparar_pr') as pr:
   state=self.state()
   with self.assertRaises(A.Revisao):REAL_PREPARAR(state,self.goal)
   self.assertEqual(state['chamadas_modelo'],3);pr.assert_not_called();self.assertNotIn('aceite',state)
 def test_reparo_usa_falha_real_mantem_contrato_e_testes(self):
  old_api=C.gh
  def api(m,path,d=None):
   if m=='POST' and path.endswith('/git/blobs'):return {'sha':A.sha(base64.b64decode(d['content']))}
   if m=='GET' and '/git/commits/' in path:return {'tree':{'sha':'treeold'}}
   if m=='POST' and path.endswith('/git/trees'):return {'sha':'treenew'}
   if m=='POST' and path.endswith('/git/commits'):return {'sha':'b'*40}
   if m=='PATCH' and '/git/refs/' in path:self.assertFalse(d['force']);return {}
   return old_api(m,path,d)
  with T.contexto_mensagem(123,'a123',self.goal),patch.object(C,'gh',side_effect=api),patch.object(C,'chamar_llm',return_value=(json.dumps({'arquivos':F.FILES}),'reparo-fixture',None)) as llm,patch.object(A,'conferir_pr',return_value={}):
   state=self.state();state.update(chamadas_modelo=2,head='a'*40,branch='autonomia/'+state['id'],prefixo_projeto='PROJETOS/'+state['id']+'/',arquivos_sha={},aceite=copy.deepcopy(CON_SOMA),aceite_sha256=S.digest(CON_SOMA));A.reparar(state,{'detalhes':'caso1: esperado5 observado0'})
   self.assertEqual(state['chamadas_modelo'],3);self.assertEqual(state['reparos'],1);self.assertEqual(state['aceite'],CON_SOMA);self.assertEqual(state['plano']['arquivos']['test_main.py'],F.FILES['test_main.py']);self.assertIn('caso1',llm.call_args.args[0][0]['content']);self.assertIn('Contrato de aceite congelado',llm.call_args.args[0][0]['content'])
if __name__=='__main__':unittest.main()
