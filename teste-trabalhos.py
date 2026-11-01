#!/usr/bin/env python3
import base64
import copy
import json
import unittest
from unittest.mock import patch
import comum as C
import trabalhos as T


class Trabalhos(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.writes = 0
        def gh(method, path, data=None):
            path = path.split('/contents/')[1]
            if method == 'GET':
                if path not in self.store:
                    raise RuntimeError('HTTP 404')
                return copy.deepcopy(self.store[path])
            antigo = self.store.get(path)
            if antigo and data.get('sha') != antigo['sha']:
                raise RuntimeError('HTTP 409 conflito')
            self.writes += 1
            info = {'content': data['content'], 'sha': f'sha{self.writes}'}
            self.store[path] = info
            return {'content': {'sha': info['sha']}}
        for p in [patch.object(C, 'gh', gh), patch.object(C, '_gravar_local_memoria', return_value=True)]:
            p.start(); self.addCleanup(p.stop)

    def chamar(self, **dados):
        return json.loads(C.executar_ferramenta('TRABALHO', json.dumps(dados)))

    def criar(self):
        return self.chamar(acao='criar', objetivo='Preparar relatório controlado', etapas=['Pesquisar', 'Redigir'])

    def evidencia(self, path='MEMORIA/entregas/prova.md', body='conteúdo verificável', sha='blob1'):
        self.store[path] = {'content': base64.b64encode(body.encode()).decode(), 'sha': sha}
        return path

    def test_criar_e_recuperar_depois(self):
        r = self.criar()
        self.assertEqual(r['estado'], 'planejado')
        self.assertEqual(self.chamar(acao='status', id=r['id'])['objetivo'], r['objetivo'])
        self.assertEqual(len(r['etapas']), 2)

    def test_nao_entrega_sem_evidencias(self):
        r = self.criar()
        with self.assertRaisesRegex(ValueError, 'sem evidência'):
            self.chamar(acao='entregar', id=r['id'], resultado='pronto')
        self.assertEqual(self.chamar(acao='status', id=r['id'])['estado'], 'planejado')

    def test_bloqueio_e_retomada_preservam_etapas(self):
        r = self.criar()
        b = self.chamar(acao='bloquear', id=r['id'], motivo='serviço indisponível')
        self.assertEqual(b['estado'], 'bloqueado')
        b = self.chamar(acao='retomar', id=r['id'])
        self.assertEqual(b['estado'], 'em_execucao')
        self.assertEqual(b['etapas'], r['etapas'])

    def test_entrega_para_revisao_com_arquivos(self):
        r = self.criar(); path = self.evidencia()
        for n in [1, 2]:
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=n, arquivo=path)
        r = self.chamar(acao='entregar', id=r['id'], resultado='relatório disponível')
        self.assertEqual(r['estado'], 'entregue_para_revisao')
        self.assertNotEqual(r['estado'], 'concluido')
        with self.assertRaises(ValueError):
            self.chamar(acao='retomar', id=r['id'])

    def test_evidencia_modificada_impede_entrega(self):
        r = self.criar(); path = self.evidencia()
        for n in [1, 2]:
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=n, arquivo=path)
        self.store[path]['sha'] = 'outro-blob'
        with self.assertRaisesRegex(ValueError, 'mudou'):
            self.chamar(acao='entregar', id=r['id'], resultado='pronto')

    def test_evidencia_ausente_ou_vazia(self):
        r = self.criar()
        with self.assertRaises(RuntimeError):
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, arquivo='MEMORIA/ausente.md')
        path = self.evidencia(body='')
        with self.assertRaises(ValueError):
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, arquivo=path)

    def test_nao_aceita_caminho_externo_ou_traversal(self):
        r = self.criar()
        for path in ['https://exemplo.com', '../MEMORIA/x', 'MEMORIA/../x', 'MEMORIA/x?ref=y']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, arquivo=path)

    def test_conflito_nao_sobrescreve(self):
        r = self.criar()
        antigo, sha = T.carregar(r['id'])
        self.chamar(acao='bloquear', id=r['id'], motivo='bloqueio novo')
        with self.assertRaisesRegex(RuntimeError, '409'):
            T.salvar(antigo, sha)
        self.assertEqual(self.chamar(acao='status', id=r['id'])['bloqueio'], 'bloqueio novo')

    def test_rejeita_ids_e_planos_invalidos(self):
        for id in ['../arquivo', 'inventado', None]:
            with self.assertRaises(ValueError):
                self.chamar(acao='status', id=id)
        with self.assertRaises(ValueError):
            self.chamar(acao='criar', objetivo='teste', etapas=[])

    def test_modelo_pode_produzir_arquivo_sem_precriacao_humana(self):
        r = self.criar()
        r = self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, conteudo='Resultado produzido pelo modelo')
        ev = r['etapas'][0]['evidencia']
        self.assertIn('trabalho-'+r['id'], ev['arquivo'])
        self.assertEqual(base64.b64decode(self.store[ev['arquivo']]['content']).decode(), 'Resultado produzido pelo modelo\n')

    def test_arquivo_preexistente_diferente_nao_e_sobrescrito(self):
        r = self.criar()
        path = f'MEMORIA/entregas/trabalho-{r["id"]}/etapa-1.md'
        self.evidencia(path=path, body='prova anterior', sha='blob-anterior')
        with self.assertRaisesRegex(ValueError, 'diverge'):
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, conteudo='alterar prova')
        self.assertEqual(self.store[path]['sha'], 'blob-anterior')

    def test_reentrada_apos_arquivo_antes_checkpoint_aceita_mesmo_conteudo(self):
        r = self.criar()
        path = T.gravar_entrega(r['id'], 1, 'conteúdo estável')
        sha = self.store[path]['sha']
        r = self.chamar(acao='registrar_etapa', id=r['id'], etapa=1, conteudo='conteúdo estável')
        self.assertEqual(r['etapas'][0]['evidencia']['sha_blob'], sha)

    def test_recibo_conferido_aparece_mesmo_com_texto_candidato_descartado(self):
        r = self.criar(); path = self.evidencia()
        for n in [1, 2]:
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=n, arquivo=path)
        r = self.chamar(acao='entregar', id=r['id'], resultado='relatório para revisão')
        usos = []
        C.rastrear_entrega_trabalho('TRABALHO', json.dumps(r), usos)
        recibo = C.anexar_recibos_trabalho('Texto original vencedor', usos)
        self.assertIn(r['id'], recibo)
        self.assertIn(path, recibo)
        self.assertIn('Texto original vencedor', recibo)
        self.assertIn('conferidos', recibo)

    def test_recibo_nao_confirma_evidencia_que_mudou(self):
        r = self.criar(); path = self.evidencia()
        for n in [1, 2]:
            self.chamar(acao='registrar_etapa', id=r['id'], etapa=n, arquivo=path)
        r = self.chamar(acao='entregar', id=r['id'], resultado='relatório para revisão')
        self.store[path]['sha'] = 'novo'
        texto = C.anexar_recibos_trabalho('resposta', ['recibo-trabalho:'+r['id']])
        self.assertIn('não confirmo', texto)
        self.assertNotIn('Arquivos conferidos', texto)

    def test_alegacao_textual_nao_gera_recibo(self):
        usos = []
        C.rastrear_entrega_trabalho('TRABALHO', 'Eu concluí tudo', usos)
        self.assertEqual(usos, [])

    def test_queda_entre_arquivo_e_checkpoint_recupera_sem_sobrescrever(self):
        with T.contexto_mensagem(42,'a42','pedido de teste'):
            r=self.criar()
            with patch.object(T,'salvar',side_effect=RuntimeError('queda antes checkpoint')):
                with self.assertRaisesRegex(RuntimeError,'queda'):
                    self.chamar(acao='registrar_etapa',id=r['id'],etapa=1,conteudo='resultado salvo antes da queda')
        with T.contexto_mensagem(42,'a42','pedido de teste'):
            recuperado=self.criar()
            self.assertEqual(recuperado['id'],r['id'])
            self.assertEqual(recuperado['etapas'][0]['estado'],'pendente')
            self.assertIn('arquivo salvo sem checkpoint',T.instrucoes_da_origem())
            inspecao=self.chamar(acao='inspecionar_etapa',id=r['id'],etapa=1)
            self.assertEqual(inspecao['conteudo'],'resultado salvo antes da queda\n')
            self.assertFalse(inspecao['checkpoint'])
            novo=self.chamar(acao='registrar_etapa',id=r['id'],etapa=1,arquivo=inspecao['arquivo'],sha_esperado=inspecao['sha_esperado'])
            self.assertEqual(novo['etapas'][0]['evidencia']['sha_blob'],inspecao['sha_esperado'])
            self.assertEqual(self.store[inspecao['arquivo']]['sha'],inspecao['sha_esperado'])
            self.assertEqual(len([p for p in self.store if p.startswith('MEMORIA/trabalhos/')]),1)

    def test_inspecionar_e_somente_leitura(self):
        r=self.criar();T.gravar_entrega(r['id'],1,'rascunho recuperável')
        antes=self.writes
        v=self.chamar(acao='inspecionar_etapa',id=r['id'],etapa=1)
        self.assertTrue(v['disponivel']);self.assertFalse(v['checkpoint'])
        self.assertEqual(antes,self.writes)
        self.assertEqual(self.chamar(acao='status',id=r['id'])['etapas'][0]['estado'],'pendente')

    def test_artefato_mudou_apos_inspecao_nao_registra_versao_diferente(self):
        r=self.criar();T.gravar_entrega(r['id'],1,'rascunho')
        v=self.chamar(acao='inspecionar_etapa',id=r['id'],etapa=1)
        self.store[v['arquivo']]['sha']='versao-outra'
        with self.assertRaisesRegex(ValueError,'mudou'):
            self.chamar(acao='registrar_etapa',id=r['id'],etapa=1,arquivo=v['arquivo'],sha_esperado=v['sha_esperado'])
        self.assertEqual(self.chamar(acao='status',id=r['id'])['etapas'][0]['estado'],'pendente')

    def test_recuperacao_exige_sha_lido(self):
        r=self.criar();path=T.gravar_entrega(r['id'],1,'rascunho')
        with self.assertRaisesRegex(ValueError,'sha_esperado'):
            self.chamar(acao='registrar_etapa',id=r['id'],etapa=1,arquivo=path)

    def test_artefato_ainda_nao_criado_e_ausente_sem_checkpoint(self):
        r=self.criar();v=self.chamar(acao='inspecionar_etapa',id=r['id'],etapa=1)
        self.assertFalse(v['disponivel']);self.assertFalse(v['checkpoint'])

    def test_erro_de_consulta_nao_e_artefato_ausente(self):
        r=self.criar()
        with patch.object(C,'gh',side_effect=RuntimeError('HTTP 503')):
            with self.assertRaises(RuntimeError):
                T.inspecionar_etapa(r,1)

    def test_marcador_e_roteador_estao_ligados(self):
        dado = json.dumps({'acao':'criar', 'objetivo':'teste', 'etapas':['validar']})
        achado = C.RE_FERRAMENTA.search('[[TRABALHO: '+dado+']]')
        self.assertEqual(achado.group(1), 'TRABALHO')
        r = json.loads(C.executar_ferramenta(*achado.groups()))
        self.assertEqual(r['estado'], 'planejado')


if __name__ == '__main__':
    unittest.main(verbosity=2)
