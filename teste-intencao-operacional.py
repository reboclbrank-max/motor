import unittest,json,importlib.util,pathlib,base64
from unittest.mock import patch
import intencao_operacional as I,planejamento_operacional as P,comum as C,trabalhos as T,varrer as V,responder as R,operacao_leitura as O
s=importlib.util.spec_from_file_location('fixtures',pathlib.Path(__file__).with_name('teste-operacao-leitura.py'));F=importlib.util.module_from_spec(s);s.loader.exec_module(F)
PEDIDO='Confira as barreiras de preparação do Site e do Chat da casa e gere um dossiê com fontes e SHAs. Sem publicar, sem alterar código e sem gastar.'
class Intencao(unittest.TestCase):
 setUp=F.Operacao.setUp
 def api(self,m,p,d=None):
  if m=="GET" and "/motor/contents/.github/workflows/chat.yml" in p:
   b=F.YAML.encode();return {"sha":O.sha(b),"content":base64.b64encode(b).decode()}
  return F.Operacao.api(self,m,p,d)
 def test_natural_sem_marcador_duas_fontes(self):
  d=I.classificar(PEDIDO);self.assertEqual(d['modo'],'automatico');self.assertEqual(len(d['fontes_minimas']),2);self.assertFalse(I.explicito(PEDIDO))
 def test_status_executor(self):
  self.assertEqual(I.classificar('Como está o Chat da casa?')['fontes_minimas'],[['ACOES','chat']])
  self.assertEqual(I.classificar('Pode conferir a operação?')['fontes_minimas'],[['ACOES','chat']])
 def test_casos_ambiguos_ou_fora_do_dominio_nao_sao_roteados(self):
  for pedido in ['Oi, tudo bem?','Termine tudo','Verifique o motor do carro','Analise o site https://example.org','Mostre esse chat','"Confira a operação"','> Confira a operação','Não confira a operação; publique']:
   with self.subTest(pedido=pedido):self.assertIsNone(I.classificar(pedido))
 def test_pedido_misto_nao_faz_leitura_nem_escrita_de_producao(self):
  pedido='Confira a operação do Chat e publique no Site.'
  with T.contexto_mensagem(101,'a101',pedido),patch.object(C,'chamar_llm') as modelo,patch.object(O,'coletar') as coletar:
   for _ in range(2):
    with self.assertRaises(P.Bloqueio):P.executar(pedido)
   modelo.assert_not_called();coletar.assert_not_called()
  self.assertEqual(len(self.writes),1);self.assertIn('planos-operacionais',self.writes[0])
 def test_negacao_nao_libera_mutacao_posterior(self):
  self.assertEqual(I.classificar('Confira a operação sem publicar e depois publique no site da casa')['modo'],'bloqueado')
 def test_plano_natural_sem_modelo_e_reentrada(self):
  with T.contexto_mensagem(101,'a101',PEDIDO),patch.object(C,'chamar_llm') as modelo:
   P.executar(PEDIDO);r,_=T.carregar(T.id_da_origem());n=len(self.writes);P.executar(PEDIDO);self.assertEqual(len(self.writes),n);modelo.assert_not_called();self.assertEqual(r['estado'],'entregue_para_revisao')
   b=self.store[r['evidencia_operacional']['arquivo']].decode();self.assertIn('roteador determinístico',b);self.assertNotIn('Fontes propostas por modelo',b)
 def test_autorizacao_de_ferramentas_fica_restrita(self):
  with T.contexto_mensagem(101,'a101',PEDIDO):
   for tipo in ['EMAIL','PUBLICAR','PLANTAR','DIAGNOSTICAR']:
    with self.assertRaises(PermissionError):C.executar_ferramenta(tipo,'x')
 def test_final_antigo_natural_preservado_sem_reabrir_historico(self):
  i={'number':101,'body':PEDIDO,'user':{'login':C.DONO_GITHUB}};c={'body':C.ASSINATURA+'\nresposta antiga\n<!--resp:a101-->','user':{'login':C.DONO_GITHUB}}
  def gh(m,p,*a):return [c] if '/comments?' in p else [i]
  with patch.object(C,'gh',side_effect=gh):self.assertEqual(V.pendentes(),[])
  with T.contexto_mensagem(101,'a101',PEDIDO),patch.object(C,'comentarios_da_conversa_verificados',return_value=[c]):self.assertTrue(R.ja_respondida(101,'a101'))
 def test_explicitos_anteriores_preservados(self):
  self.assertEqual(I.classificar(I.PREFIXO_LEITURA+'objetivo')['modo'],'leitura_explicita');self.assertEqual(I.classificar(I.PREFIXO_PLANO+'objetivo')['modo'],'planejamento_explicito');self.assertTrue(O.exige_comprovante(I.PREFIXO_LEITURA))
 def test_caminho_inseguro_natural_bloqueado(self):
  pedido='Leia site/../base.'
  with T.contexto_mensagem(101,'a101',pedido),patch.object(C,'chamar_llm') as modelo:
   with self.assertRaises((ValueError,PermissionError)):P.executar(pedido)
   modelo.assert_not_called()
if __name__=='__main__':unittest.main()
