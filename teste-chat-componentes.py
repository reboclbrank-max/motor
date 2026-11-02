import unittest,copy,json,os,contextlib
from unittest.mock import patch
import chat_componentes as F,autonomia_reversivel as A,comum as C,aceite_semantico as S
REAL_POLITICA=F.politica
REAL_PROTEGIDO=F.protegido
class Componentes(unittest.TestCase):
 def setUp(self):
  self.db={};self.shas={};self.writes=[];self.calls=[];self.p={'versao':1,'ativo':True,'aprovacao':'dono-autoaperfeicoamento-isolado-r0-v1','dono':C.DONO_GITHUB,'repo_privado':C.REPO,'alvo':F.ALVO,'orcamento_reais':0,'worker_sha':'a'*40,'contrato_sha256':S.digest(F.contrato())}
  def ler(repo,path):return copy.deepcopy(self.db.get(path)),self.shas.get(path)
  def gravar(repo,path,v,old=None):
   self.assertEqual(old,self.shas.get(path));self.db[path]=json.loads(json.dumps(v));self.shas[path]=str(len(self.writes));self.writes.append(path);return self.shas[path]
  def preparar(s,pedido,p):
   self.assertIn(F.ALVO,pedido);s.update(fase='pr_criada',prefixo_projeto='PROJETOS/'+F.ALVO+'/',head='b'*40,branch='autonomia/'+s['id'],arquivos_sha={'PROJETOS/'+F.ALVO+'/'+n:A.sha(t.encode()) for n,t in s['plano']['arquivos'].items()});A.salvar(s)
  def dispatch(s):s['fase']='ci_aguardando';self.calls.append('dispatch');A.salvar(s)
  for target,name,kw in [(F,'politica',{'return_value':self.p}),(F,'protegido',{'side_effect':lambda p:contextlib.nullcontext()}),(A,'ler',{'side_effect':ler}),(A,'gravar',{'side_effect':gravar}),(A,'politica',{'return_value':{}}),(A,'preparar_pr',{'side_effect':preparar}),(A,'recuperar_pr',{}),(A,'despachar_ci',{'side_effect':dispatch}),(A,'integrar',{'side_effect':A.Aguardar('CI em andamento')}),(C,'gh',{'side_effect':AssertionError('rede inesperada')}),(C,'chamar_llm',{'side_effect':AssertionError('remoto proibido')})]:
   p=patch.object(target,name,**kw);p.start();self.addCleanup(p.stop)
 def estado(self):return next(v for k,v in self.db.items() if k.endswith('/estado.json'))
 def test_sem_objetivo_pontual_audita_componente_e_congela_contrato(self):
  r=F.executar();s=self.estado();self.assertTrue(r['aguardando']);self.assertEqual(s['aceite'],F.contrato());self.assertEqual(s['chamadas_modelo'],0);self.assertEqual(self.calls,['dispatch']);self.assertEqual(set(s['plano']['arquivos']),{'formatador.py','test_api.py'})
 def test_reentrada_espera_ci_sem_repetir_dispatch(self):
  F.executar();n=len(self.writes);F.executar();self.assertEqual(self.calls,['dispatch']);self.assertEqual(len(self.writes),n)
 def test_contrato_cobre_robustez_e_nao_mutacao(self):
  c=F.contrato();S.validar(c,{'formatador.py':F.BASELINE,'test_api.py':F.TESTE});self.assertEqual(len(c['casos']),11);self.assertTrue(all(v['nao_muta'] for v in c['casos']));self.assertTrue(any('erro' in v for v in c['casos']))
 def test_referencia_preserva_fatos_escape_e_nulos(self):
  self.assertEqual(F.referencia([{}]),'- sem nome: desconhecido; SHA `não informado`; não informado');self.assertEqual(F.escapar('a [b]\nc'),'a \\[b\\] c')
  for d in [None,{},[2],[{'name':['x']}]]:
   with self.assertRaises(ValueError):F.referencia(d)
 def test_pol_aprovacao_pin_orcamento_contrato(self):
  for mod in [{'worker_sha':'b'*40},{'orcamento_reais':10},{'alvo':'outro'},{'contrato_sha256':'x'},{'aprovacao':'tudo'}]:
   with patch.object(A,'ler',return_value=(dict(self.p,**mod),'x')),patch.dict(os.environ,{'GITHUB_SHA':'a'*40}):
    with self.assertRaises(A.Revisao):REAL_POLITICA()
 def test_pausa_sem_efeito(self):
  with patch.object(F,'politica',return_value=None):self.assertEqual(F.executar(),{'ativo':False})
  self.assertFalse(self.writes)
 def test_ativacao_cas_preserva_anterior(self):
  s={'id':'id1','aceite_sha256':S.digest(F.contrato()),'head':'b'*40,'merge':'c'*40,'prefixo_projeto':'PROJETOS/'+F.ALVO+'/','arquivos_sha':{},'ci':{'run_id':7},'ativo_anterior_sha':None};v=F.ativar(s,self.p);self.assertEqual(v['versao_id'],'id1');n=len(self.writes);self.assertEqual(F.ativar(s,self.p),v);self.assertEqual(len(self.writes),n)
  with self.assertRaises(A.Revisao):F.ativar(dict(s,id='id2'),self.p)
 def test_estado_modelo_nao_pode_mudar_teste_contrato_alvo(self):
  F.executar();s=self.estado()
  for mod in [{'alvo_componente':'x'},{'aceite':{}},{'prefixo_projeto':'comum.py/'},{'plano':{'arquivos':{'formatador.py':F.BASELINE,'test_api.py':'pass'}}}]:
   with self.assertRaises((A.Revisao,ValueError)):F.verificar(dict(s,**mod),self.p)
 def test_manifesto_nao_aceita_outros_caminhos(self):
  with self.assertRaises(A.Revisao):F.arquivos({'alvo':F.ALVO,'prefixo':'.github/','contrato_sha256':S.digest(F.contrato()),'arquivos_sha':{}})
 def test_runtime_sem_token_usa_fallback_sem_executar_host(self):
  with patch.object(C,'GH_TOKEN',''),patch.object(F.E,'executar',side_effect=AssertionError('não deveria executar')):self.assertEqual(F.apresentar([{}]),F.referencia([{}]))
 def test_modelo_somente_local_nao_cadeia_remota(self):
  import motor_local
  s={'plano':{'arquivos':{'formatador.py':F.BASELINE}}};original=C.chamar_llm
  with patch.object(motor_local,'responder',return_value=('{}',None)) as local:
   with F.modelo_local(s,{'detalhes':'falha'}):self.assertEqual(C.chamar_llm([])[1],'local-isolado-sem-chave')
   local.assert_called_once();self.assertIs(C.chamar_llm,original)
 def test_runtime_rollback_cas_sem_entregar_stdout(self):
  ativo={'versao_id':'x','anterior':None};self.db[F.ATIVO]=ativo;self.shas[F.ATIVO]='v'
  with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}),patch.object(C,'GH_TOKEN','fixture'),patch.object(F,'arquivos',return_value={'formatador.py':F.BASELINE,'test_api.py':F.TESTE}),patch.object(F.E,'_container',return_value={'sucesso':False,'detalhes':'inventado'}):
   self.assertEqual(F.apresentar([{}]),F.referencia([{}]))
  self.assertTrue(self.db[F.ATIVO]['desativado']);self.assertEqual(self.db['MEMORIA/chat-componentes/falhas/x.json']['classe'],'divergencia_runtime')
 def test_reserva_checkpoint_recupera_estado_ausente_sem_dup_dispatch(self):
  F.executar();path=next(k for k in self.db if k.endswith('/estado.json'));del self.db[path];del self.shas[path];F.executar();self.assertEqual(self.estado()['aceite'],F.contrato());self.assertEqual(len(self.db[F.CONTROLE]['rodadas']),1)
 def test_ci_controlador_errado_bloqueia_sem_integrar(self):
  F.executar();st=self.estado();path=A.RAIZ+'/'+st['id']+'/ci/'+st['head']+'.json';self.db[path]={'run_id':7}
  with patch.object(C,'gh',return_value={'head_sha':'outro'}),patch.object(A,'integrar') as integrar:
   self.assertTrue(F.executar()['bloqueado']);integrar.assert_not_called()
 def test_ci_negativa_pede_reparo_mas_nao_ativa(self):
  F.executar();ci={'sucesso':False,'testes':2,'detalhes':'caso diverge'}
  def reparar(s,c):self.assertIs(c,ci);s['fase']='pr_criada';s['head']='c'*40;A.salvar(s)
  with patch.object(A,'integrar',side_effect=A.FalhaCI(ci)),patch.object(A,'reparar',side_effect=reparar):
   self.assertTrue(F.executar()['reparo_proposto'])
  self.assertNotIn(F.ATIVO,self.db);self.assertEqual(self.calls,['dispatch','dispatch'])
 def test_estado_bloqueado_nao_reseta_orcamento(self):
  F.executar();path=next(k for k in self.db if k.endswith('/estado.json'));self.db[path]['fase']='bloqueado';self.db[path]['chamadas_modelo']=3;n=len(self.writes)
  self.assertTrue(F.executar()['bloqueado']);self.assertEqual(len(self.writes),n);self.assertEqual(self.db[path]['chamadas_modelo'],3)
 def test_protecao_reavalia_cada_escrita_e_restaura_transporte(self):
  original=C.gh
  with patch.object(F,'guardar') as g,patch.object(C,'gh',return_value={'ok':True}) as transport:
   with REAL_PROTEGIDO(self.p):C.gh('GET','/read');C.gh('PUT','/write',{});C.gh('POST','/write2',{})
   self.assertEqual(g.call_count,2);self.assertIs(C.gh,transport)
  self.assertIs(C.gh,original)
 def test_revogacao_bloqueia_antes_do_post(self):
  with patch.object(F,'guardar',side_effect=A.Aguardar('pausa')),patch.object(C,'gh') as transport:
   with REAL_PROTEGIDO(self.p):
    with self.assertRaises(A.Aguardar):C.gh('POST','/proibido',{})
   transport.assert_not_called()
 def test_runtime_entrega_observacao_validada_nao_saida_inventada(self):
  d=[{}];esperado=F.referencia(d);obs=[{'retorno':esperado,'args_depois':[d],'kwargs_depois':{}}]
  with patch.object(F,'arquivos',return_value={}),patch.object(F.E,'_container',return_value={'sucesso':True,'observacoes':obs}):self.assertEqual(F.rodar_ativo({},d),esperado)
  obs[0]['retorno']='texto falso'
  with patch.object(F,'arquivos',return_value={}),patch.object(F.E,'_container',return_value={'sucesso':True,'observacoes':obs}):
   with self.assertRaises(A.Revisao):F.rodar_ativo({},d)
if __name__=='__main__':unittest.main()
