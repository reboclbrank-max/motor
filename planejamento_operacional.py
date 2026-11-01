"""Modelo propõe fontes; controlador valida, persiste e executa só leituras.
Não é planejador universal, não concede permissão e não aceita sucesso declarado.
"""
import base64,hashlib,json,re
import comum as C
import trabalhos as T
import operacao_leitura as O
PREFIXO='<!--escopo:planejamento-operacional-->'
class Bloqueio(ValueError):pass
def eh_planejamento(pedido):
 import intencao_operacional as I
 return (I.classificar(pedido) or {}).get("modo") in ("automatico","planejamento_explicito")

def validar_fontes(fontes):
 if not isinstance(fontes,list) or not 1<=len(fontes)<=6:raise Bloqueio('quantidade_de_fontes_invalida')
 saida=[]
 for f in fontes:
  if not isinstance(f,(list,tuple)) or len(f)!=2 or not all(isinstance(v,str) for v in f):raise Bloqueio('fonte_invalida')
  tipo,arg=f
  if tipo=='REPO':
   if not re.fullmatch(r'(motor|site|chat)/[A-Za-z0-9_./-]{1,200}',arg):raise Bloqueio('repositorio_ou_caminho_nao_autorizado')
  elif tipo=='ACOES':
   if not re.fullmatch(r'[A-Za-z0-9 _()-]{0,60}',arg):raise Bloqueio('filtro_invalido')
  else:raise Bloqueio('acao_nao_autorizada')
  C._autorizar_leitura_operacional(tipo,arg)
  if [tipo,arg] not in saida:saida.append([tipo,arg])
 return saida

def validar_proposta(texto,digest):
 if not isinstance(texto,str) or len(texto)>32000:raise Bloqueio('resposta_invalida')
 texto=texto.strip()
 if texto.startswith('```json') and texto.endswith('```'):texto=texto[7:-3].strip()
 try:d=json.loads(texto)
 except (ValueError,TypeError):raise Bloqueio('json_invalido') from None
 if not isinstance(d,dict) or set(d)!={'versao','pedido_sha256','fontes'} or type(d['versao']) is not int or d['versao']!=1:raise Bloqueio('esquema_invalido')
 if d['pedido_sha256']!=digest:raise Bloqueio('pedido_divergente')
 return validar_fontes(d['fontes'])

def obter_plano(pedido):
 import intencao_operacional as I
 intencao=I.classificar(pedido)
 if not intencao or intencao['modo']=='leitura_explicita' or not T.id_da_origem():raise Bloqueio('origem_ou_escopo_ausente')
 digest=hashlib.sha256(pedido.encode()).hexdigest();ident=T.id_da_origem();path=f'MEMORIA/planos-operacionais/{ident}.json'
 existente=O.ler_opcional(path)
 if existente:
  raw=base64.b64decode(existente['content'])
  if O.sha(raw)!=existente['sha']:raise Bloqueio('plano_sem_integridade')
  registro=json.loads(raw)
  if registro.get('versao')!=1 or registro.get('pedido_sha256')!=digest or registro.get('origem')!=T._ORIGEM.get():raise Bloqueio('plano_de_outra_origem_ou_pedido')
  if registro.get('estado')!='validado':
   if registro.get('motivo_bloqueio')=='pedido_misto_leitura_e_alteracao_requer_revisao':raise Bloqueio(registro['motivo_bloqueio'])
   raise Bloqueio('plano_bloqueado_persistido_requer_revisao')
  registro['fontes']=validar_fontes(registro.get('fontes'));return registro
 if intencao['modo']=='bloqueado':
  registro={'versao':1,'origem':T._ORIGEM.get(),'pedido_sha256':digest,'estado':'bloqueado','fontes':[],'tentativas_modelo':0,'modelo':None,'motivo_bloqueio':intencao['motivo']}
  O.imutavel(path,json.dumps(registro,ensure_ascii=False,sort_keys=True)+'\n')
  raise Bloqueio(intencao['motivo'])
 if intencao['modo']=='automatico':
  fontes=validar_fontes(intencao['fontes_minimas'])
  registro={'versao':1,'origem':T._ORIGEM.get(),'pedido_sha256':digest,'estado':'validado','fontes':fontes,'tentativas_modelo':0,'modelo':None,'metodo':intencao['metodo'],'versao_roteador':1,'motivo_bloqueio':None}
  O.imutavel(path,json.dumps(registro,ensure_ascii=False,sort_keys=True)+'\n')
  return registro
 sistema=('Você propõe um plano de LEITURA, não executa nada. Responda somente JSON com chaves versao=1, pedido_sha256 (copie exatamente o hash informado), fontes (lista de pares [tipo,argumento]). '
 'Tipos: REPO com argumento motor/caminho, site/caminho ou chat/caminho (apenas repositórios públicos); ACOES com filtro de nome, por exemplo chat. Máximo seis fontes. '
 'Não inclua comandos, ferramentas de escrita, textos de relatório, estado de sucesso, credenciais ou chaves extras. Escolha fontes necessárias ao objetivo atual; não use tarefas de histórico. '
 'Este escopo não permite publicar, enviar email, instalar, disparar workflows, gastar ou mudar código. Propor fontes não comprova atender ao objetivo; a entrega será para revisão.')
 mensagens=[{'role':'user','content':json.dumps({'pedido_atual':pedido,'pedido_sha256':digest},ensure_ascii=False)}]
 fontes=None;erro='modelo_indisponivel';tentativas=0;modelo=None
 for _ in range(2):
  tentativas+=1
  texto,modelo,_erro=C.chamar_llm(mensagens,system=sistema)
  if texto is None:break
  try:fontes=validar_proposta(texto,digest);break
  except (ValueError,PermissionError):
   erro='proposta_nao_validada'
   mensagens.append({'role':'user','content':'Proposta rejeitada pelo controlador. Refaça somente o JSON do esquema permitido, sem ampliar o escopo, usando o pedido e hash originais.'})
 registro={'versao':1,'origem':T._ORIGEM.get(),'pedido_sha256':digest,'estado':'validado' if fontes else 'bloqueado','fontes':fontes or [],'tentativas_modelo':tentativas,'modelo':modelo,'motivo_bloqueio':None if fontes else erro}
 O.imutavel(path,json.dumps(registro,ensure_ascii=False,sort_keys=True)+'\n')
 if not fontes:raise Bloqueio(erro)
 return registro

def executar(pedido):
 plano=obter_plano(pedido)
 return O.executar(pedido,fontes_planejadas=plano['fontes'])
