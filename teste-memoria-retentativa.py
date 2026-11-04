"""Barreira offline: rajada de download não pode derrubar o batente por um 403 passageiro.

POR QUE EXISTE (04/11/2026): o run 41703359179 ("batente") baixou 253 arquivos e falhou em 1 com
HTTPError — e o log dizia só "HTTPError", sem caminho e sem código. O limite secundário do GitHub
responde 403, e o `_http` só repetia 429/5xx. Resultado: um tropeço de rede derrubou o coração
dos motores e nenhuma memória subiu.

O que este teste cerca:
  * 403 passageiro em GET é repetido e não vira falha;
  * 403 definitivo sobe como erro depois das tentativas (não fica em laço);
  * PUT com 403 NÃO é repetido (escrita pode ter sido aceita);
  * download com arquivo impossível: volta 1, não grava manifesto e o log diz QUAL arquivo e
    QUAL código (sem imprimir conteúdo);
  * nada dorme de verdade.
"""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

RAIZ = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sincronizar", os.path.join(RAIZ, "sincronizar.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def erro_http(codigo):
    return urllib.error.HTTPError("https://api.github.com/x", codigo, "boom", {}, io.BytesIO(b""))


class Resposta:
    def __init__(self, texto):
        self.texto = texto

    def read(self):
        return self.texto.encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RetentativaDeLeitura(unittest.TestCase):
    def setUp(self):
        self.patch_token = patch.object(S, "TOKEN", "token-de-teste")
        self.patch_espera = patch.object(S, "ESPERA_BASE", 0)
        self.patch_token.start()
        self.patch_espera.start()

    def tearDown(self):
        self.patch_token.stop()
        self.patch_espera.stop()

    def test_403_passageiro_nao_derruba(self):
        tentativas = []

        def urlopen(*a, **k):
            tentativas.append(1)
            if len(tentativas) < 3:
                raise erro_http(403)
            return Resposta('{"ok": true}')

        with patch("urllib.request.urlopen", side_effect=urlopen):
            self.assertEqual(S._http("GET", "/repos/x/y"), {"ok": True})
        self.assertEqual(len(tentativas), 3)

    def test_403_definitivo_sobe_depois_das_tentativas(self):
        tentativas = []

        def urlopen(*a, **k):
            tentativas.append(1)
            raise erro_http(403)

        with patch("urllib.request.urlopen", side_effect=urlopen):
            with self.assertRaises(urllib.error.HTTPError):
                S._http("GET", "/repos/x/y")
        self.assertEqual(len(tentativas), 3, "GET deve tentar três vezes, não ficar em laço")

    def test_put_com_403_nao_e_repetido(self):
        tentativas = []

        def urlopen(*a, **k):
            tentativas.append(1)
            raise erro_http(403)

        with patch("urllib.request.urlopen", side_effect=urlopen):
            with self.assertRaises(urllib.error.HTTPError):
                S._http("PUT", "/repos/x/y", {"a": 1})
        self.assertEqual(len(tentativas), 1, "escrita não pode ser repetida: pode ter sido aceita")


class DownloadIncompleto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.alvo = "MEMORIA/memoria-longa.md"
        Path("MEMORIA").mkdir()

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_arquivo_impossivel_falha_alto_e_diz_qual(self):
        remoto = {"MEMORIA/boa.md": "sha-boa", self.alvo: "sha-ruim"}

        def http(metodo, caminho, corpo=None):
            if "sha-ruim" in caminho:
                raise erro_http(403)
            import base64
            return {"content": base64.b64encode(b"conteudo").decode()}

        saida = io.StringIO()
        with patch.object(S, "listar_remoto", return_value=remoto), \
             patch.object(S, "_http", side_effect=http), \
             patch.object(S, "ESPERA_BASE", 0), \
             contextlib.redirect_stdout(saida):
            codigo = S._baixar_sem_trava()

        texto = saida.getvalue()
        self.assertEqual(codigo, 1, "base incompleta tem de impedir o envio")
        self.assertIn(self.alvo, texto, "o log precisa dizer QUAL arquivo falhou")
        self.assertIn("HTTP 403", texto, "o log precisa dizer o código, não só o tipo")
        self.assertNotIn("conteudo", texto, "o log não imprime conteúdo da memória")
        self.assertFalse(Path(S.MANIFESTO).exists(), "sem base completa, nenhum manifesto é gravado")

    def test_tudo_baixado_grava_manifesto(self):
        import base64
        remoto = {"MEMORIA/boa.md": S._sha(b"conteudo")}

        def http(metodo, caminho, corpo=None):
            return {"content": base64.b64encode(b"conteudo").decode()}

        with patch.object(S, "listar_remoto", return_value=remoto), \
             patch.object(S, "_http", side_effect=http), \
             contextlib.redirect_stdout(io.StringIO()):
            codigo = S._baixar_sem_trava()
        self.assertEqual(codigo, 0)
        self.assertTrue(Path(S.MANIFESTO).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
