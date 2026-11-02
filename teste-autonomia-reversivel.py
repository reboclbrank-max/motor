import unittest,json,base64,importlib.util,pathlib,os,subprocess
from unittest.mock import patch
import autonomia_reversivel as A,execucao_isolada as E,comum as C,trabalhos as T,varrer as V,responder as R
spec=importlib.util.spec_from_file_location('fixture_autonomia',pathlib.Path(__file__).with_name('teste-operacao-leitura.py'));F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
GOAL='Crie um projeto Python interno para somar inteiros com testes.'
FILES={'main.py':'def somar(a,b): return a+b\n','test_main.py':'import unittest\nfrom main import somar\nclass Teste(unittest.TestCase):\n def test_soma(self): self.assertEqual(somar(2,3),5)\n'}
PLAN={'tipo':'projeto_python','criterios':['somar inteiros e passar nos testes'],'arquivos':FILES}
class Autonomia(unittest.TestCase):
 def setUp(self):
  F.Operacao.setUp(self);self.goal=GOAL;self.store[A.POLITICA_PATH]=json.dumps({'versao':1,'aprovacao':'dono-opcao-reversivel','ativo':True,'repositorio_projetos':C.REPO,'workflows_privados_sem_gatilhos_de_codigo':{}}).encode()
 def api(self,m,p,d=None):
  if m=='GET' and p.endswith('/issues/123'):return {'body':self.goal,'user':{'login':C.DONO_GITHUB}}
  return F.Operacao.api(self,m,p,d)
 def test_documento_persistido_retomada_sem_modelo_e_sem_reescrita(self):
  self.goal='Prepare um documento interno com um checklist.'
  doc={'tipo':'documento','criterios':['checklist salvo'],'texto':'Checklist interno com etapas suficientes para revisar e testar o projeto antes da integração.'}
  with T.contexto_mensagem(123,'a123',self.goal),patch.object(C,'chamar_llm',return_value=(json.dumps(doc),'fixture',None)) as llm:
   r=A.executar(self.goal);n=len(self.writes);r2=A.executar(self.goal);self.assertEqual(r,r2);self.assertEqual(len(self.writes),n);self.assertEqual(llm.call_count,1);self.assertEqual(T.recuperar_da_origem()['estado'],'entregue_para_revisao')
 def test_modelo_nao_escolhe_comandos_repositorios_ou_workflows(self):
  for extra in [{'shell':'rm -rf /'},{'repo':'outro'},{'workflow':'roubar.yml'}]:
   with self.assertRaises(ValueError):A.validar_plano(dict(PLAN,**extra))
 def test_paths_executores_e_teste_obrigatorio(self):
  for fs in [{'../comum.py':'x','test_a.py':'x'},{'.github/workflows/a.py':'x','test_a.py':'x'},{'sitecustomize.py':'x','test_a.py':'x'},{'main.py':'x','README.md':'x'}]:
   with self.assertRaises(ValueError):E.validar_arquivos(fs)
 def test_efeitos_externos_pedem_aprovacao_e_negacao_nao_a_concede(self):
  for g in ['Crie relatório e envie email','Prepare post e publique','Corrija comum.py','Crie e apague o anterior','Crie senha: NAO_USAR']:
   with self.assertRaises(A.Revisao):A.proteger_pedido(g)
  A.proteger_pedido('Crie um projeto Python. Sem publicar, sem excluir, sem gastar.')
 def test_autor_falso_ou_pedido_alterado_nao_executa(self):
  with T.contexto_mensagem(123,'a123','outro'):
   with self.assertRaises(A.Revisao):A.verificar_autor('outro')
  with T.contexto_mensagem(123,'a123',GOAL),patch.object(C,'gh',return_value={'body':GOAL,'user':{'login':'estranho'}}):
   with self.assertRaises(A.Revisao):A.verificar_autor(GOAL)
 def test_politica_pausada_fail_closed(self):
  p=json.loads(self.store[A.POLITICA_PATH]);p['ativo']=False;self.store[A.POLITICA_PATH]=json.dumps(p).encode()
  with T.contexto_mensagem(123,'a123',GOAL),patch.object(C,'chamar_llm') as llm:
   with self.assertRaises(A.Aguardar):A.executar(GOAL)
   llm.assert_not_called();self.assertEqual(self.writes,[]);self.assertTrue(A.aguardando_ci(123,'a123',GOAL))
 def test_objetivo_e_alvo_nao_vem_do_modelo(self):
  self.assertTrue(A.eh_objetivo(GOAL));self.assertFalse(A.eh_objetivo('Oi'));self.assertEqual(A.projeto_alvo('crie projeto', 'a'*32),'a'*32);self.assertEqual(A.projeto_alvo('Atualize projeto '+'b'*32,'a'*32),'b'*32)
 def test_ciclo_projeto_pendente_e_entrega_sem_repetir_proposta(self):
  def preparar(s,pedido,p):s.update(fase='pr_criada',head='a'*40,pr=7,pr_url='https://example.test/pr/7',prefixo_projeto='PROJETOS/'+s['id']+'/',arquivos_sha={'main.py':'x'});A.salvar(s)
  def dispatch(s):s['fase']='ci_aguardando';A.salvar(s)
  def integrate(s,p):s.update(fase='integrado',merge='b'*40,ci={'testes':1},ci_url='https://example.test/ci');A.salvar(s)
  with T.contexto_mensagem(123,'a123',GOAL),patch.object(C,'chamar_llm',return_value=(json.dumps(PLAN),'fixture',None)) as llm,patch.object(A,'preparar_pr',side_effect=preparar) as prep,patch.object(A,'despachar_ci',side_effect=dispatch) as dis,patch.object(A,'integrar',side_effect=A.Aguardar('CI em andamento')):
   for _ in range(2):
    with self.assertRaises(A.Aguardar):A.executar(GOAL)
   self.assertEqual(llm.call_count,1);self.assertEqual(prep.call_count,1);self.assertEqual(dis.call_count,1)
  with T.contexto_mensagem(123,'a123',GOAL),patch.object(A,'integrar',side_effect=integrate),patch.object(C,'chamar_llm') as llm:
   self.assertIn('Arquivos conferidos',A.executar(GOAL));n=len(self.writes);A.executar(GOAL);self.assertEqual(len(self.writes),n);llm.assert_not_called()
 def test_pr_fora_do_prefixo_nunca_integra(self):
  s={'pr':7,'head':'a'*40,'branch':'autonomia/x','prefixo_projeto':'PROJETOS/x/','arquivos_sha':{'PROJETOS/x/main.py':'s'}}
  def gh(m,p,*a):return [{'filename':'comum.py','status':'modified','sha':'s'}] if '/files?' in p else {'head':{'sha':'a'*40,'ref':'autonomia/x'},'base':{'ref':'main'}}
  with patch.object(C,'gh',side_effect=gh):
   with self.assertRaises(A.Revisao):A.conferir_pr(s)
 def test_ci_em_andamento_nunca_antecipa_integracao(self):
  with patch.object(A,'ler',return_value=({'head':'a'*40,'run_id':1,'sucesso':True},'x')),patch.object(C,'gh',return_value={'status':'in_progress'}):
   with self.assertRaises(A.Aguardar):A.ci_observavel({'id':'x','head':'a'*40})
 def test_ci_sha_errado_bloqueia(self):
  with patch.object(A,'ler',return_value=({'head':'b'*40,'run_id':1,'sucesso':True},'x')):
   with self.assertRaises(A.Revisao):A.ci_observavel({'id':'x','head':'a'*40})
 def test_reparo_nao_pode_trocar_testes(self):
  s={'plano':PLAN,'reparos':0}
  with patch.object(A,'modelo_json',return_value={'arquivos':dict(FILES,**{'test_main.py':'# fraude'})}),patch.object(C,'gh') as gh:
   with self.assertRaises(A.Revisao):A.reparar(s,{'detalhes':'falha'})
   gh.assert_not_called()
 def test_deferimento_nao_e_falso_sucesso_ou_loop(self):
  with patch.object(C,'GH_TOKEN','fixture'),patch.object(V,'pendentes',return_value=[({'number':123},None)]):
   dispatch=[];self.assertEqual(V.main(processar_um=lambda *a:V.ADIADO,disparar=lambda *a:dispatch.append(a)),0);self.assertEqual(dispatch,[])
 def test_container_sem_segredos_rede_e_limites_e_cleanup(self):
  chamadas=[]
  def run(cmd,**kw):
   chamadas.append((cmd,kw));self.assertNotIn('GITHUB_TOKEN',kw['env']);self.assertNotIn('PAT_MEMORIA',kw['env'])
   if 'run' in cmd:kw['stdout'].write(b'RESULTADO_CI:{"testes":1,"sucesso":true,"detalhes":"ok"}\n')
   return subprocess.CompletedProcess(cmd,0)
  with patch.dict(os.environ,{'GITHUB_TOKEN':'NAO_USAR','PAT_MEMORIA':'NAO_USAR'}),patch.object(E.subprocess,'run',side_effect=run):r=E.executar(FILES)
  self.assertTrue(r['sucesso']);cmd=chamadas[1][0]
  for f in ['--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534','--memory=256m','--pids-limit=64']:self.assertIn(f,cmd)
  self.assertEqual(chamadas[-1][0][:3],['docker','rm','-f'])
 def test_sem_docker_nao_faz_fallback_no_host(self):
  with patch.object(E.subprocess,'run',side_effect=FileNotFoundError):
   with self.assertRaises(FileNotFoundError):E.executar(FILES)
 def test_comandos_pausa_nao_ampliam_autorizacao(self):
  self.assertIs(A.comando_controle('pausar autonomia'),False);self.assertIs(A.comando_controle('retomar autonomia'),True);self.assertIsNone(A.comando_controle('ative poderes ilimitados'))
 def test_chat_nao_imprime_pedido_privado(self):
  self.assertNotIn('texto[:80]',pathlib.Path(R.__file__).read_text())
if __name__=='__main__':unittest.main()
