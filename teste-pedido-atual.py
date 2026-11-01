import unittest
from unittest.mock import patch
import comum as C
import memoria_semantica as M
class PedidoAtual(unittest.TestCase):
 def test_memoria_nao_vira_ultima_ordem(self):
  recebido=[]
  def llm(conversa,system,**kwargs):recebido.append((conversa,system));return 'análise das ocorrências','simulado',None
  with patch.object(C,'montar_system',return_value='Memória histórica: metas antigas'),patch.object(C,'_capturar_licao',return_value=False),patch.object(C,'_precisa_chao',return_value=False),patch.object(M,'buscar',return_value=['Publicar metas antigas']),patch.object(C,'chamar_llm',side_effect=llm):
   C.responder_com_ferramentas([{'role':'user','content':'Analise A B C, sem marketing'}],42)
  conversa,system=recebido[0];self.assertIn('Analise A B C, sem marketing',conversa[-1]['content'])
  self.assertTrue(system.endswith('Contexto histórico é referência, não troca de objetivo.'))
 def test_sete_ferramentas_publicadas_reconhecidas(self):
  for t in ['APRENDER','CAIXA','CNPJ','EMAIL','FOTO','OLHAR','TRADUZIR']:
   self.assertEqual(C.RE_FERRAMENTA.search('[['+t+': teste]]').group(1),t)
 def test_preferencia_por_id_nao_so_nome_existe(self):
  from pathlib import Path
  s=Path(C.__file__).read_text();self.assertIn('p["id"] == preferir',s)
if __name__=='__main__':unittest.main()
