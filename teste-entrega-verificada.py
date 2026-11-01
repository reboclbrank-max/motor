"""Contrato offline: entrega não implica qualidade semântica ou cumprimento da tarefa."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import varrer as V

class EntregaTest(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'REBOCL_VERIFICAR_ENTREGA':'1'});self.env.start()
        self.issue={'number':42,'body':'tarefa de teste','user':{'login':V.C.DONO_GITHUB}}
    def tearDown(self):
        self.env.stop()
    def resposta(self,marca='a42',autor=None):
        return {'body':V.C.ASSINATURA+'\n\nResposta teste\n<!--resp:'+marca+'-->',
                'user':{'login':autor or V.C.DONO_GITHUB}}
    def executar(self,fn,comentario=None):
        with patch.object(V.responder,'principal',side_effect=fn):
            return V.processar(self.issue,comentario)
    def test_saida_zero_sem_entrega_falha(self):
        with patch.object(V.C,'gh',return_value=[]):
            self.assertFalse(self.executar(lambda:0))
    def test_systemexit_erro_falha(self):
        def fn():raise SystemExit(7)
        with patch.object(V.C,'gh',return_value=[]):
            self.assertFalse(self.executar(fn))
    def test_saida_zero_com_entrega(self):
        comentarios=[]
        def fn():comentarios.append(self.resposta());return 0
        with patch.object(V.C,'gh',side_effect=lambda *a:comentarios[:]):
            self.assertTrue(self.executar(fn))
    def test_dedupe_apos_reinicio(self):
        with patch.object(V.C,'gh',return_value=[self.resposta()]):
            with patch.object(V.responder,'principal') as p:
                self.assertTrue(V.processar(self.issue,None));p.assert_not_called()
    def test_marca_de_terceiro_nao_confirma(self):
        with patch.object(V.C,'gh',return_value=[self.resposta(autor='terceiro')]):
            self.assertFalse(V.entrega_confirmada(42,'a42'))
    def test_marca_sem_assinatura_nao_confirma(self):
        c=self.resposta();c['body']='<!--resp:a42-->'
        with patch.object(V.C,'gh',return_value=[c]):
            self.assertFalse(V.entrega_confirmada(42,'a42'))
    def test_pagina_seguinte(self):
        with patch.object(V.C,'gh',side_effect=[[{'body':''}]*100,[self.resposta()]]):
            self.assertTrue(V.entrega_confirmada(42,'a42'))
    def test_api_falha_nao_vira_ocioso(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V.C,'gh',side_effect=OSError):
            self.assertEqual(V.main(),2)
    def test_api_malformada(self):
        with patch.object(V.C,'gh',return_value={'message':'erro'}):
            with self.assertRaises(RuntimeError):V.comentarios_verificados(42)
    def test_ambiente_restaurado_evento_removido(self):
        eventos=[]
        def fn():eventos.append(os.environ['GITHUB_EVENT_PATH']);return 0
        with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'original'}):
            with patch.object(V.C,'gh',return_value=[]):self.executar(fn)
            self.assertEqual(os.environ['GITHUB_EVENT_NAME'],'original')
        self.assertFalse(Path(eventos[0]).exists())
    def test_falha_entrega_retorna_nao_zero(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V,'pendentes',return_value=[(self.issue,None)]),patch.object(V,'processar',return_value=False):
            self.assertEqual(V.main(),1)
    def test_lista_vazia_observada(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V.C,'gh',return_value=[]):
            self.assertEqual(V.main(),0)
    def test_marca_comentario(self):
        with patch.object(V.C,'gh',return_value=[self.resposta('c77')]),patch.object(V.responder,'principal') as p:
            self.assertTrue(V.processar(self.issue,{'id':77}));p.assert_not_called()

    def test_resposta_real_com_memoria_e_retomada(self):
        # Principal, exatidão, publicação e registro reais; transporte GitHub simulado.
        import base64, json, tempfile
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); comentarios=root/'comentarios.json'
            comentarios.write_text('[]')
            self.issue['body']='quanto é 2 + 2?'
            def api(metodo,caminho,corpo=None):
                if metodo=='GET' and '/comments?' in caminho:
                    return json.loads(comentarios.read_text())
                if metodo=='POST' and caminho.endswith('/comments'):
                    lista=json.loads(comentarios.read_text())
                    lista.append({'body':corpo['body'],'user':{'login':V.C.DONO_GITHUB},'id':99})
                    comentarios.write_text(json.dumps(lista));return lista[-1]
                if metodo=='PUT' and '/contents/MEMORIA/' in caminho:
                    arquivo=root/caminho.split('/contents/')[1]
                    arquivo.parent.mkdir(parents=True,exist_ok=True)
                    arquivo.write_bytes(base64.b64decode(corpo['content']));return {'ok':True}
                if metodo=='GET' and '/contents/MEMORIA/trabalhos/' in caminho:
                    raise RuntimeError('HTTP 404')
                raise AssertionError('Acesso inesperado: '+metodo+' '+caminho)
            with patch.object(V.C,'gh',side_effect=api),patch.object(V.C,'sha_arquivo',return_value=None):
                self.assertTrue(V.processar(self.issue,None))
                self.assertTrue(V.processar(self.issue,None)) # reentrada: sem duplicar
            lista=json.loads(comentarios.read_text())
            self.assertEqual(len(lista),1)
            self.assertIn('**4**',lista[0]['body'])
            self.assertIn('exatidão local',(root/'MEMORIA/conversas/issue-42.md').read_text())
    def test_none_nao_vira_lista_vazia(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V.C,'gh',return_value=None):
            self.assertEqual(V.main(),2)
    def test_resposta_pat_dono_nao_vira_pergunta(self):
        self.issue['updated_at']='2099-01-01T00:00:00Z'
        with patch.object(V.C,'gh',side_effect=[[self.issue],[self.resposta()]]):
            self.assertEqual(V.pendentes(),[])

if __name__=='__main__':unittest.main()
