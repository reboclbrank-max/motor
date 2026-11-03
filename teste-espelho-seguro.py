import unittest
import os
from pathlib import Path
import tempfile
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
class IntegridadeEspelho(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.src=Path(self.tmp.name,'orig')
  self.dst=Path(self.tmp.name,'esp')
  self.src.mkdir()
  self.dst.mkdir()
 def test_extra_no_destino_bloqueia_antes_da_copia(self):
  (self.src/'a.txt').write_text('novo')
  (self.dst/'a.txt').write_text('antigo')
  (self.dst/'extra.txt').write_text('preservado')
  with patch.object(E,'_git') as g:
   with self.assertRaisesRegex(RuntimeError,'extras'):
    E.sincronizar_caminhos(str(self.src),str(self.dst),push=False)
   g.assert_not_called()
  self.assertEqual((self.dst/'extra.txt').read_text(),'preservado')
  self.assertEqual((self.dst/'a.txt').read_text(),'antigo')
 def test_copia_integra_sem_exclusoes(self):
  (self.src/'a.txt').write_text('novo')
  (self.src/'b.txt').write_text('segundo')
  (self.dst/'a.txt').write_text('antigo')
  with patch.object(E,'_git',side_effect=lambda args,**kw:' M a.txt\n' if args[:2]==['status','--porcelain'] else '') as git:
   self.assertTrue(E.sincronizar_caminhos(str(self.src),str(self.dst),push=False))
   self.assertFalse(any(c.args[0][0]=='push' for c in git.call_args_list))
  self.assertEqual((self.dst/'a.txt').read_text(),'novo')
  self.assertEqual((self.dst/'b.txt').read_text(),'segundo')
 def test_link_simbolico_e_fila_especial_nao_passam(self):
  (self.src/'a.txt').write_text('novo')
  (self.src/'link').symlink_to('a.txt')
  with patch.object(E,'_git') as git:
   with self.assertRaises(RuntimeError):E.sincronizar_caminhos(str(self.src),str(self.dst))
   git.assert_not_called()
  (self.src/'link').unlink()
  os.mkfifo(self.src/'fila')
  with patch.object(E,'_git') as git:
   with self.assertRaises(RuntimeError):E.sincronizar_caminhos(str(self.src),str(self.dst))
   git.assert_not_called()
 def test_falha_copia_nao_commita_nem_envia(self):
  (self.src/'a.txt').write_text('novo')
  (self.dst/'a.txt').write_text('antigo')
  with patch.object(E.shutil,'copy2',side_effect=OSError('DISCO')),patch.object(E,'_git') as git:
   with self.assertRaises(OSError):E.sincronizar_caminhos(str(self.src),str(self.dst))
   git.assert_not_called()
  self.assertEqual((self.dst/'a.txt').read_text(),'antigo')

if __name__=='__main__':unittest.main()
