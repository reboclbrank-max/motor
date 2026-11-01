import unittest,datetime,tempfile,os,json
from unittest.mock import patch
import sentinela as S, varrer as V, responder as R
class Fila(unittest.TestCase):
 def test_sentinela_usa_varredor_sem_expirar_pendente(self):
  i={'number':7,'created_at':'2020-01-01T00:00:00Z'}
  with patch.object(V,'pendentes',return_value=[(i,None)]),patch.object(S.C,'agora',return_value=datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc)):
   self.assertEqual(S.perguntas_sem_resposta({}),[{'numero':7,'comentario_id':'a7','marca':'a7'}])
 def test_leitura_falha_nao_e_fila_vazia(self):
  with patch.object(V,'pendentes',side_effect=RuntimeError('indisponível')):
   with self.assertRaises(RuntimeError):S.perguntas_sem_resposta({})
 def test_ja_entregue_marca_do_dono_nao_renasce(self):
  i={'number':7,'user':{'login':V.C.DONO_GITHUB},'body':'objetivo','created_at':'2020-01-01T00:00:00Z'};c={'id':1,'body':V.C.ASSINATURA+'\nrecibo\n<!--resp:a7-->','user':{'login':V.C.DONO_GITHUB}}
  def gh(m,p,*a):return [c] if '/comments?' in p else [i]
  with patch.object(V.C,'gh',side_effect=gh):self.assertEqual(S.perguntas_sem_resposta({}),[])
 def test_fila_historica_preservada_sem_modelo_ou_envio(self):
  with patch.object(R.C,'fila_respostas_carregar',return_value=[{'numero':85,'texto':'pedido antigo','marca':'c123'}]),patch.object(V,'revisao_historica',return_value={(85,'c123')}),patch.object(R.C,'responder_com_ferramentas') as m,patch.object(R.C,'fila_respostas_salvar') as salvar:
   R.drenar_fila_respostas();m.assert_not_called();salvar.assert_not_called()
 def test_evento_historico_ignorado_antes_de_ler_mensagem(self):
  with patch.dict(os.environ,{'REPROCESSAR_ISSUE':'85','REPROCESSAR_COMMENT':'123'}),patch.object(V,'revisao_historica',return_value={(85,'c123')}),patch.object(R.C,'gh') as gh:
   self.assertIsNone(R.do_evento());gh.assert_not_called()
 def test_ferramenta_acoes_observa_executor_real_com_evidencia(self):
  import io
  dados={'workflow_runs':[{'name':'chat','conclusion':'success','status':'completed','created_at':'2026-11-01T00:00:00Z','head_sha':'123456789','html_url':'https://github.com/dono/motor/actions/runs/1'}]}
  with patch.object(S.C.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(dados).encode())) as u:
   txt=S.C._ferramenta_acoes('chat')
  self.assertIn('/'+S.C.REPO_ROBO+'/actions/runs?',u.call_args.args[0].full_url)
  self.assertIn('12345678',txt);self.assertIn('/runs/1',txt)
 def test_escopo_bloqueia_efeitos_antes_de_qualquer_chamada(self):
  import casa,trabalhos
  pedido='<!--escopo:leitura-operacional-->\nconferir operação sem publicar'
  with trabalhos.contexto_mensagem(100,'a100',pedido),patch.object(S.C,'gh') as gh,patch.object(S.C,'_ferramenta_repo') as repo:
   for tipo,arg in [('PUBLICAR',''),('EMAIL','teste'),('DIAGNOSTICAR',''),('PLANTAR','x'),('REPO','agente/MEMORIA/segredo'),('REPO','motor/../agente'),('TRABALHO',json.dumps({'acao':'status','id':'outro'}))]:
    with self.assertRaises(PermissionError):S.C.executar_ferramenta(tipo,arg)
   gh.assert_not_called();repo.assert_not_called();self.assertIn('BLOQUEADO',casa.disparar('publicar'))
 def test_trabalho_da_origem_autorizado(self):
  import trabalhos
  with trabalhos.contexto_mensagem(100,'a100','<!--escopo:leitura-operacional-->objetivo'),patch.object(trabalhos,'executar',return_value='ok') as e:
   self.assertEqual(S.C.executar_ferramenta('TRABALHO',json.dumps({'acao':'criar','objetivo':'ler','etapas':['ler']})),'ok');e.assert_called_once()
 def test_um_dispatch_por_ciclo(self):
  from pathlib import Path
  self.assertIn('for item in pendentes[:1]:',Path(S.__file__).read_text())
if __name__=='__main__':unittest.main()
