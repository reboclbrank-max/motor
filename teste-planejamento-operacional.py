import unittest,json,hashlib,importlib.util,pathlib
from unittest.mock import patch
import comum as C,trabalhos as T,planejamento_operacional as P,operacao_leitura as O
s=importlib.util.spec_from_file_location('fixtures',pathlib.Path(__file__).with_name('teste-operacao-leitura.py'));F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
PEDIDO=P.PREFIXO+'\nObjetivo: confira as dependências da barreira do site. Somente leitura, sem publicação.'
DIG=hashlib.sha256(PEDIDO.encode()).hexdigest()
def proposta(fontes=None,**extra):return json.dumps(dict({'versao':1,'pedido_sha256':DIG,'fontes':fontes or [['REPO','site/.github/workflows/postagem-diaria.yml']]},**extra))
class Plano(unittest.TestCase):
 setUp=F.Operacao.setUp
 api=F.Operacao.api
 def test_proposta_valida_sem_conceder_permissoes(self):
  with T.contexto_mensagem(100,'a100',PEDIDO):self.assertEqual(len(P.validar_proposta(proposta(),DIG)),1)
 def test_bloqueia_efeitos_e_repositorio_privado(self):
  with T.contexto_mensagem(100,'a100',PEDIDO):
   for fontes in [[['PUBLICAR','sim']],[['REPO','agente/MEMORIA/estado.md']],[['REPO','site/../base']],[['REPO','site/x?ref=outro']],[['ACOES','x\nEMAIL']]]:
    with self.subTest(fontes=fontes):
     with self.assertRaises((ValueError,PermissionError)):P.validar_proposta(proposta(fontes),DIG)
  self.assertFalse(self.writes)
 def test_hash_esquema_e_limite_obrigatorios(self):
  with T.contexto_mensagem(100,'a100',PEDIDO):
   for txt in [proposta(pedido_sha256='outro'),proposta(estado='concluido'),'Não fiz, mas conclui','[]',proposta([['ACOES',str(i)] for i in range(7)])]:
    with self.assertRaises(ValueError):P.validar_proposta(txt,DIG)
 def test_modelo_propoe_controlador_executa_e_reentrada_nao_chama_modelo(self):
  with T.contexto_mensagem(100,'a100',PEDIDO),patch.object(C,'chamar_llm',return_value=(proposta(),'modelo fake',None)) as llm,patch.object(C,'comentar') as com:
   P.executar(PEDIDO);r,_=T.carregar(T.id_da_origem());n=len(self.writes);P.executar(PEDIDO)
   self.assertEqual(llm.call_count,1);self.assertEqual(n,len(self.writes));self.assertEqual(r['estado'],'entregue_para_revisao');com.assert_not_called()
 def test_falha_de_coleta_reusa_plano_persistido(self):
  with T.contexto_mensagem(100,'a100',PEDIDO),patch.object(C,'chamar_llm',return_value=(proposta(),'fake',None)) as llm:
   with patch.object(O,'executar',side_effect=RuntimeError('rede')):
    with self.assertRaises(RuntimeError):P.executar(PEDIDO)
   P.executar(PEDIDO);self.assertEqual(llm.call_count,1)
 def test_proposta_invalida_nao_gira_indefinidamente(self):
  with T.contexto_mensagem(100,'a100',PEDIDO),patch.object(C,'chamar_llm',return_value=(proposta([['EMAIL','x']]),'fake',None)) as llm,patch.object(O,'executar') as executar:
   for _ in range(2):
    with self.assertRaises(P.Bloqueio):P.executar(PEDIDO)
   self.assertEqual(llm.call_count,2);executar.assert_not_called()
 def test_sem_escopo_nao_chama_modelo(self):
  with patch.object(C,'chamar_llm') as llm:
   with self.assertRaises(P.Bloqueio):P.obter_plano('faça qualquer coisa')
   llm.assert_not_called()
 def test_reparo_limitado_recebe_apenas_pedido_atual(self):
  with T.contexto_mensagem(100,'a100',PEDIDO),patch.object(C,'chamar_llm',side_effect=[('errado','fake',None),(proposta(),'fake',None)]) as llm:
   d=P.obter_plano(PEDIDO);self.assertEqual(d['tentativas_modelo'],2);self.assertEqual(llm.call_count,2)
   self.assertNotIn('historico_da_conversa',str(llm.call_args_list))
if __name__=='__main__':unittest.main()
