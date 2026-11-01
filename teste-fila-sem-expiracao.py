import unittest
from unittest.mock import patch
import varrer as V

class FilaTest(unittest.TestCase):
    def issue(self,n):return {'number':n,'user':{'login':V.C.DONO_GITHUB},'updated_at':'2000-01-01T00:00:00Z'}
    def test_antiga_nao_expira(self):
        with patch.object(V.C,'gh',side_effect=[[self.issue(1)],[]]),patch.object(V,'JANELA_HORAS',0):
            self.assertEqual(len(V.pendentes()),1)
    def test_pagina_dois(self):
        def gh(m,p,*a):
            if '/comments?' in p:return []
            if '&page=1' in p:return [self.issue(n) for n in range(100)]
            return [self.issue(101)]
        with patch.object(V.C,'gh',side_effect=gh),patch.object(V,'JANELA_HORAS',0),patch.object(V,'POR_PAGINA',100):
            self.assertEqual(len(V.pendentes()),101)
    def test_sem_teto_tres(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V,'MAX_POR_RODADA',0),patch.object(V,'pendentes',return_value=[(self.issue(n),None) for n in range(5)]):
            feitas=[];pedidos=[]
            self.assertEqual(V.main(lambda i,c:feitas.append(i) or True,lambda m:pedidos.append(m) or True),0)
            self.assertEqual(len(feitas),5);self.assertEqual(pedidos,[])
    def test_handover_por_tempo(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V,'MAX_POR_RODADA',0),patch.object(V,'pendentes',return_value=[(self.issue(n),None) for n in range(5)]),patch.object(V.time,'monotonic',side_effect=[0,500]):
            feitas=[];pedidos=[]
            self.assertEqual(V.main(lambda i,c:feitas.append(i) or True,lambda m:pedidos.append(m) or True),0)
            self.assertEqual(len(feitas),1);self.assertEqual(pedidos,['faltam 4'])
    def test_sem_progresso_nao_encadeia(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V,'pendentes',return_value=[(self.issue(1),None)]):
            with patch.object(V,'acordar_de_novo') as d:
                self.assertEqual(V.main(lambda *a:False),1);d.assert_not_called()
    def test_dispatch_falha_visivel(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V,'MAX_POR_RODADA',1),patch.object(V,'pendentes',return_value=[(self.issue(n),None) for n in range(2)]):
            self.assertEqual(V.main(lambda *a:True,lambda *a:False),2)
    def test_pagina_ilegivel_nao_finge_vazia(self):
        with patch.object(V.C,'GH_TOKEN','fake'),patch.object(V.C,'gh',return_value=None):
            self.assertEqual(V.main(),2)

if __name__=='__main__':unittest.main()
