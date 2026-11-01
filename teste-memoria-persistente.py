"""Reproduz gravação seguida do sincronizador, sem rede ou segredos."""
import base64
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import comum as C
import sincronizar as S

class MemoriaPersistente(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.cwd=os.getcwd();os.chdir(self.tmp.name)
        self.path='MEMORIA/memoria-longa.md';Path('MEMORIA').mkdir()
        self.antigo='# Fatos\n\n- fato anterior\n';Path(self.path).write_text(self.antigo)
        self.remoto=self.antigo;self.publicacoes=0
    def tearDown(self):
        os.chdir(self.cwd);self.tmp.cleanup()
    def api(self,metodo,caminho,corpo=None):
        if metodo=='PUT':
            self.remoto=base64.b64decode(corpo['content']).decode();self.publicacoes+=1;return {}
        if metodo=='GET':return {'sha':'sha-teste'}
        raise AssertionError(metodo)
    def sincronizar(self):
        # Usa subir() real e hashes reais dos bytes; a escrita direta já foi persistida.
        antes = self.publicacoes
        S._salvar_base({self.path:S._sha(self.antigo.encode())})
        with patch.object(S,'listar_remoto',side_effect=lambda:{self.path:S._sha(self.remoto.encode())}),patch.object(S,'_http',side_effect=self.api):
            self.assertEqual(S.subir(),0)
        self.assertEqual(self.publicacoes,antes, "não reenvia escrita já confirmada pela API")
    def test_escrita_nao_e_desfeita(self):
        with patch.object(C,'gh',side_effect=self.api):
            self.assertTrue(C.acrescentar_memoria(self.path,'- CODIGO-PERSISTENTE'))
        self.assertIn('CODIGO-PERSISTENTE',self.remoto)
        self.sincronizar()
        self.assertIn('CODIGO-PERSISTENTE',self.remoto)
        self.assertIn('fato anterior',self.remoto)
        self.assertEqual(Path(self.path).read_text(),self.remoto)
    def test_duas_escritas_preservadas(self):
        with patch.object(C,'gh',side_effect=self.api):
            C.acrescentar_memoria(self.path,'- PRIMEIRO')
            C.acrescentar_memoria(self.path,'- SEGUNDO')
        self.sincronizar()
        self.assertIn('PRIMEIRO',self.remoto);self.assertIn('SEGUNDO',self.remoto)
    def test_api_falhou_nao_confirma(self):
        with patch.object(C,'gh',side_effect=RuntimeError('indisponivel')):
            with self.assertRaises(RuntimeError):C.acrescentar_memoria(self.path,'- NAO-GRAVADO')
        self.assertEqual(Path(self.path).read_text(),self.antigo)
    def test_espelho_falhou_nao_confirma(self):
        with patch.object(C,'gh',side_effect=self.api),patch.object(C,'_gravar_local_memoria',side_effect=OSError('disco')):
            with self.assertRaises(OSError):C.acrescentar_memoria(self.path,'- DADO')
    def test_cria_pasta_primeira_gravacao(self):
        Path(self.path).unlink();Path('MEMORIA').rmdir()
        with patch.object(C,'gh',side_effect=self.api):
            C.acrescentar_memoria(self.path,'- PRIMEIRO',titulo='# Fatos')
        self.assertIn('PRIMEIRO',Path(self.path).read_text())

if __name__=='__main__':unittest.main()
