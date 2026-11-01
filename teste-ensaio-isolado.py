import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('ensaio',Path(__file__).with_name('ensaio-retomada.py'));E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)
class Ensaio(unittest.TestCase):
    def test_issue_comum_nao_pode_ser_usada(self):
        with patch.object(E.C,'gh',return_value={'state':'open','body':'normal','user':{'login':E.C.DONO_GITHUB}}):
            with self.assertRaises(ValueError):E.conferir_issue(42)
    def test_issue_sintetica_fechada_do_dono(self):
        i={'state':'closed','body':E.MARCA+'\nteste','user':{'login':E.C.DONO_GITHUB}}
        with patch.object(E.C,'gh',return_value=i):self.assertEqual(E.conferir_issue(42),i)
    def test_terceiro_nao_e_adotado(self):
        with patch.object(E.C,'gh',return_value={'state':'closed','body':E.MARCA,'user':{'login':'terceiro'}}):
            with self.assertRaises(ValueError):E.conferir_issue(42)
    def test_tres_runners_com_dependencias_sem_cron(self):
        s=Path(__file__).with_name('.github').joinpath('workflows/ensaio-retomada.yml').read_text()
        self.assertEqual(s.count('runs-on: ubuntu-latest'),3);self.assertIn('needs: [iniciar, retomar]',s)
        self.assertNotIn('schedule:',s);self.assertNotIn('secrets.EMAIL',s);self.assertNotIn('secrets.IG_',s)
    def test_subprocesso_real_nao_mata_runner(self):
        s=Path(__file__).with_name('ensaio-retomada.py').read_text();self.assertIn('os._exit(23)',s)
        self.assertIn('capture_output=True',s);self.assertNotIn('print(proc.stdout',s)
    def test_sem_atendimento_ou_aprendizado_de_fixture(self):
        s=Path(__file__).with_name('ensaio-retomada.py').read_text()
        for item in ['R.drenar_fila_respostas=lambda','C.checar_avisos_rapido=lambda','C.registrar_diario=lambda','C.registrar_resposta_cache=lambda','T.id_da_origem()!=id_isolado','MEMORIA/ensaios/retomada-']:
            self.assertIn(item,s)
    def test_digest_do_pai_igual_ao_evento_real_canonico(self):
        import hashlib
        pedido=(E.MARCA+'\n'+E.PEDIDO).strip()
        esperado=hashlib.sha256(pedido.encode()).hexdigest()
        with patch.object(E.T,'recuperar_da_origem',side_effect=lambda:E.T._PEDIDO_SHA.get()):
            self.assertEqual(E.registro(42),esperado)
if __name__=='__main__':unittest.main()
