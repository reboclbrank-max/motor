"""Barreira offline da medição de entrega do agendador — sem rede e sem token.

O instrumento só vale se a conta dele estiver certa: é ela que vai dizer à casa quais relés
estão famintos. Aqui a agenda é testada em casos conhecidos, e a classificação em fronteiras.
"""
import importlib.util
import os
import unittest

RAIZ = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("entrega", os.path.join(RAIZ, "entrega_agendador.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


class ContaDeCron(unittest.TestCase):
    def test_cada_dez_minutos(self):
        self.assertEqual(E.esperado_por_dia("*/10 * * * *"), 144)

    def test_de_hora_em_hora(self):
        self.assertEqual(E.esperado_por_dia("20 * * * *"), 24)

    def test_quatro_vezes_ao_dia(self):
        self.assertEqual(E.esperado_por_dia("25 1,7,13,19 * * *"), 4)

    def test_uma_vez_ao_dia(self):
        self.assertEqual(E.esperado_por_dia("0 11 * * *"), 1)

    def test_de_doze_em_doze_horas(self):
        self.assertEqual(E.esperado_por_dia("45 */12 * * *"), 2)

    def test_duas_por_hora(self):
        self.assertEqual(E.esperado_por_dia("17,47 * * * *"), 48)

    def test_uma_por_semana_e_fracao(self):
        self.assertAlmostEqual(E.esperado_por_dia("30 12 * * 0"), 1 / 7.0)

    def test_cron_que_nao_se_entende_devolve_none(self):
        self.assertIsNone(E.esperado_por_dia("todo dia"))
        self.assertIsNone(E.esperado_por_dia("* * * *"))          # quatro campos
        self.assertIsNone(E.esperado_por_dia("0 0 1 * *"))        # dia do mês fixo
        self.assertAlmostEqual(E.esperado_por_dia("0 0 * * 1-5"), 5 / 7.0)   # faixa de dias


class Julgamento(unittest.TestCase):
    def test_doze_de_cento_e_quatro_e_faminto(self):
        taxa, veredito = E.julgar(104 / 2, 12, 48)     # pede 52/dia, recebeu 12 em 48 h
        self.assertEqual(veredito, "faminto")
        self.assertLess(taxa, 0.5)

    def test_no_prazo(self):
        self.assertEqual(E.julgar(1, 2, 48)[1], "no prazo")

    def test_atrasado_entre_metade_e_noventa(self):
        self.assertEqual(E.julgar(24, 30, 48)[1], "atrasado")   # previsto 48, veio 30

    def test_zero_e_morto(self):
        self.assertEqual(E.julgar(1, 0, 48)[1], "morto")

    def test_sem_cron_nao_julga(self):
        self.assertEqual(E.julgar(0, 0, 48)[1], "sem cron")


class ContaDeCampos(unittest.TestCase):
    def test_estrela(self):
        self.assertEqual(E.conta_campo("*", 24), 24)

    def test_lista_com_repeticao_conta_uma_vez(self):
        self.assertEqual(E.conta_campo("5,5,10", 60), 2)

    def test_valor_fora_do_relogio_e_recusado(self):
        self.assertIsNone(E.conta_campo("70", 60))

    def test_faixa(self):
        self.assertEqual(E.conta_campo("10-12", 24), 3)


class JulgarJanelaCurta(unittest.TestCase):
    """Zero execução só é 'morto' quando a janela comportava pelo menos uma."""

    def test_semanal_sem_amostra_nao_e_morte(self):
        self.assertEqual(E.julgar(1 / 7.0, 0, 48), (None, "sem amostra"))

    def test_semanal_que_rodou_uma_vez_esta_no_prazo(self):
        taxa, veredito = E.julgar(1 / 7.0, 1, 48)
        self.assertEqual(veredito, "no prazo")
        self.assertGreater(taxa, 1)

    def test_zero_em_janela_larga_continua_morto(self):
        self.assertEqual(E.julgar(144, 0, 48)[1], "morto")

    def test_uma_esperada_por_janela_ja_julga(self):
        self.assertEqual(E.julgar(0.75, 0, 48)[1], "morto")


if __name__ == "__main__":
    unittest.main(verbosity=2)
