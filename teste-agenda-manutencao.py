import unittest,json,copy,datetime,os
from unittest.mock import patch
import agenda_manutencao as M,autonomia_reversivel as A,comum as C
REAL_POLITICA=M.politica
class Agenda(unittest.TestCase):
 def setUp(self):
  self.now=1800000000.;self.p={'versao':1,'aprovacao':'dono-manutencao-privada-r0-v1','dono':C.DONO_GITHUB,'repo_privado':C.REPO,'orcamento_reais':0,'publicacoes':'somente_codigo_tecnico_aprovado','ativo':True,'worker_sha':'a'*40,'iniciar_apos':self.now-100};self.store=None;self.sha=None;self.runs=[];self.issues=[];self.comments=[];self.effects=[];self.writes=0
  def ler(repo,path):
   if path==M.ESTADO:return copy.deepcopy(self.store),self.sha
   raise AssertionError(path)
  def gravar(repo,path,v,old=None):
   self.assertEqual(path,M.ESTADO);self.assertEqual(old,self.sha);self.store=json.loads(json.dumps(v));self.sha='s'+str(self.writes);self.writes+=1;return self.sha
  for target,name,kw in [(M,'politica',{'return_value':self.p}),(A,'politica',{'return_value':{}}),(A,'garantir_workflows',{'return_value':{}}),(A,'ler',{'side_effect':ler}),(A,'gravar',{'side_effect':gravar}),(M.time,'time',{'side_effect':lambda:self.now}),(C,'gh',{'side_effect':self.api}),(C,'chamar_llm',{'side_effect':AssertionError('modelo proibido na agenda')})]:
   p=patch.object(target,name,**kw);p.start();self.addCleanup(p.stop)
 def api(self,m,path,d=None):
  if m=='GET' and path.endswith('/git/ref/heads/main'):return {'object':{'sha':self.p['worker_sha']}}
  if m=='GET' and '/actions/runs?' in path:return {'workflow_runs':copy.deepcopy(self.runs)}
  if m=='GET' and '/issues?state=all' in path:return copy.deepcopy(self.issues)
  if m=='GET' and '/comments?' in path:return copy.deepcopy(self.comments)
  if m=='POST':
   self.effects.append((path,d))
   if path.endswith('/issues'):
    v={'number':123,'body':d['body'],'user':{'login':C.DONO_GITHUB}};self.issues.append(v);return v
   if path.endswith('/comments'):
    v={'id':len(self.comments)+1,'body':d['body'],'user':{'login':C.DONO_GITHUB}};self.comments.append(v);return v
   if path.endswith('/dispatches') or path.endswith('/rerun-failed-jobs'):return None
  raise AssertionError((m,path))
 def runmeta(self,**kw):
  return dict({'id':999,'event':'workflow_dispatch','head_sha':'a'*40,'actor':{'login':C.DONO_GITHUB},'path':M.TESTES,'created_at':datetime.datetime.fromtimestamp(self.now,datetime.timezone.utc).isoformat(),'status':'completed','conclusion':'success','run_attempt':1},**kw)
 def test_sem_ordem_pontual_seleciona_verificacao_privada_e_fixa_workflow(self):
  self.assertEqual(M.executar()['acao'],'verificar');self.assertEqual(self.store['usados'],1);self.assertTrue(self.issues[0]['body'].startswith('🤖'));self.assertEqual(sum('/actions/workflows/testes.yml/dispatches' in x[0] for x in self.effects),1)
  self.assertTrue(all('/repos/'+C.REPO+'/' in path or '/repos/'+C.REPO_ROBO+'/actions/' in path for path,d in self.effects))
 def test_reentrada_aguardando_nao_repete_post_ou_modelo(self):
  M.executar();n=len(self.effects);w=self.writes;self.assertTrue(M.executar()['aguardando']);self.assertEqual(len(self.effects),n);self.assertEqual(self.writes,w)
 def test_resultado_evidenciado_depois_noop_ate_24h(self):
  M.executar();self.runs=[self.runmeta()];self.assertEqual(M.executar()['observado'],999);n=len(self.effects);w=self.writes;self.assertTrue(M.executar()['sem_acao']);self.assertEqual(len(self.effects),n);self.assertEqual(self.writes,w)
 def test_ci_falhada_tem_prioridade_e_orcamento_max2(self):
  M.executar();self.runs=[self.runmeta(conclusion='failure')];M.executar();self.assertEqual(M.executar()['acao'],'retomar');self.assertEqual(self.store['usados'],2);n=len(self.effects);M.executar();self.assertEqual(len(self.effects),n)
  self.runs=[self.runmeta(conclusion='failure',run_attempt=2)];M.executar();self.assertTrue(M.executar()['orcamento_esgotado']);self.assertEqual(sum('/rerun-failed-jobs' in x[0] for x in self.effects),1)
 def test_run_antigo_estranho_outro_sha_cancelado_nao_reexecuta(self):
  for kw in [{'created_at':'2020-01-01T00:00:00Z'},{'actor':{'login':'estranho'}},{'head_sha':'b'*40},{'conclusion':'cancelled'},{'run_attempt':3},{'path':'.github/workflows/marketing.yml'}]:
   self.assertFalse(M.seguro_retomar(self.runmeta(**dict({'conclusion':'failure'},**kw)),self.p))
 def test_ativacao_nao_reabre_historicos(self):
  self.runs=[self.runmeta(conclusion='failure',created_at='2020-01-01T00:00:00Z')];M.executar();self.assertFalse(any('/rerun-failed-jobs' in x[0] for x in self.effects))
 def test_pausa_antes_de_efeitos(self):
  with patch.object(M,'politica',side_effect=A.Aguardar('pausado')):
   with self.assertRaises(A.Aguardar):M.executar()
  self.assertFalse(self.effects);self.assertEqual(self.writes,0)
 def test_pin_e_orcamento_reais_sao_guardas(self):
  for mod in [{'worker_sha':'b'*40},{'orcamento_reais':10},{'publicacoes':'tudo'}]:
   p=dict(self.p,**mod)
   with patch.object(A,'ler',return_value=(p,'x')),patch.dict(os.environ,{'GITHUB_SHA':'a'*40}):
    with self.assertRaises(A.Revisao):REAL_POLITICA()
 def test_envio_incerto_nao_e_repetido(self):
  old=self.api
  def api(m,path,d=None):
   if m=='POST' and path.endswith('/actions/workflows/testes.yml/dispatches'):raise RuntimeError('HTTP 503')
   return old(m,path,d)
  with patch.object(C,'gh',side_effect=api):
   with self.assertRaises(RuntimeError):M.executar()
  self.assertEqual(self.store['usados'],1);n=len(self.effects);M.executar();self.assertEqual(len(self.effects),n)
 def test_correlacao_ambigua_nao_inventa_execucao(self):
  M.executar();self.runs=[self.runmeta(),self.runmeta(id=1000)]
  with self.assertRaises(A.Revisao):M.executar()
 def test_ci_codigo_falho_nao_e_repetida_pela_agenda(self):
  r=self.runmeta(path=M.CI,conclusion='failure',display_title='Projeto '+'c'*32);st={'fase':'ci_aguardando','dispatch_em':self.now-10,'head':'d'*40}
  with patch.object(A,'ler',side_effect=[(st,'x'),({'sucesso':False,'run_id':999},'y')]),patch.object(A,'conferir_pr'):self.assertFalse(M.seguro_retomar(r,self.p))
 def test_ci_sem_recibo_tem_retomada_controlada(self):
  r=self.runmeta(path=M.CI,conclusion='failure',display_title='Projeto '+'c'*32);st={'fase':'ci_aguardando','dispatch_em':self.now-10,'head':'d'*40}
  with patch.object(A,'ler',side_effect=[(st,'x'),(None,None)]),patch.object(A,'conferir_pr'):self.assertTrue(M.seguro_retomar(r,self.p))
 def test_main_mudou_antes_de_efeitos_interrompe(self):
  old=self.api
  def api(m,path,d=None):
   if path.endswith('/git/ref/heads/main'):return {'object':{'sha':'b'*40}}
   return old(m,path,d)
  with patch.object(C,'gh',side_effect=api):
   with self.assertRaises(A.Revisao):M.executar()
  self.assertFalse(self.effects);self.assertEqual(self.writes,0)
 def test_politica_mudou_antes_do_efeito_interrompe(self):
  with patch.object(M,'politica',side_effect=[self.p,dict(self.p,ativo=False)]):
   with self.assertRaises(A.Revisao):M.executar()
  self.assertFalse(self.effects)
 def pendente(self,segundos=3600,evento=False,chave='verificar-2026-11-03-6bbe61da033d'):
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-03','usados':1,'ultima_verificacao':self.now,'pendente':{'chave':chave,'tipo':'verificar','em':self.now-segundos,'run':None,'attempt':1}}
  if evento:self.store['eventos']['incerto-'+chave]='enviado'
  self.sha='s0'
 def test_pendente_orfao_de_pin_antigo_e_encerrado_em_vez_de_travar(self):
  # Medido em 04/11/2026: re-apontado o pin, o pendente do pin antigo nunca mais casa com
  # `permitido` (head_sha diferente) e a agenda respondia "aguardando" para sempre.
  self.pendente(evento=True);n=len(self.effects);w=self.writes
  r=M.executar();self.assertIn('incerto_encerrado',r);self.assertIsNone(self.store['pendente'])
  self.assertEqual(len(self.effects),n)
  self.assertEqual(sum('/dispatches' in x[0] or '/rerun-failed-jobs' in x[0] for x in self.effects),0)
  self.assertGreater(self.writes,w)
 def test_pendente_vencido_registra_incerto_uma_vez_e_encerra(self):
  self.pendente();M.executar()
  self.assertEqual(sum('/comments' in x[0] for x in self.effects),1)
  self.assertIsNone(self.store['pendente']);self.assertEqual(self.store['eventos']['incerto-verificar-2026-11-03-6bbe61da033d'],'enviado')
  self.assertEqual(sum('/dispatches' in x[0] or '/rerun-failed-jobs' in x[0] for x in self.effects),0)
  n=len(self.effects);M.executar();self.assertEqual(sum('/comments' in x[0] for x in self.effects),1);self.assertLessEqual(len(self.effects),n+1)
 def test_pendente_recente_ainda_espera_sem_encerrar(self):
  self.pendente(segundos=60);n=len(self.effects)
  self.assertTrue(M.executar()['aguardando']);self.assertIsNotNone(self.store['pendente']);self.assertEqual(len(self.effects),n)
 def test_encerrada_a_pendencia_a_agenda_volta_a_escolher_prioridade(self):
  self.pendente(evento=True);M.executar()
  self.runs=[self.runmeta(conclusion='failure')];self.assertEqual(M.executar()['acao'],'retomar')
 def test_pendente_e_conferido_no_worker_que_o_despachou_nao_no_pin_novo(self):
  # Medido em 04/11: cada merge em main move o pin, e a execucao despachada antes disso nunca
  # mais casava com permitido() - o resultado virava "incerto" no diario do dono sem ser.
  antigo='f'*40
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-04','usados':1,'ultima_verificacao':self.now,
              'pendente':{'chave':'verificar-2026-11-04-abcd','tipo':'verificar','em':self.now-60,'run':None,'attempt':1,'worker_sha':antigo}}
  self.sha='s0'
  self.runs=[self.runmeta(id=1234,head_sha=antigo,created_at=datetime.datetime.fromtimestamp(self.now-30,datetime.timezone.utc).isoformat())]
  r=M.executar()
  self.assertEqual(r.get('observado'),1234);self.assertIsNone(self.store['pendente'])
  self.assertEqual(self.store['eventos'].get('resultado-verificar-2026-11-04-abcd'),'enviado')
 def test_pendente_nao_casa_execucao_de_outro_sha(self):
  antigo='f'*40
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-04','usados':1,'ultima_verificacao':self.now,
              'pendente':{'chave':'verificar-2026-11-04-abcd','tipo':'verificar','em':self.now-60,'run':None,'attempt':1,'worker_sha':antigo}}
  self.sha='s0'
  self.runs=[self.runmeta(id=1234,head_sha='e'*40,created_at=datetime.datetime.fromtimestamp(self.now-30,datetime.timezone.utc).isoformat())]
  self.assertTrue(M.executar().get('aguardando'));self.assertIsNotNone(self.store['pendente'])
 def test_pendente_legado_sem_worker_cai_no_pin_atual(self):
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-04','usados':1,'ultima_verificacao':self.now,
              'pendente':{'chave':'verificar-2026-11-04-abcd','tipo':'verificar','em':self.now-60,'run':None,'attempt':1}}
  self.sha='s0'
  self.runs=[self.runmeta(id=1234,head_sha='f'*40,created_at=datetime.datetime.fromtimestamp(self.now-30,datetime.timezone.utc).isoformat())]
  self.assertTrue(M.executar().get('aguardando'));self.assertIsNotNone(self.store['pendente'])
 def test_pendente_legado_deriva_o_worker_da_propria_chave(self):
  # Estado real de 04/11: pendente verificar-2026-11-04-43abfdda995e gravado antes do contrato
  # novo, sem worker_sha. A execucao despachada (head 43abfdda...) precisa ser reconhecida.
  cheio='43abfdda995e' + 'a'*28
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-04','usados':1,'ultima_verificacao':self.now,
              'pendente':{'chave':'verificar-2026-11-04-43abfdda995e','tipo':'verificar','em':self.now-60,'run':None,'attempt':1}}
  self.sha='s0'
  self.runs=[self.runmeta(id=1234,head_sha=cheio,created_at=datetime.datetime.fromtimestamp(self.now-30,datetime.timezone.utc).isoformat())]
  r=M.executar();self.assertEqual(r.get('observado'),1234);self.assertIsNone(self.store['pendente'])
  self.assertEqual(self.store['eventos'].get('resultado-verificar-2026-11-04-43abfdda995e'),'enviado')
 def test_pendente_legado_ambiguo_nao_escolhe_worker_no_chute(self):
  self.store={'versao':1,'acoes':{},'eventos':{},'diario':116,'dia':'2026-11-04','usados':1,'ultima_verificacao':self.now,
              'pendente':{'chave':'verificar-2026-11-04-43abfdda995e','tipo':'verificar','em':self.now-60,'run':None,'attempt':1}}
  self.sha='s0'
  self.runs=[self.runmeta(id=1,head_sha='43abfdda995e'+'a'*28),self.runmeta(id=2,head_sha='43abfdda995e'+'b'*28)]
  # Sem worker único, não escolhe no chute: apenas espera e deixa o prazo de 30 min decidir.
  self.assertTrue(M.executar().get('aguardando'))
  self.assertIsNotNone(self.store['pendente'])
  self.assertNotIn('resultado-verificar-2026-11-04-43abfdda995e', self.store['eventos'])
if __name__=='__main__':unittest.main()
