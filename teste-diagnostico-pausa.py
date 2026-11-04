# -*- coding: utf-8 -*-
"""Contrato: o log do Chat precisa distinguir "pausada por revisão" de "quebrada".

Medido em 04/11/2026 no run 41766721918: a agenda de manutenção recusou por desenho
(pin do worker mudou) e o log público disse `agenda de manutenção indisponível: Revisao`
— que se lê como defeito e esconde o motivo e o que fazer. Aqui se prova a diferença.
"""
import os
import sys
import types
import unittest
from unittest.mock import patch

import varrer
import autonomia_reversivel as A


class Pausa(unittest.TestCase):
    def test_revisao_diz_pausa_e_motivo(self):
        linha = varrer.linha_de_bloqueio('agenda de manutenção', A.Revisao('Worker mudou; agenda aguarda revisão do pin, sem efeitos.'))
        self.assertEqual(linha, 'agenda de manutenção pausada por revisão: Worker mudou; agenda aguarda revisão do pin, sem efeitos.')

    def test_erro_comum_vira_indisponivel_sem_texto(self):
        linha = varrer.linha_de_bloqueio('agenda de manutenção', ValueError('conteudo-privado-do-dono'))
        self.assertEqual(linha, 'agenda de manutenção indisponível: ValueError')
        self.assertNotIn('conteudo-privado', linha)

    def test_revisao_sem_motivo_nao_fica_em_branco(self):
        self.assertIn('sem motivo declarado', varrer.linha_de_bloqueio('autoaperfeiçoamento', A.Revisao('   ')))

    def test_motivo_longo_e_cortado(self):
        linha = varrer.linha_de_bloqueio('agenda de manutenção', A.Revisao('x' * 400))
        self.assertLessEqual(len(linha), len('agenda de manutenção pausada por revisão: ') + 120)

    def test_segredo_nao_vaza_no_log_publico(self):
        for texto in ('falhou com ghp_' + 'A' * 30, 'sk-' + 'b' * 40, 'use github_pat_' + 'C' * 25):
            linha = varrer.linha_de_bloqueio('agenda de manutenção', A.Revisao(texto))
            self.assertIn('[omitido]', linha)
            self.assertNotIn('ghp_', linha)
            self.assertNotIn('sk-', linha)
            self.assertNotIn('github_pat_', linha)

    def test_main_loga_pausa_quando_a_agenda_recusa(self):
        falso = types.ModuleType('agenda_manutencao')

        def executar():
            raise A.Revisao('Worker mudou; agenda aguarda revisão do pin, sem efeitos.')

        falso.executar = executar
        outro = types.ModuleType('chat_componentes')
        outro.executar = lambda: None
        linhas = []
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
             patch.dict(sys.modules, {'agenda_manutencao': falso, 'chat_componentes': outro}), \
             patch.object(varrer.C, 'GH_TOKEN', 'x'), \
             patch.object(varrer, 'pendentes', lambda diagnostico=None: []), \
             patch.object(varrer, 'log', linhas.append):
            self.assertEqual(varrer.main(), 0)
        self.assertTrue(any(l.startswith('agenda de manutenção pausada por revisão: Worker mudou') for l in linhas), linhas)
        self.assertTrue(any('nenhuma mensagem executável pendente' in l for l in linhas), linhas)

    def test_main_loga_indisponivel_quando_a_agenda_quebra(self):
        falso = types.ModuleType('agenda_manutencao')

        def executar():
            raise KeyError('dado-privado')

        falso.executar = executar
        outro = types.ModuleType('chat_componentes')
        outro.executar = lambda: None
        linhas = []
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
             patch.dict(sys.modules, {'agenda_manutencao': falso, 'chat_componentes': outro}), \
             patch.object(varrer.C, 'GH_TOKEN', 'x'), \
             patch.object(varrer, 'pendentes', lambda diagnostico=None: []), \
             patch.object(varrer, 'log', linhas.append):
            varrer.main()
        agenda = [l for l in linhas if l.startswith('agenda de manutenção')]
        self.assertEqual(agenda, ['agenda de manutenção indisponível: KeyError'])


class Desligado(unittest.TestCase):
    """Terceiro estado: política manda não fazer nada. Antes disso, silêncio absoluto."""

    def _rodar(self, resultado_agenda, resultado_componente, eventos):
        agenda = types.ModuleType('agenda_manutencao')
        agenda.executar = lambda: resultado_agenda
        componente = types.ModuleType('chat_componentes')
        componente.executar = lambda: resultado_componente
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}), \
             patch.dict(sys.modules, {'agenda_manutencao': agenda, 'chat_componentes': componente}), \
             patch.object(varrer.C, 'GH_TOKEN', 'x'), \
             patch.object(varrer, 'pendentes', lambda diagnostico=None: []), \
             patch.object(varrer, 'log', eventos.append):
            varrer.main()
        return eventos

    def test_componente_desligado_por_politica_aparece_no_log(self):
        eventos = self._rodar({'ativo': False}, {'ativo': False}, [])
        self.assertIn('autoaperfeiçoamento desligado por política privada (ausente ou ativo=false)', eventos)
        self.assertIn('agenda de manutenção desligada por política privada (ausente ou ativo=false)', eventos)

    def test_desligado_nao_vira_indisponivel(self):
        eventos = self._rodar({'ativo': False}, {'ativo': False}, [])
        self.assertFalse([e for e in eventos if 'indisponível' in e], eventos)

    def test_sem_acao_nao_anuncia_desligado(self):
        eventos = self._rodar({'sem_acao': True}, {'sem_acao': True}, [])
        self.assertFalse([e for e in eventos if 'desligado' in e], eventos)

    def test_retorno_none_nao_quebra_o_log(self):
        eventos = self._rodar(None, None, [])
        self.assertTrue(any('nenhuma mensagem executável pendente' in e for e in eventos), eventos)


if __name__ == '__main__':
    unittest.main()
