#!/usr/bin/env python3
"""Contrato offline: indisponibilidade não é entrega nem conclusão de trabalho."""
import base64
import json
import unittest
from unittest.mock import patch
import comum as C
import responder as R
import varrer as V


class Contrato(unittest.TestCase):
    def setUp(self):
        self.cs = []
        self.dono = {'login': C.DONO_GITHUB, 'type': 'User'}
        self.issue = {'number': 42, 'body': 'pedido controlado', 'user': self.dono}

    def comentario(self, texto):
        return {'id': len(self.cs)+1, 'body': C.ASSINATURA+'\n\n'+texto, 'user': self.dono}

    def test_avisos_legados_nao_encerram_pedido(self):
        avisos = ['🚦 **Não consegui falar com nenhum motor agora** (falha)',
                  '⚠️ Agora não consegui responder: motores fora',
                  '🗄 **Cérebro de reserva (100% meu, sem motores):** texto aproximado']
        for aviso in avisos:
            with self.subTest(aviso=aviso):
                c = self.comentario(aviso+' <!--resp:a42-->')
                self.assertFalse(C.comentario_e_resposta_final(c))
                with patch.object(C, 'gh', return_value=[c]):
                    self.assertFalse(R.ja_respondida(42, 'a42'))
                    self.assertFalse(V.entrega_confirmada(42, 'a42'))

    def test_marca_pendente_nao_e_final(self):
        c = self.comentario('status <!--estado:pendente--><!--resp:a42-->')
        self.assertFalse(C.comentario_e_resposta_final(c))

    def test_erro_nao_some_da_fila(self):
        c = self.comentario('🚦 **Não consegui falar com nenhum motor agora** <!--resp:a42-->')
        with patch.object(C, 'gh', side_effect=[[self.issue], [c]]), patch.object(V, 'revisao_historica', return_value=set()):
            self.assertEqual(V.pendentes(), [(self.issue, None)])

    def test_publicacao_pendente_reutiliza_aviso(self):
        def comentar(n, corpo):
            self.cs.append({'id': 10, 'body': corpo, 'user': self.dono})
        def editar(i, corpo):
            self.assertEqual(i, 10)
            self.cs[0]['body'] = corpo
            return True
        with patch.object(C, 'comentarios_da_conversa_verificados', lambda n: list(self.cs)), patch.object(C, 'comentar', comentar), patch.object(C, 'editar_comentario', editar):
            R.responder(42, 'aguardando', 'a42', pendente=True)
            R.responder(42, 'ainda aguardando', 'a42', pendente=True)
        self.assertEqual(len(self.cs), 1)
        self.assertNotIn('<!--resp:a42-->', self.cs[0]['body'])
        self.assertIn('<!--pendente:a42-->', self.cs[0]['body'])

    def test_falha_retorno_e_reentrada_sem_duplicacao(self):
        def falha():
            self.cs.append(self.comentario('aguardando <!--estado:pendente--><!--pendente:a42-->'))
            return 0
        def recuperado():
            self.cs.append(self.comentario('resultado verificado <!--resp:a42-->'))
            return 0
        with patch.object(C, 'gh', side_effect=lambda *a: list(self.cs)):
            with patch.object(R, 'principal', side_effect=falha):
                self.assertFalse(V.processar(self.issue, None))
            with patch.object(R, 'principal', side_effect=recuperado):
                self.assertTrue(V.processar(self.issue, None))
            with patch.object(R, 'principal') as chamada:
                self.assertTrue(V.processar(self.issue, None))
                chamada.assert_not_called()
        self.assertEqual(sum(C.comentario_e_resposta_final(c) for c in self.cs), 1)

    def test_so_anuncia_fila_se_persistiu_ou_ja_existia(self):
        with patch.object(C, 'fila_respostas_adicionar', return_value=False):
            with patch.object(C, 'fila_respostas_carregar', return_value=[]):
                with self.assertRaisesRegex(RuntimeError, 'persistir'):
                    R.garantir_pendencia(42, 'q', 'a42')
            with patch.object(C, 'fila_respostas_carregar', return_value=[{'numero':42, 'marca':'a42'}]):
                R.garantir_pendencia(42, 'q', 'a42')

    def test_fila_indisponivel_nao_vira_vazia(self):
        with patch.object(C, 'gh', side_effect=RuntimeError('HTTP 503')):
            with self.assertRaises(RuntimeError):
                C.fila_respostas_adicionar(42, 'q', 'a42')

    def test_fila_corrompida_nao_e_sobrescrita(self):
        for texto in ['{', '{}', '[1]']:
            with self.subTest(texto=texto), patch.object(C, 'gh', return_value={'content':base64.b64encode(texto.encode()).decode()}), patch.object(C, 'escrever_remoto') as escrever:
                with self.assertRaises((RuntimeError, ValueError)):
                    C.fila_respostas_adicionar(42, 'q', 'a42')
                escrever.assert_not_called()

    def test_fila_ausente_404_e_vazia(self):
        with patch.object(C, 'gh', side_effect=RuntimeError('GitHub API → HTTP 404: ausente')):
            self.assertEqual(C.fila_respostas_carregar(), [])

    def test_contrato_final_nao_certifica_trabalho_externo(self):
        c = self.comentario('resposta textual <!--resp:a42-->')
        self.assertTrue(C.comentario_e_resposta_final(c))
        # É somente entrega de resposta. Não criamos estado "trabalho concluído".
        self.assertNotIn('trabalho_concluido', c)


if __name__ == '__main__':
    unittest.main(verbosity=2)
