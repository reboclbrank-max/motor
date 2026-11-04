# -*- coding: utf-8 -*-
"""Contrato: queda de conexão no meio da resposta não é falha definitiva — mas também não vira repetição de escrita.

Medido em 04/11/2026 (runs 41819338210 e 41845953050): UM `RemoteDisconnected` em 254 arquivos
derrubou o banco da casa e o espelho da memória. `RemoteDisconnected` e `IncompleteRead` não são
`urllib.error.URLError` — escapavam do retry, e a casa tratava uma queda de rede como defeito.
O outro lado do contrato é igualmente importante: POST/PUT nunca se repetem.
"""
import http.client
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

import comum as C
import sincronizar as S


class Resposta:
    def __init__(self, dados):
        self._dados = dados

    def read(self):
        return self._dados

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def queda():
    return http.client.RemoteDisconnected('Remote end closed connection without response')


class Base(unittest.TestCase):
    def setUp(self):
        for alvo in (C.time, S.time):
            p = patch.object(alvo, 'sleep', return_value=None)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(C, 'GH_TOKEN', 'token-de-teste')
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(S, 'TOKEN', 'token-de-teste')
        p.start()
        self.addCleanup(p.stop)


class Comum(Base):
    def seq(self, *efeitos):
        return patch.object(C.urllib.request, 'urlopen', side_effect=list(efeitos))

    def test_get_recupera_queda_de_conexao_e_devolve_json(self):
        with self.seq(queda(), Resposta(b'{"ok": 1}')) as m:
            self.assertEqual(C.gh('GET', '/x'), {'ok': 1})
        self.assertEqual(m.call_count, 2)

    def test_get_desiste_depois_de_tres_quedas(self):
        with self.seq(queda(), queda(), queda()) as m:
            with self.assertRaises(http.client.RemoteDisconnected):
                C.gh('GET', '/x')
        self.assertEqual(m.call_count, 3)

    def test_get_transitorio_500_repete_e_401_nao_repete(self):
        erro500 = urllib.error.HTTPError('u', 500, 'boom', {}, io.BytesIO(b''))
        with self.seq(erro500, Resposta(b'{"ok": 2}')) as m:
            self.assertEqual(C.gh('GET', '/x'), {'ok': 2})
        self.assertEqual(m.call_count, 2)
        erro401 = urllib.error.HTTPError('u', 401, 'no', {}, io.BytesIO(b'token-de-teste invalido'))
        with self.seq(erro401) as m:
            with self.assertRaises(RuntimeError) as ctx:
                C.gh('GET', '/x')
        self.assertEqual(m.call_count, 1)
        self.assertIn('HTTP 401', str(ctx.exception))

    def test_credencial_do_corpo_de_erro_nao_vaza(self):
        for bruto in ('ghp_' + 'A' * 30, 'sk-' + 'b' * 40, 'github_pat_' + 'C' * 25):
            erro = urllib.error.HTTPError('u', 401, 'no', {}, io.BytesIO(('recusado: ' + bruto).encode()))
            with patch.object(C.urllib.request, 'urlopen', side_effect=erro):
                with self.assertRaises(RuntimeError) as ctx:
                    C.gh('GET', '/x')
            self.assertIn('[omitido]', str(ctx.exception))
            self.assertNotIn(bruto[:12], str(ctx.exception))
        self.assertIn('[omitido]', C.sem_segredo('ghp_' + 'Z' * 30))

    def test_escrita_nunca_e_repetida(self):
        for metodo in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.seq(queda()) as m:
                with self.assertRaises(http.client.RemoteDisconnected):
                    C.gh(metodo, '/x', {'a': 1})
            self.assertEqual(m.call_count, 1, metodo)


class Sincronizar(Base):
    def seq(self, *efeitos):
        return patch.object(S.urllib.request, 'urlopen', side_effect=list(efeitos))

    def test_blob_recupera_queda_de_conexao(self):
        with self.seq(queda(), Resposta(b'{"sha": "abc"}')) as m:
            self.assertEqual(S._http('GET', '/repos/dono/mem/git/blobs/abc'), {'sha': 'abc'})
        self.assertEqual(m.call_count, 2)

    def test_blob_desiste_depois_de_tres_quedas(self):
        with self.seq(queda(), queda(), queda()) as m:
            with self.assertRaises(http.client.RemoteDisconnected):
                S._http('GET', '/x')
        self.assertEqual(m.call_count, 3)

    def test_escrita_da_memoria_nao_e_repetida(self):
        with self.seq(queda()) as m:
            with self.assertRaises(http.client.RemoteDisconnected):
                S._http('PUT', '/x', {'a': 1})
        self.assertEqual(m.call_count, 1)

    def test_motivo_seguro_nao_imprime_conteudo(self):
        self.assertEqual(S._motivo_seguro(queda()), 'RemoteDisconnected')
        self.assertNotIn('Remote end closed', S._motivo_seguro(queda()))


if __name__ == '__main__':
    unittest.main()
