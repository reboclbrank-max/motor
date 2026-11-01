"""Contexto por tarefa: entrada, retomada e fila sem publicar de verdade."""
import unittest
from contextvars import copy_context
from unittest.mock import patch
import casa
import comum as C
import responder as R
import trabalhos as T

class ContextoPedido(unittest.TestCase):
    def setUp(self):
        casa.definir_pedido('')
        self.addCleanup(casa.definir_pedido,'')
    def test_pedido_explicito_da_propria_mensagem_preservado(self):
        with T.contexto_mensagem(42,'a42','publica o ciclo'):
            with patch.object(C,'gh',return_value={}) as gh:
                self.assertIn('disparado',casa.disparar('publicar'));self.assertEqual(gh.call_count,1)
        self.assertFalse(casa.pedido_explicito())
    def test_contexto_interno_nao_herda_pedido_externo_e_restaura(self):
        with T.contexto_mensagem(42,'a42','publica o ciclo'):
            self.assertTrue(casa.pedido_explicito())
            with T.contexto_mensagem(43,'a43','apenas analise'):
                self.assertFalse(casa.pedido_explicito())
            self.assertTrue(casa.pedido_explicito())
    def test_sem_pedido_nao_herda_autorizacao(self):
        casa.definir_pedido('publica')
        with T.contexto_mensagem(42,'a42'):self.assertFalse(casa.pedido_explicito())
        self.assertTrue(casa.pedido_explicito())
    def test_excecao_restaura_contexto(self):
        casa.definir_pedido('anterior')
        with self.assertRaises(RuntimeError):
            with T.contexto_mensagem(42,'a42','publica'):
                raise RuntimeError('interrupção')
        self.assertFalse(casa.pedido_explicito())
    def test_contextos_independentes_nao_compartilham_mutacao(self):
        a,b=copy_context(),copy_context();a.run(casa.definir_pedido,'publica');b.run(casa.definir_pedido,'analise')
        self.assertTrue(a.run(casa.pedido_explicito));self.assertFalse(b.run(casa.pedido_explicito))
    def test_retomada_com_pedido_antigo_nao_dispara(self):
        casa.definir_pedido('publica o ciclo')
        reg={'id':'a'*32,'estado':'planejado'}
        def modelo(*args,**kwargs):
            self.assertIn('exige pedido',C.executar_ferramenta('PUBLICAR',''))
            return None,'simulado',[],'interrupção'
        with patch.object(C,'gh') as gh,patch.object(C,'historico_da_conversa',return_value=[]),patch.object(C,'responder_com_ferramentas',side_effect=modelo),patch.object(T,'recuperar_da_origem',return_value=reg),patch.object(R,'garantir_pendencia'),patch.object(R,'responder'):
            with T.contexto_mensagem(42,'a42','apenas analise'):
                self.assertEqual(R.retomar_trabalho_da_mensagem(42,'apenas analise','a42',reg),1)
            gh.assert_not_called()
    def test_entrada_principal_define_contexto_antes_da_rota(self):
        evento={'numero':42,'marca':'a42','texto':'apenas analise'};casa.definir_pedido('publica')
        with patch.object(R,'do_evento',return_value=evento),patch.object(R,'_principal_com_origem',side_effect=lambda d: casa.pedido_explicito()):
            self.assertFalse(R.principal())
        self.assertTrue(casa.pedido_explicito())
    def test_fila_isola_pedido_atual_e_restaura(self):
        casa.definir_pedido('publica')
        item={'numero':42,'marca':'a42','texto':'analise o relatório'}
        def modelo(*args,**kwargs):
            self.assertFalse(casa.pedido_explicito());return 'resultado','fake',[],None
        with patch.object(C,'fila_respostas_carregar',return_value=[item]),patch.object(R,'ja_respondida',side_effect=[False,True]),patch.object(C,'historico_da_conversa',return_value=[]),patch.object(C,'responder_com_ferramentas',side_effect=modelo),patch.object(T,'recuperar_da_origem',return_value=None),patch.object(R,'responder'),patch.object(C,'fila_respostas_salvar',return_value=True),patch.object(C,'registrar_conversa'),patch.object(C,'registrar_resposta_cache'):
            R.drenar_fila_respostas()
        self.assertTrue(casa.pedido_explicito())

if __name__=='__main__':unittest.main()
