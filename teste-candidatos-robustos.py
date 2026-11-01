import unittest,json,importlib.util
from pathlib import Path
from unittest.mock import patch
s=importlib.util.spec_from_file_location('tm',Path(__file__).with_name('testar-motores.py'));T=importlib.util.module_from_spec(s);s.loader.exec_module(T)
class Candidatos(unittest.TestCase):
 def test_invalido_nao_aborta_valido(self):
  cs=[{'base':'https://example.com','modelo':'m','chave':'SENTINELA_PRIVADA'}, {'nome':'modelo','base':'https://example.com','modelo':'m'}]
  with patch.object(T.C,'ler_remoto',return_value=json.dumps(cs)),patch.object(T.C,'provar_motor',return_value=(True,1,'ok')) as provar,patch.object(T.C,'escrever_remoto'):
   linhas,aprovados=T.testar_candidatos()
  self.assertEqual(provar.call_count,1);self.assertEqual(len(aprovados),1);self.assertNotIn('SENTINELA',str(linhas))
 def test_esquemas_invalidos_sem_sondagem(self):
  for cs in [{'x':1},[None,1,{}, {'nome':'x','base':'https://u:SEGREDO@example.com','modelo':'m'}, {'nome':'x','base':'https://example.com','modelo':'m','timeout':'errado'}]]:
   with patch.object(T.C,'ler_remoto',return_value=json.dumps(cs)),patch.object(T.C,'provar_motor') as p:
    linhas,aprovados=T.testar_candidatos();p.assert_not_called();self.assertFalse(aprovados);self.assertTrue(linhas)
 def test_json_invalido_nao_reativa_defaults(self):
  with patch.object(T.C,'ler_remoto',return_value='QUEBRADO'),patch.object(T.C,'provar_motor') as p:
   T.testar_candidatos();p.assert_not_called()
if __name__=='__main__':unittest.main()
