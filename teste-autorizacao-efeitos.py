import unittest,json
from unittest.mock import patch
import comum as C,casa,autorizacao_efeitos as A
class Efeitos(unittest.TestCase):
 def test_modelo_nao_autoriza_email_ou_configuracao(self):
  with casa.contexto_pedido('Explique como funciona o chat'),patch.object(C,'ferramenta_email') as email,patch.object(C,'_ferramenta_plantar') as plantar:
   self.assertIn('exige pedido',C.executar_ferramenta('EMAIL','resumo | inventado'))
   self.assertIn('exige pedido',C.executar_ferramenta('PLANTAR','https://example.com | modelo'))
   email.assert_not_called();plantar.assert_not_called()
 def test_autorizacao_atual_e_negacoes(self):
  self.assertTrue(A.permitido('EMAIL','x','Envie um email com o resumo'))
  self.assertFalse(A.permitido('EMAIL','x','Me explique como enviar email'))
  self.assertFalse(A.permitido('EMAIL','x','Não envie email'))
  self.assertFalse(A.permitido('PLANTAR','https://evil.example | y','Plante https://example.com | x'))
  self.assertTrue(A.permitido('PLANTAR','https://example.com | x','Plante https://example.com | x'))
 def test_candidato_completo_preserva_registros_antigos(self):
  gravados=[]
  with patch.object(C,'ler_remoto',return_value=json.dumps([None,{'base':'antigo','modelo':'x'}])),patch.object(C,'_validar_url_publica'),patch.object(C,'escrever_remoto',side_effect=lambda a,b,c:gravados.append(json.loads(b)) or True):
   self.assertIn('Plantado',C._ferramenta_plantar('https://example.com/v1 | modelo'))
  self.assertEqual(gravados[0][:2],[None,{'base':'antigo','modelo':'x'}]);self.assertTrue(gravados[0][-1]['nome']);self.assertEqual(gravados[0][-1]['timeout'],45)
 def test_cadastro_corrompido_nao_e_apagado(self):
  with patch.object(C,'ler_remoto',return_value='JSON CORROMPIDO'),patch.object(C,'_validar_url_publica'),patch.object(C,'escrever_remoto') as gravar:
   self.assertIn('não apaguei',C._ferramenta_plantar('https://example.com | x'));gravar.assert_not_called()
 def test_sem_recibo_nao_declara_sucesso(self):
  with patch.object(C,'ler_remoto',return_value='[]'),patch.object(C,'_validar_url_publica'),patch.object(C,'escrever_remoto',return_value=False):
   self.assertIn('não confirmado',C._ferramenta_plantar('https://example.com | x'))
 def test_url_credencial_query_negada_sem_gravacao(self):
  with patch.object(C,'escrever_remoto') as gravar:
   self.assertIn('não alterei',C._ferramenta_plantar('https://example.com/?key=NAO_USAR | x'));gravar.assert_not_called()
if __name__=='__main__':unittest.main()
