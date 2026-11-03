import unittest
from unittest.mock import patch
import diagnostico_autonomia as D
class Diagnostico(unittest.TestCase):
 def test_pin_divergente_nao_aparece_ativo(self):
  d=D.avaliar({'ativo':True},{'ativo':True,'worker_sha':'a'*40},{'ativo':False},'b'*40)
  self.assertIn('bloqueado por versão',d['agenda']);self.assertEqual(d['componente'],'pausado')
 def test_pausa_geral_prevalece(self):
  d=D.avaliar({'ativo':False},{'ativo':True,'worker_sha':'a'*40},{'ativo':True,'worker_sha':'a'*40},'a'*40)
  self.assertIn('pausa geral',d['agenda']);self.assertIn('pausa geral',d['componente'])
 def test_pin_compativel_nao_promete_execucao(self):
  self.assertIn('execução não comprovada',D.avaliar({'ativo':True},{'ativo':True,'worker_sha':'a'*40},None,'a'*40)['agenda'])
 def test_erro_nao_expoe_corpo(self):
  with patch.object(D.A,'ler',side_effect=RuntimeError('conteudo-privado')):self.assertNotIn('conteudo-privado',D.texto());self.assertIn('não observável',D.texto())
 def test_consulta_somente_get(self):
  with patch.object(D.A,'ler',return_value=({'ativo':True,'worker_sha':'a'*40},None)),patch.object(D.C,'gh',return_value={'object':{'sha':'a'*40}}) as gh:
   D.consultar();gh.assert_called_once_with('GET',f'/repos/{D.C.REPO_ROBO}/git/ref/heads/main')
if __name__=='__main__':unittest.main()
