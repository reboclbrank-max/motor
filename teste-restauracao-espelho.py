"""Restaurar em fixture local vazia; nunca usa rede, segredos ou espelhos reais."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import restauracao_espelho as R


class ProvaRestauracao(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz=Path(self.tmp.name)
        self.fonte=self.raiz/'fonte'
        self.dest=self.raiz/'nova'
        self.fonte.mkdir()
        (self.fonte/'d').mkdir()
        (self.fonte/'d'/'a.txt').write_bytes(b'conteudo ficticio')
        (self.fonte/'b.txt').write_bytes(b'outro')

    def test_restauracao_em_novo_diretorio_preserva_bytes(self):
        antes=(self.fonte/'d'/'a.txt').read_bytes()
        res=R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertEqual(res,{'arquivos_verificados':2,'pastas_verificadas':1})
        self.assertEqual((self.dest/'d'/'a.txt').read_bytes(),antes)
        self.assertEqual((self.fonte/'d'/'a.txt').read_bytes(),antes)
        self.assertEqual((self.dest/'b.txt').read_bytes(),b'outro')

    def test_recusa_destino_existente_sem_modificar(self):
        self.dest.mkdir()
        (self.dest/'proteger.txt').write_bytes(b'nao apagar')
        with self.assertRaises(RuntimeError):
            R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertEqual((self.dest/'proteger.txt').read_bytes(),b'nao apagar')

    def test_recusa_symlink_antes_de_criar_destino(self):
        (self.fonte/'d'/'link').symlink_to('a.txt')
        with self.assertRaises(RuntimeError):
            R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertFalse(self.dest.exists())

    def test_recusa_destino_abaixo_da_fonte(self):
        with self.assertRaises(RuntimeError):
            R.ensaiar_restauracao(self.fonte,self.fonte/'destino')
        self.assertFalse((self.fonte/'destino').exists())

    def test_recusa_pasta_vazia(self):
        (self.fonte/'d'/'a.txt').unlink()
        (self.fonte/'b.txt').unlink()
        with self.assertRaises(RuntimeError):
            R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertFalse(self.dest.exists())

    def test_falha_de_copia_nao_declara_restauracao(self):
        with patch.object(R,'_copiar_verificado',side_effect=OSError('disco')):
            with self.assertRaises(OSError):
                R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertTrue(self.dest.exists())
        self.assertEqual((self.fonte/'d'/'a.txt').read_bytes(),b'conteudo ficticio')
        self.assertFalse((self.dest/'d'/'a.txt').exists())

    def test_hardlink_reprovado_antes_da_copia(self):
        (self.raiz/'externo').write_bytes(b'segredo-ficticio')
        os.link(self.raiz/'externo',self.fonte/'d'/'externo')
        with self.assertRaises(RuntimeError):
            R.ensaiar_restauracao(self.fonte,self.dest)
        self.assertFalse(self.dest.exists())


if __name__=='__main__':
    unittest.main()
