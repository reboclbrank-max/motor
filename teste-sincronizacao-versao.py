"""Contratos da sincronização com API em memória; sem rede, segredo ou dado real."""
import base64
import json
import os
import tempfile
import unittest
import urllib.error
import io
import contextlib
from pathlib import Path
from unittest.mock import patch
import sincronizar as S
_HTTP_ORIGINAL = S._http  # captura antes do setUp substituir o transporte


class Sincronizacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.cwd = os.getcwd(); os.chdir(self.tmp.name)
        self.arq = 'MEMORIA/estado.json'; self.store = {self.arq:b'original'}; self.puts = []
        for p in [patch.object(S,'_http',side_effect=self.api), patch.object(S,'PASTA','MEMORIA'),patch.object(S,'REPO_MEMORIA','dono/memoria'),patch.object(S,'RAMO','main')]:
            p.start(); self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup); self.addCleanup(os.chdir,self.cwd)
    def api(self, metodo, caminho, corpo=None):
        if '/git/trees/' in caminho:
            return {'tree':[{'path':k,'sha':S._sha(v),'type':'blob'} for k,v in self.store.items()]}
        if '/git/blobs/' in caminho:
            sha=caminho.rsplit('/',1)[1];v=next(v for v in self.store.values() if S._sha(v)==sha)
            return {'content':base64.b64encode(v).decode()}
        if metodo == 'GET' and '/contents/' in caminho:
            key=caminho.split('/contents/')[1].split('?')[0]
            if key not in self.store:raise urllib.error.HTTPError('nao_logar_url_privada',404,'faltou',None,None)
            return {'content':base64.b64encode(self.store[key]).decode(),'sha':S._sha(self.store[key])}
        if metodo == 'PUT':
            key=caminho.split('/contents/')[1];v=self.store.get(key)
            if (S._sha(v) if v is not None else None)!=corpo.get('sha'):raise RuntimeError('HTTP409')
            v=base64.b64decode(corpo['content']);self.puts.append(corpo.copy());self.store[key]=v
            return {'content':{'sha':S._sha(v)}}
        raise AssertionError('rota não simulada')
    def baixar(self):self.assertEqual(S.baixar(),0)
    def test_get_recupera_503_transitorio_sem_logar_segredo(self):
        class Resposta:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"ok": true}'
        erro = urllib.error.HTTPError('url-privada', 503, 'indisponivel', None, None)
        with patch.object(S, 'TOKEN', 'valor-ficticio'), \
             patch.object(S.urllib.request, 'urlopen', side_effect=[erro, Resposta()]) as abrir, \
             patch.object(S.time, 'sleep') as dormir:
            self.assertEqual(_HTTP_ORIGINAL('GET', '/rota-publica'), {'ok': True})
            self.assertEqual(abrir.call_count, 2)
            dormir.assert_called_once_with(0.5)

    def test_get_401_nao_tenta_repetir_credencial_rejeitada(self):
        erro = urllib.error.HTTPError('url-privada', 401, 'bloqueado', None, None)
        with patch.object(S, 'TOKEN', 'valor-ficticio'), \
             patch.object(S.urllib.request, 'urlopen', side_effect=erro) as abrir, \
             patch.object(S.time, 'sleep') as dormir:
            with self.assertRaises(urllib.error.HTTPError):
                _HTTP_ORIGINAL('GET', '/rota-publica')
            self.assertEqual(abrir.call_count, 1)
            dormir.assert_not_called()
        self.assertEqual(S._motivo_seguro(erro), 'http_401')

    def test_put_com_erro_de_rede_nao_e_repetido(self):
        erro = urllib.error.URLError('sem rede')
        with patch.object(S, 'TOKEN', 'valor-ficticio'), \
             patch.object(S.urllib.request, 'urlopen', side_effect=erro) as abrir, \
             patch.object(S.time, 'sleep') as dormir:
            with self.assertRaises(urllib.error.URLError):
                _HTTP_ORIGINAL('PUT', '/rota-publica', {'conteudo': 'ficticio'})
            self.assertEqual(abrir.call_count, 1)
            dormir.assert_not_called()
        self.assertEqual(S._motivo_seguro(erro), 'rede_indisponivel')

    def test_download_confere_blob_e_base_fora_memoria(self):
        self.baixar();self.assertEqual(S._ler_base()[self.arq],S._sha(b'original'))
        self.assertFalse(Path('MEMORIA/.memoria-sync.json').exists())
    def test_sem_mudanca_nao_escreve(self):
        self.baixar();self.assertEqual(S.subir(),0);self.assertFalse(self.puts)
    def test_remoto_novo_local_intocado_nao_e_sobrescrito(self):
        self.baixar();self.store[self.arq]=b'outro executor';self.assertEqual(S.subir(),0)
        self.assertEqual(self.store[self.arq],b'outro executor');self.assertFalse(self.puts)
    def test_duas_edicoes_divergentes_preservam_ambos_sem_put_na_origem(self):
        self.baixar();self.store[self.arq]=b'novo remoto';Path(self.arq).write_bytes(b'novo local')
        self.assertEqual(S.subir(),1);self.assertEqual(self.store[self.arq],b'novo remoto');self.assertEqual(len(self.puts),1)
        copias=[json.loads(v) for k,v in self.store.items() if '/conflitos-sync/' in k]
        self.assertEqual(len(copias),1);self.assertEqual(base64.b64decode(copias[0]['conteudo_base64']),b'novo local')
        self.assertEqual(copias[0]['sha_local'],S._sha(b'novo local'))
        self.assertEqual(S.subir(),1);self.assertEqual(len(self.puts),1)
        self.assertEqual(Path(self.arq).read_bytes(),b'novo local')
    def test_local_editado_usa_sha_da_base(self):
        self.baixar();Path(self.arq).write_bytes(b'editado');self.assertEqual(S.subir(),0)
        self.assertEqual(self.puts[0]['sha'],S._sha(b'original'));self.assertEqual(self.store[self.arq],b'editado')
    def test_escrita_direta_api_e_espelho_igual_nao_reenvia(self):
        self.baixar();self.store[self.arq]=b'gravado na API';Path(self.arq).write_bytes(b'gravado na API')
        self.assertEqual(S.subir(),0);self.assertFalse(self.puts)
    def test_criacao_nova_so_uma_vez(self):
        self.baixar();Path('MEMORIA/novo.md').write_bytes(b'entrega')
        self.assertEqual(S.subir(),0);self.assertEqual(S.subir(),0);self.assertEqual(len(self.puts),1)
    def test_novo_arquivo_com_colisao_remota_nao_sobrescreve(self):
        self.baixar();self.store['MEMORIA/novo.md']=b'de outro';Path('MEMORIA/novo.md').write_bytes(b'meu')
        self.assertEqual(S.subir(),1);self.assertEqual(self.store['MEMORIA/novo.md'],b'de outro')
    def test_falha_individual_download_nao_cria_base_valida(self):
        self.baixar()
        with patch.object(S,'_http',side_effect=lambda m,p,c=None: (_ for _ in ()).throw(RuntimeError('503')) if '/git/blobs/' in p else self.api(m,p,c)):
            self.assertEqual(S.baixar(),1)
        self.assertFalse(Path(S.MANIFESTO).exists());self.assertEqual(S.subir(),1)
    def test_falha_de_put_nao_vira_sucesso_e_pode_repetir(self):
        self.baixar();Path(self.arq).write_bytes(b'editado')
        with patch.object(S,'_http',side_effect=lambda m,p,c=None: (_ for _ in ()).throw(RuntimeError('503')) if m=='PUT' else self.api(m,p,c)):
            self.assertEqual(S.subir(),1)
        self.assertEqual(S.subir(),0);self.assertEqual(self.store[self.arq],b'editado')
    def test_sem_manifesto_nao_envia_nem_cria(self):
        Path('MEMORIA').mkdir();Path(self.arq).write_bytes(b'orfao');self.assertEqual(S.subir(),1);self.assertFalse(self.puts)
    def test_escopo_diferente_nao_envia(self):
        self.baixar()
        with patch.object(S,'RAMO','outro'):self.assertEqual(S.subir(),1)
        self.assertFalse(self.puts)
    def test_listagem_truncada_falha(self):
        with patch.object(S,'_http',return_value={'tree':[],'truncated':True}):self.assertEqual(S.baixar(),1)
    def test_corpo_divergente_do_sha_falha(self):
        with patch.object(S,'_http',side_effect=lambda m,p,c=None: {'content':base64.b64encode(b'errado').decode()} if '/git/blobs/' in p else self.api(m,p,c)):
            self.assertEqual(S.baixar(),1)
        self.assertFalse(Path(self.arq).exists())
    def test_race_apos_listagem_http409_nao_sobrescreve(self):
        self.baixar();Path(self.arq).write_bytes(b'local')
        def race(m,p,c=None):
            if m=='PUT':self.store[self.arq]=b'concorrente'
            return self.api(m,p,c)
        with patch.object(S,'_http',side_effect=race):self.assertEqual(S.subir(),1)
        self.assertEqual(self.store[self.arq],b'concorrente')
    def test_backup_falha_nao_finge_preservacao(self):
        self.baixar();self.store[self.arq]=b'concorrente';Path(self.arq).write_bytes(b'local')
        out=io.StringIO()
        with contextlib.redirect_stdout(out),patch.object(S,'preservar_conflito',side_effect=RuntimeError('SEGREDO_PRIVADO')):
            self.assertEqual(S.subir(),1)
        self.assertIn('conflito_sem_copia_confirmada',out.getvalue());self.assertNotIn('SEGREDO_PRIVADO',out.getvalue());self.assertNotIn(self.arq,out.getvalue())
        self.assertEqual(self.store[self.arq],b'concorrente')
    def test_http409_preserva_local_e_origem(self):
        self.baixar();Path(self.arq).write_bytes(b'local')
        def race(m,p,c=None):
            if m=='PUT' and p.endswith('/'+self.arq):
                self.store[self.arq]=b'concorrente';raise urllib.error.HTTPError('SEGREDO_PRIVADO',409,'conflito',None,None)
            return self.api(m,p,c)
        with patch.object(S,'_http',side_effect=race):self.assertEqual(S.subir(),1)
        self.assertEqual(self.store[self.arq],b'concorrente')
        self.assertEqual(len([k for k in self.store if '/conflitos-sync/' in k]),1)
    def test_recibo_incorreto_nao_confirma(self):
        self.baixar();Path(self.arq).write_bytes(b'local')
        with patch.object(S,'_http',side_effect=lambda m,p,c=None: {} if m=='PUT' else self.api(m,p,c)):
            self.assertEqual(S.subir(),1)
    def test_remocao_remota_nao_ressuscita_copia_intocada(self):
        self.baixar();del self.store[self.arq];self.assertEqual(S.subir(),0);self.assertFalse(self.puts)
    def test_recusa_caminho_fora_da_memoria(self):
        with patch.object(S,'listar_remoto',return_value={'MEMORIA/../fora.md':S._sha(b'x')}):self.assertEqual(S.baixar(),1)
        self.assertFalse(Path('fora.md').exists())
    def test_erro_disco_de_download_nao_vira_sucesso(self):
        with patch.object(S,'_atomico',side_effect=OSError('disco')):self.assertEqual(S.baixar(),1)
    def test_manifesto_corrompido_nao_envia(self):
        self.baixar();Path(S.MANIFESTO).write_text('{');self.assertEqual(S.subir(),1);self.assertFalse(self.puts)

if __name__=='__main__':unittest.main()
