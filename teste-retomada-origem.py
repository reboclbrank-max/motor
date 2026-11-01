#!/usr/bin/env python3
"""Retomada da mesma mensagem sem ID fornecido pelo usuário. API/modelo simulados."""
import base64
import copy
import json
import unittest
import subprocess
import tempfile
from pathlib import Path
import textwrap
from unittest.mock import patch
import comum as C
import responder as R
import trabalhos as T


class RetomadaOrigem(unittest.TestCase):
    def setUp(self):
        self.store = {}
        self.comments = []
        self.n = 0
        self.evento = {'numero':42, 'marca':'a42', 'texto':'produza o relatório', 'origem':'nova conversa'}
        def gh(method, path, dados=None):
            if '/comments?' in path:
                return copy.deepcopy(self.comments)
            if method == 'POST' and path.endswith('/comments'):
                c = {'id':len(self.comments)+1,'body':dados['body'],'user':{'login':C.DONO_GITHUB}}
                self.comments.append(c); return c
            if '/contents/' not in path:
                raise AssertionError('rota não simulada: '+path)
            path = path.split('/contents/')[1]
            if method == 'GET':
                if path not in self.store:
                    raise RuntimeError('GitHub API → HTTP 404: ausente')
                return copy.deepcopy(self.store[path])
            if method != 'PUT':
                raise AssertionError('método inesperado')
            anterior = self.store.get(path)
            if anterior and anterior['sha'] != dados.get('sha'):
                raise RuntimeError('HTTP 409 conflito')
            self.n += 1
            self.store[path] = {'sha':f'sha{self.n}', 'content':dados['content']}
            return {'content':{'sha':f'sha{self.n}'}}
        for p in [patch.object(C,'gh',gh), patch.object(C,'_gravar_local_memoria'),
                  patch.object(R,'do_evento',return_value=self.evento)]:
            p.start(); self.addCleanup(p.stop)

    def tool(self, **dados):
        return json.loads(T.executar(json.dumps(dados)))

    def criar(self):
        return self.tool(acao='criar', objetivo='relatório interno', etapas=['analisar','redigir'])

    def preparar(self, terminar=False):
        with T.contexto_mensagem(42, 'a42', self.evento['texto']):
            r = self.criar()
            self.tool(acao='registrar_etapa', id=r['id'], etapa=1, conteudo='análise já executada')
            if terminar:
                self.tool(acao='registrar_etapa', id=r['id'], etapa=2, conteudo='relatório final')
                self.tool(acao='entregar', id=r['id'], resultado='arquivos disponíveis')
        return r

    def test_criar_duas_vezes_mesma_origem_preserva_id_e_plano(self):
        with T.contexto_mensagem(42,'a42'):
            a = self.criar()
            b = self.tool(acao='criar',objetivo='outro plano não deve sobrescrever',etapas=['nova'])
        self.assertEqual(a,b)
        self.assertEqual(len(self.store),1)

    def test_mensagem_diferente_na_mesma_issue_nao_colide(self):
        with T.contexto_mensagem(42,'a42'): a=self.criar()
        with T.contexto_mensagem(42,'c123'): b=self.criar()
        self.assertNotEqual(a['id'],b['id'])

    def test_contexto_restaura_mesmo_apos_excecao(self):
        self.assertIsNone(T.id_da_origem())
        with T.contexto_mensagem(42,'a42'):
            id1=T.id_da_origem()
            with self.assertRaises(RuntimeError):
                with T.contexto_mensagem(43,'a43'):
                    raise RuntimeError('interrupção')
            self.assertEqual(T.id_da_origem(),id1)
        self.assertIsNone(T.id_da_origem())

    def test_interrupcao_apos_etapa_um_reentrada_sem_refazer(self):
        r=self.preparar(); prova1=copy.deepcopy(self.store[f'MEMORIA/entregas/trabalho-{r["id"]}/etapa-1.md'])
        def modelo(historico, numero):
            existente=T.recuperar_da_origem()
            self.assertEqual(existente['id'],r['id'])
            self.assertEqual(existente['etapas'][0]['estado'],'evidencia_registrada')
            self.assertIn(r['id'],T.instrucoes_da_origem())
            self.tool(acao='registrar_etapa',id=r['id'],etapa=2,conteudo='relatório produzido após retomada')
            self.tool(acao='entregar',id=r['id'],resultado='entrega retomada')
            return 'finalizado','modelo simulado',[],None
        with patch.object(C,'responder_com_ferramentas',side_effect=modelo) as m:
            self.assertEqual(R.principal(),0)
            self.assertEqual(R.principal(),0)
            self.assertEqual(m.call_count,1)
        self.assertEqual(len(self.comments),1)
        self.assertIn(r['id'],self.comments[0]['body'])
        self.assertEqual(prova1,self.store[f'MEMORIA/entregas/trabalho-{r["id"]}/etapa-1.md'])
        self.assertEqual(len([p for p in self.store if p.startswith('MEMORIA/trabalhos/')]),1)

    def test_terminou_mas_nao_publicou_recupera_sem_modelo(self):
        r=self.preparar(terminar=True)
        with patch.object(C,'responder_com_ferramentas') as m:
            self.assertEqual(R.principal(),0)
            m.assert_not_called()
        self.assertIn(r['id'],self.comments[0]['body'])
        self.assertIn('<!--resp:a42-->',self.comments[0]['body'])

    def test_modelo_diz_pronto_sem_entregar_nao_fecha_mensagem(self):
        self.preparar()
        with patch.object(C,'responder_com_ferramentas',return_value=('terminei tudo','M',[],None)),patch.object(C,'fila_respostas_adicionar',return_value=True):
            self.assertEqual(R.principal(),1)
        self.assertNotIn('<!--resp:a42-->',self.comments[0]['body'])
        self.assertIn('<!--estado:pendente-->',self.comments[0]['body'])
        self.assertNotIn('terminei tudo',self.comments[0]['body'])

    def test_mensagem_editada_nao_reexecuta_plano_antigo(self):
        self.preparar()
        with T.contexto_mensagem(42,'a42','pedido editado'):
            with self.assertRaisesRegex(ValueError,'alterada'):
                T.recuperar_da_origem()

    def test_503_nao_e_origem_vazia(self):
        with T.contexto_mensagem(42,'a42'),patch.object(C,'gh',side_effect=RuntimeError('HTTP 503')):
            with self.assertRaises(RuntimeError):
                self.criar()
        self.assertEqual(self.store,{})

    def test_fila_reserva_usa_origem_do_item_e_preserva_trabalho_incompleto(self):
        item={'numero':9,'marca':'c999','texto':'produza outro trabalho'}
        def modelo(historico,numero):
            self.assertEqual(T._ORIGEM.get()['conversa'],9)
            self.criar()
            return 'terminei','M',[],None
        with T.contexto_mensagem(42,'a42'),patch.object(C,'fila_respostas_carregar',return_value=[item]),patch.object(C,'fila_respostas_salvar') as salvar,patch.object(C,'responder_com_ferramentas',side_effect=modelo),patch.object(R,'responder') as publicar:
            R.drenar_fila_respostas()
            self.assertEqual(T._ORIGEM.get()['conversa'],42)
            salvar.assert_not_called();publicar.assert_not_called()


    def test_dois_processos_retomam_checkpoint_apos_saida_abrupta(self):
        fonte = str(Path(__file__).resolve().parent)
        script = textwrap.dedent(r'''import sys,pathlib,json,base64,os
sys.path.insert(0,sys.argv[1])
import comum as C
import trabalhos as T
import responder as R
root=pathlib.Path.cwd()
def gh(method,path,data=None):
    if '/comments?' in path:
        return json.loads((root/'comentarios.json').read_text()) if (root/'comentarios.json').exists() else []
    if method=='POST' and path.endswith('/comments'):
        old=gh('GET','/comments?')
        item={'id':len(old)+1,'body':data['body'],'user':{'login':C.DONO_GITHUB}}
        (root/'comentarios.json').write_text(json.dumps(old+[item]));return item
    arq=root/'remoto'/path.split('/contents/')[1]
    if method=='GET':
        if not arq.exists():raise RuntimeError('HTTP 404')
        body=arq.read_bytes()
        import hashlib
        return {'content':base64.b64encode(body).decode(),'sha':hashlib.sha256(body).hexdigest()}
    atual=gh('GET',path)['sha'] if arq.exists() else None
    if atual!=data.get('sha'):raise RuntimeError('HTTP 409')
    arq.parent.mkdir(parents=True,exist_ok=True);arq.write_bytes(base64.b64decode(data['content']))
    return {'content':{'sha':gh('GET',path)['sha']}}
C.gh=gh
R.do_evento=lambda:{'numero':42,'marca':'a42','texto':'pedido de teste','origem':'teste'}
def tool(**kw):return json.loads(T.executar(json.dumps(kw)))
if sys.argv[2]=='cair':
    with T.contexto_mensagem(42,'a42','pedido de teste'):
        r=tool(acao='criar',objetivo='relatório',etapas=['análise','redação'])
        tool(acao='registrar_etapa',id=r['id'],etapa=1,conteudo='análise já feita')
        (root/'id.txt').write_text(r['id'])
        os._exit(23)
def modelo(historico,numero):
    r=T.recuperar_da_origem();assert r['id']==(root/'id.txt').read_text()
    assert r['etapas'][0]['estado']=='evidencia_registrada'
    tool(acao='registrar_etapa',id=r['id'],etapa=2,conteudo='redação após reinício')
    tool(acao='entregar',id=r['id'],resultado='entrega para revisão')
    return 'feito','modelo simulado',[],None
C.responder_com_ferramentas=modelo
assert R.principal()==0
''')
        with tempfile.TemporaryDirectory() as d:
            arq=Path(d)/'worker.py';arq.write_text(script)
            a=subprocess.run(['python',str(arq),fonte,'cair'],cwd=d,capture_output=True,text=True,timeout=20)
            self.assertEqual(a.returncode,23,a.stderr)
            ident=(Path(d)/'id.txt').read_text()
            first=Path(d)/f'remoto/MEMORIA/entregas/trabalho-{ident}/etapa-1.md'
            before=first.read_bytes()
            for _ in range(2):
                b=subprocess.run(['python',str(arq),fonte,'retomar'],cwd=d,capture_output=True,text=True,timeout=20)
                self.assertEqual(b.returncode,0,b.stdout+b.stderr)
            self.assertEqual(first.read_bytes(),before)
            self.assertEqual(len(list((Path(d)/'remoto/MEMORIA/trabalhos').glob('*.json'))),1)
            comments=json.loads((Path(d)/'comentarios.json').read_text())
            self.assertEqual(len(comments),1)
            self.assertIn(ident,comments[0]['body'])


if __name__=='__main__':
    unittest.main(verbosity=2)
