import unittest
from unittest.mock import patch,Mock
import espelho as E
class Espelho(unittest.TestCase):
 def test_erro_nao_repete_argumento_nem_stderr(self):
  with patch.object(E.subprocess,'run',return_value=Mock(returncode=1,stderr='SENTINELA_PRIVADA')):
   with self.assertRaises(RuntimeError) as e:E._git(['clone','https://user:SENTINELA_PRIVADA@example.invalid'])
  self.assertNotIn('SENTINELA',str(e.exception));self.assertIn('código 1',str(e.exception))
 def test_token_so_no_ambiente_efemero(self):
  with patch.object(E,'_git') as g,patch.object(E,'sincronizar_caminhos',return_value=True) as sync:
   self.assertTrue(E.sincronizar('base','base-espelho','SENTINELA_PRIVADA'))
  self.assertEqual(g.call_count,2)
  for c in g.call_args_list:self.assertNotIn('SENTINELA',str(c.args));self.assertNotIn('@github',str(c.args));self.assertIn('GIT_CONFIG_VALUE_0',c.kwargs['env'])
  self.assertIn('GIT_CONFIG_VALUE_0',sync.call_args.kwargs['env'])
 def test_falha_parcial_nao_verde(self):
  with patch.dict(E.os.environ,{'CHAT_TOKEN':'sentinela'}),patch.object(E,'sincronizar',side_effect=RuntimeError('sentinela')),patch.object(E.C,'log') as log:
   self.assertEqual(E.main(),1)
  self.assertNotIn('sentinela',str(log.call_args_list))
if __name__=='__main__':unittest.main()
