# -*- coding: utf-8 -*-
"""Contrato do instrumento de espera: parear sem inventar e recusar resposta órfã."""
import unittest
import tempo_resposta as T

DONO = T.DONO


def c(t, quem, corpo=""):
    return {"created_at": t, "user": {"login": quem}, "body": corpo, "_numero": 1}


class Pareamento(unittest.TestCase):
    def test_pergunta_seguida_de_resposta(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "faz isso"),
                               c("2026-11-04T10:10:00Z", DONO, "🤖 feito")])
        self.assertEqual(len(pares), 1)
        self.assertEqual(pares[0][0], 600)

    def test_resposta_orfã_nao_conta(self):
        self.assertEqual(T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "🤖 falei sozinha")]), [])

    def test_marca_invisivel_tambem_e_resposta(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "pergunta"),
                               c("2026-11-04T10:00:02Z", DONO, "texto <!--resp:a1-->")])
        self.assertEqual(pares[0][0], 2)

    def test_fala_de_estranho_nao_abre_pergunta(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", "estranho", "oi"),
                               c("2026-11-04T10:05:00Z", DONO, "🤖 respondi")])
        self.assertEqual(pares, [])

    def test_uma_resposta_serve_de_espera_para_as_duas_perguntas(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "a"),
                               c("2026-11-04T10:01:00Z", DONO, "b"),
                               c("2026-11-04T10:02:00Z", DONO, "🤖 ok"),
                               c("2026-11-04T10:09:00Z", DONO, "🤖 ok2")])
        self.assertEqual([p[0] for p in pares], [120, 60])

    def test_pergunta_depois_da_ultima_resposta_nao_e_medida(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "a"),
                               c("2026-11-04T10:01:00Z", DONO, "b"),
                               c("2026-11-04T10:02:00Z", DONO, "🤖 ok"),
                               c("2026-11-04T10:30:00Z", DONO, "ainda esperando")])
        self.assertEqual([p[0] for p in pares], [120, 60])

    def test_ordem_de_entrada_nao_importa(self):
        pares = T.pareamentos([c("2026-11-04T10:10:00Z", DONO, "🤖 ok"),
                               c("2026-11-04T10:00:00Z", DONO, "pergunta")])
        self.assertEqual(pares[0][0], 600)


class Resumo(unittest.TestCase):
    def test_sem_pares_nao_inventa_numero(self):
        s = T.resumo([])
        self.assertEqual(s["pares"], 0)
        self.assertIsNone(s["mediana_s"])

    def test_mediana_de_lista_par(self):
        s = T.resumo([(60, 1, None, None), (120, 1, None, None),
                      (600, 1, None, None), (900, 1, None, None)])
        self.assertEqual(s["mediana_s"], 360)

    def test_mediana_de_lista_impar_e_contagem_de_dez_minutos(self):
        s = T.resumo([(60, 1, None, None), (600, 1, None, None), (3600, 1, None, None)])
        self.assertEqual(s["mediana_s"], 600)
        self.assertEqual(s["dentro_de_10min"], 2)
        self.assertEqual(s["pior_s"], 3600)

    def test_um_par_so_vira_mediana_dele_mesmo(self):
        s = T.resumo([(42, 1, None, None)])
        self.assertEqual((s["mediana_s"], s["media_s"], s["pior_s"]), (42, 42, 42))


class DaCasa(unittest.TestCase):
    """O login é o mesmo do dono: separar a casa da pessoa é por conteúdo, não por autor."""

    def test_boletim_da_casa_nao_e_pergunta(self):
        for corpo in ("🤖 **Assistente Rebocl**\n\nTudo em ordem",
                      "🌅 **Turno autônomo 02/11**\n\n**Missão de hoje:** x",
                      "🌙 **Sonho da noite**\n\ntexto",
                      "algo <!--robo:abc-->",
                      "resposta <!--resp:a1-->"):
            self.assertTrue(T.da_casa(corpo), corpo)

    def test_pergunta_de_gente_continua_pergunta(self):
        for corpo in ("perfeito, continue, resolva", "e o vídeo?", ""):
            self.assertFalse(T.da_casa(corpo), corpo)

    def test_predicado_e_subconjunto_do_varrer(self):
        """Se a varredura trata como casa, o instrumento também precisa tratar."""
        import varrer
        amostras = ["🤖 **Assistente Rebocl**\n\nTudo em ordem",
                    "🌅 **Turno autônomo 02/11**\n\n**Missão de hoje:** x _(🤖 eu acordei sozinha hoje · )",
                    "🌙 **Sonho da noite**\n\n_(🤖 eu acordei sozinha hoje · )",
                    "corpo com <!--robo:xyz--> no meio",
                    "corpo com <!--resp:abc-->",
                    "@reboclbrank-max — aviso automático do assistente.\n\nqualquer\n\nPara receber também no Telegram (grátis), veja o passo a passo no COMECE-AQUI._",
                    "perfeito, continue, resolva",
                    "texto comum sem marca"]
        for corpo in amostras:
            if varrer._do_robo(corpo):
                self.assertTrue(T.da_casa(corpo), corpo)

    def test_mensagem_da_casa_nao_abre_espera(self):
        pares = T.pareamentos([c("2026-11-04T10:00:00Z", DONO, "🤖 boletim"),
                               c("2026-11-04T14:00:00Z", DONO, "🤖 outro boletim")])
        self.assertEqual(pares, [])

class Conversa(unittest.TestCase):
    def test_resposta_de_outra_conversa_nao_serve(self):
        a = c("2026-11-04T10:00:00Z", DONO, "pergunta"); a["_numero"] = 17
        b = c("2026-11-04T10:05:00Z", DONO, "🤖 falei em outra conversa"); b["_numero"] = 116
        self.assertEqual(T.pareamentos([a, b]), [])

    def test_cada_conversa_espera_a_propria_resposta(self):
        a = c("2026-11-04T10:00:00Z", DONO, "p1"); a["_numero"] = 17
        b = c("2026-11-04T10:05:00Z", DONO, "🤖 r no 116"); b["_numero"] = 116
        d = c("2026-11-04T12:00:00Z", DONO, "🤖 r no 17"); d["_numero"] = 17
        pares = T.pareamentos([a, b, d])
        self.assertEqual([(p[0], p[1]) for p in pares], [(7200, 17)])

class Janela(unittest.TestCase):
    def test_comentario_antigo_em_conversa_ativa_fica_fora(self):
        """O caso real: #17 mexeu hoje, mas a mensagem tem 5 dias — não é espera de hoje."""
        import datetime
        agora = datetime.datetime.now(datetime.timezone.utc)
        antigo = (agora - datetime.timedelta(days=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        recente = (agora - datetime.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        agora_s = agora.strftime('%Y-%m-%dT%H:%M:%SZ')
        pares = T.pareamentos([c(antigo, DONO, "pergunta velha"),
                               c(recente, DONO, "🤖 resposta de agora"),
                               c(recente, DONO, "pergunta de agora"),
                               c(agora_s, DONO, "🤖 resposta")])
        # sem janela, a pergunta velha também pareia; com a janela, some
        self.assertEqual(len(pares), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
