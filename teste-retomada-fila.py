#!/usr/bin/env python3
"""Contratos offline: paginação, confirmação e retomada entre itens (sem rede)."""
import copy
import unittest
from unittest.mock import patch
import comum as C
import responder as R


def comentario(i, corpo=None, autor=None):
    return {'id': i, 'body': corpo or f'mensagem {i}',
            'user': {'login': autor or C.DONO_GITHUB}}


class Historico(unittest.TestCase):
    def test_todas_paginas_e_pular(self):
        itens = [comentario(i) for i in range(1, 206)]
        calls = []
        def gh(m, path):
            page = int(path.split('&page=')[1]); calls.append(page)
            return itens[(page-1)*100:page*100]
        with patch.object(C, 'gh', gh):
            h = C.historico_da_conversa(1, pular_id=205)
        self.assertEqual(calls, [1, 2, 3])
        self.assertEqual(len(h), 204)
        self.assertEqual(h[-1]['content'], 'mensagem 204')

    def test_autoria_resposta_mesmo_login(self):
        with patch.object(C, 'gh', return_value=[comentario(1, C.ASSINATURA+'\nresposta')]):
            self.assertEqual(C.historico_da_conversa(1)[0]['role'], 'assistant')

    def test_marca_pagina_dois_e_estranho(self):
        itens = [comentario(i) for i in range(100)]
        itens += [comentario(101, C.ASSINATURA+'\nOK <!--resp:c9-->')]
        with patch.object(C, 'gh', side_effect=[itens[:100], itens[100:]]):
            self.assertTrue(R.ja_respondida(1, 'c9'))
        with patch.object(C, 'gh', return_value=[comentario(1, C.ASSINATURA+' <!--resp:c9-->', 'estranho')]):
            self.assertFalse(R.ja_respondida(1, 'c9'))

    def test_erro_nao_e_conversa_vazia(self):
        with patch.object(C, 'gh', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'nao_observaveis'):
                R.ja_respondida(1, 'c9')

    def test_pagina_repetida_nao_loopa(self):
        page = [comentario(i) for i in range(100)]
        with patch.object(C, 'gh', return_value=page) as gh:
            with self.assertRaisesRegex(RuntimeError, 'sem_progresso'):
                C.historico_da_conversa(1)
            self.assertEqual(gh.call_count, 2)


class Retomada(unittest.TestCase):
    def setUp(self):
        self.fila = [{'numero': i, 'texto': f'q{i}', 'marca': f'c{i}'} for i in range(1, 6)]
        self.entregues = set()
        self.publicacoes = []
        self.checkpoints = []
        def salvar(itens):
            self.fila = copy.deepcopy(itens)
            self.checkpoints.append(copy.deepcopy(itens))
            return True
        def publicar(n, t, m, **kw):
            self.publicacoes.append(m)
            self.entregues.add(m)
        funcs = [patch.object(C, 'gh', side_effect=RuntimeError('HTTP 404')),
                 patch.object(C, 'fila_respostas_carregar', lambda: copy.deepcopy(self.fila)),
                 patch.object(C, 'fila_respostas_salvar', salvar),
                 patch.object(R, 'ja_respondida', lambda n, m: m in self.entregues),
                 patch.object(R, 'responder', publicar),
                 patch.object(C, 'historico_da_conversa', lambda n: []),
                 patch.object(C, 'responder_com_ferramentas', return_value=('ok', 'teste', [], None)),
                 patch.object(C, 'registrar_conversa', return_value=True),
                 patch.object(C, 'registrar_resposta_cache', return_value=True)]
        for p in funcs:
            p.start(); self.addCleanup(p.stop)

    def test_cinco_entregas_cinco_checkpoints(self):
        R.drenar_fila_respostas()
        self.assertEqual(len(self.publicacoes), 5)
        self.assertEqual([len(x) for x in self.checkpoints], [4, 3, 2, 1, 0])

    def test_interrupcao_e_reentrada_sem_repetir_primeiro(self):
        original = R.responder
        def falha(n, t, m, **kw):
            if m == 'c2':
                raise RuntimeError('interrupcao simulada')
            original(n, t, m, **kw)
        with patch.object(R, 'responder', falha):
            with self.assertRaisesRegex(RuntimeError, 'simulada'):
                R.drenar_fila_respostas()
        self.assertEqual(self.fila[0]['marca'], 'c2')
        R.drenar_fila_respostas()
        self.assertEqual(self.publicacoes, ['c1', 'c2', 'c3', 'c4', 'c5'])
        self.assertEqual(self.fila, [])

    def test_entrega_nao_confirmada_preserva(self):
        with patch.object(R, 'responder', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'entrega nao confirmada'):
                R.drenar_fila_respostas()
        self.assertEqual(len(self.fila), 5)

    def test_checkpoint_falhou_reentrada_confere_marca(self):
        with patch.object(C, 'fila_respostas_salvar', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'checkpoint nao confirmado'):
                R.drenar_fila_respostas()
        self.assertEqual(len(self.fila), 5)
        R.drenar_fila_respostas()
        self.assertEqual(self.publicacoes.count('c1'), 1)
        self.assertEqual(self.fila, [])

    def test_prazo_preserva_restantes(self):
        with patch.object(R.time, 'monotonic', side_effect=[0, 0, 181]):
            R.drenar_fila_respostas()
        self.assertEqual(self.publicacoes, ['c1'])
        self.assertEqual(len(self.fila), 4)

    def test_motor_falhou_preserva_restantes(self):
        with patch.object(C, 'responder_com_ferramentas', side_effect=[('ok','M',[],None), (None,None,[],'falha')]):
            R.drenar_fila_respostas()
        self.assertEqual(len(self.fila), 4)

    def test_item_invalido_nao_e_apagado(self):
        self.fila.insert(0, {'texto': 'invalido'})
        R.drenar_fila_respostas()
        self.assertEqual(self.fila, [{'texto': 'invalido'}])


if __name__ == '__main__':
    unittest.main(verbosity=2)
