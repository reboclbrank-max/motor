import unittest,json
from unittest.mock import patch
import comum as C
class Cache(unittest.TestCase):
 def registro(self,resposta):return json.dumps([{'p':'Execute uma tarefa','h':C.hash_pergunta('Execute uma tarefa'),'r':resposta}])
 def test_cache_legado_nao_reentrega_progresso_de_outra_origem(self):
  for r in ['Trabalho `7b74106618465b77934bedcc01e71a8d` salvo em planejado, mas ainda não entregue.','**Recibo do trabalho `7b74106618465b77934bedcc01e71a8d`** Estado: entregue para revisão.']:
   with patch.object(C,'ler_remoto',return_value=self.registro(r)):
    self.assertIsNone(C.cache_exato('Execute uma tarefa'));self.assertIsNone(C.resposta_de_reserva('Execute uma tarefa'))
 def test_informacao_continua_reutilizavel(self):
  with patch.object(C,'ler_remoto',return_value=self.registro('Uma fila organiza itens pendentes.')):
   self.assertEqual(C.cache_exato('Execute uma tarefa'),'Uma fila organiza itens pendentes.')
 def test_operacional_nao_e_gravado(self):
  with patch.object(C,'escrever_remoto') as w:
   self.assertFalse(C.registrar_resposta_cache('Execute uma tarefa','Trabalho salvo em planejado'));w.assert_not_called()
 def test_fluxo_principal_nao_cacheia_falha_ou_ferramenta(self):
  from pathlib import Path
  s=Path(C.__file__).with_name('responder.py').read_text();self.assertIn('if not resposta_falha and not usos and trabalho_atual is None:',s)
if __name__=='__main__':unittest.main()
