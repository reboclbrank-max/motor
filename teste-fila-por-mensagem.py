import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import varrer as V

class FilaMensagem(unittest.TestCase):
    def setUp(self):
        self.dono={'login':V.C.DONO_GITHUB,'type':'User'}
        self.i={'number':42,'body':'pergunta inicial','user':self.dono,'created_at':'2026-11-01T00:00:00Z'}
    def c(self,n,body='pergunta',user=None):
        return {'id':n,'body':body,'user':user or self.dono,'created_at':f'2026-11-01T00:00:{n:02d}Z'}
    def fila(self,cs,review=None):
        with patch.object(V.C,'gh',side_effect=[[self.i],cs]),patch.object(V,'revisao_historica',return_value=review or set()):
            return V.pendentes()
    def marcas(self,f):return [f'c{c["id"]}' if c else 'a42' for i,c in f]
    def test_inicial_e_duas_mensagens(self):
        self.assertEqual(self.marcas(self.fila([self.c(1),self.c(2)])),['a42','c1','c2'])
    def test_resposta_ultima_nao_apaga_anterior(self):
        cs=[self.c(1),self.c(2),self.c(3,V.C.ASSINATURA+'\nfeito<!--resp:c2-->')]
        self.assertEqual(self.marcas(self.fila(cs)),['a42','c1'])
    def test_terceiro_nao_forja_entrega(self):
        cs=[self.c(1),self.c(2,V.C.ASSINATURA+'<!--resp:c1-->',{'login':'terceiro'})]
        self.assertIn('c1',self.marcas(self.fila(cs)))
    def test_inicial_respondida_nao_volta(self):
        cs=[self.c(1,V.C.ASSINATURA+'<!--resp:a42-->'),self.c(2)]
        self.assertEqual(self.marcas(self.fila(cs)),['c2'])
    def test_revisao_nao_e_sucesso(self):
        self.assertEqual(self.marcas(self.fila([self.c(1)],{(42,'a42')})),['c1'])
    def test_falha_entre_mensagens_nao_perde_fila(self):
        cs=[self.c(1),self.c(2)]
        primeira=self.marcas(self.fila(cs));self.assertIn('c2',primeira)
        cs.append(self.c(3,V.C.ASSINATURA+'<!--resp:c1-->'))
        self.assertIn('c2',self.marcas(self.fila(cs)))
    def test_registro_obrigatorio_ausente_falha(self):
        with patch.dict(os.environ,{'FILA_EXIGE_REVISAO_HISTORICA':'1'}),patch.object(V.os.path,'isfile',return_value=False):
            with self.assertRaises(RuntimeError):V.revisao_historica()
    def test_ensaio_marcado_nao_disputa_worker(self):
        self.i["body"]="<!--ensaio-retomada:isolado-->\nteste"
        with patch.object(V.C,"gh",return_value=[self.i]),patch.object(V,"revisao_historica",return_value=set()):
            self.assertEqual(V.pendentes(),[])
    def test_ordenacao_cronologica(self):
        self.assertEqual(self.marcas(self.fila([self.c(2),self.c(1)])),['a42','c1','c2'])

class Legados(unittest.TestCase):
    def test_aviso_antigo_nao_e_ordem(self):
        texto=f"@{V.C.DONO_GITHUB} — aviso automático do assistente.\n\n### Estado\n\nAviso.\n\n---\n_Você recebe isto pela menção (e-mail/app do GitHub). Para receber também no Telegram (grátis), veja o passo a passo no COMECE-AQUI._"
        self.assertTrue(V._do_robo(texto));self.assertFalse(V._do_robo('Por que recebi '+texto))
    def test_turno_e_sonho_anteriores(self):
        for prefix in ['🌅 **Turno autônomo 01/01**','🌙 **Sonho da noite**']:
            self.assertTrue(V._do_robo(prefix+'\n**Missão de hoje:** saúde\n\n_(🤖 eu acordei sozinha hoje · motor)_'))
        self.assertFalse(V._do_robo('🌅 **Turno autônomo 01/01** pode explicar isso?'))
    def test_turno_falhou_sem_resposta_nao_e_pedido(self):
        self.assertTrue(V._do_robo('🌅 **Turno autônomo 01/01** — acordei, mas o motor não respondeu (`indisponível`).'))
    def test_rotina_antiga_so_abertura_nao_comentarios_humanos(self):
        i={'title':'📋 Rotina da noite — 01/01/2026','body':'Boa noite\n### 🌐 Tudo no ar?\n### 🌤 Clima\n### 🔔 Avisos e lembretes'}
        self.assertTrue(V._rotina_legada(i,None));self.assertFalse(V._rotina_legada(i,{'body':'corrija o diagnóstico'}));self.assertFalse(V._rotina_legada(dict(i,title='Meu pedido'),None))
    def test_conversa_de_robo_preserva_pergunta_do_dono(self):
        i={'number':42,'user':{'login':V.C.DONO_GITHUB},'title':'📋 Rotina da noite — 01/01/2026','body':'### 🌐 Tudo no ar?\n### 🌤 Clima\n### 🔔 Avisos e lembretes'}
        c={'id':1,'user':{'login':V.C.DONO_GITHUB},'body':'corrija esta informação','created_at':'2026-01-01T01:00:00Z'}
        with patch.object(V.C,'gh',side_effect=[[i],[c]]),patch.object(V,'revisao_historica',return_value=set()):
            self.assertEqual(V.pendentes(),[(i,c)])
    def test_produtores_marcam_bot_sem_executar_modelos(self):
        from pathlib import Path
        import ast
        root=Path(__file__).resolve().parent
        for n in ['comum.py','inspire.py','rotina.py']:
            ast.parse((root/n).read_text())
        self.assertIn('<!--robo:inspire-->',(root/'inspire.py').read_text());self.assertIn('<!--robo:rotina-->',(root/'rotina.py').read_text());self.assertIn('🤖 @{DONO_GITHUB} — aviso automático',(root/'comum.py').read_text())

if __name__=='__main__':unittest.main()
