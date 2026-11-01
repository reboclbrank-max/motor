"""Roteamento conservador do pedido atual, sem inferência nem autorização nova.
Só reconhece leituras operacionais da casa. História ou publicação não vira plano.
"""
import re,unicodedata
PREFIXO_LEITURA='<!--escopo:leitura-operacional-->'
PREFIXO_PLANO='<!--escopo:planejamento-operacional-->'
VERBOS='publicar|publique|publica|postar|poste|enviar|envie|apagar|apague|excluir|exclua|remover|remova|instalar|instale|alterar|altere|corrigir|corrija|atualizar|atualize|comprar|compre|pagar|pague|revogar|revogue|mudar|mude|implantar|implante|gastar|gaste|contratar|contrate|ativar|ative|desativar|desative|cancelar|cancele|reiniciar|reinicie|executar|execute'
def normalizar(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))
def explicito(s):return str(s or '').lstrip().startswith((PREFIXO_LEITURA,PREFIXO_PLANO))
def classificar(pedido):
 if not isinstance(pedido,str):return None
 texto=pedido.strip()
 if texto.startswith(PREFIXO_LEITURA):return {'modo':'leitura_explicita'}
 if texto.startswith(PREFIXO_PLANO):return {'modo':'planejamento_explicito'}
 s=normalizar(texto)
 if len(s)>12000 or s.startswith(('"',"'",'```','>')):return None
 s=re.sub(r'^(?:por favor[, ]+|voce pode |pode |quero que voce |quero que )','',s)
 leitura=bool(re.match(r'^(confira|conferir|verifique|verificar|audite|auditar|diagnostique|diagnosticar|inspecione|inspecionar|consulte|consultar|cheque|veja|mostre|compare|analise|analisar|leia)\b',s) or re.match(r'^como esta(?:o)? (?:o |a |os |as )?(chat|site|motor|operacao)\b',s))
 if not leitura:return None
 if re.search(r'https?://(?!github\.com/reboclbrank-max/)',s):return None
 # Restrições negativas não escolhem alvos/fontes. Mutação ainda é checada no pedido inteiro.
 texto_fontes=re.sub(r'\b(?:nao|não|sem)\b[^,;.\n]*','',texto,flags=re.I)
 evidencias=normalizar(texto_fontes)
 alvos={a for a in ['chat','site','motor'] if re.search(r'\b'+a+r'\b',evidencias)}
 contexto=bool(re.search(r'\b(operacao|executor|workflow|workflows|barreira|barreiras|dependencias|preparacao|repositorio|casa|status|saude|funcionamento)\b',s) or re.search(r'\b(?:motor|site|chat)/[A-Za-z0-9_./-]+',texto))
 if not alvos and 'operacao' not in s:return None
 if alvos=={'motor'} and not contexto:return None
 if 'chat' in alvos and not contexto and not s.startswith('como esta'):return None
 if 'site' in alvos and not contexto and not re.search(r'\b(nosso site|site da casa)\b',s):return None
 # Negação de alteração não é autorização. Outra ocorrência afirmativa continua bloqueada.
 sem_negacoes=re.sub(r'\b(?:nao|sem)\s+(?:'+VERBOS+r')\b','',s)
 if re.search(r'\b(?:'+VERBOS+r')\b',sem_negacoes) or re.search(r'\bfaca (deploy|publicacao|envio|alteracao|implantacao|compra)\b',sem_negacoes):
  return {'modo':'bloqueado','motivo':'pedido_misto_leitura_e_alteracao_requer_revisao'}
 fontes=[]
 for caminho in re.findall(r'\b(?:motor|site|chat)/[A-Za-z0-9_./-]+',texto_fontes):fontes.append(['REPO',caminho.rstrip('.')])
 if not fontes:
  preparacao=any(p in evidencias for p in ['barreira','dependencia','preparacao','workflow'])
  status=bool(re.search(r'\b(execucao|execucoes|runs|jobs|status)\b',evidencias))
  if 'site' in alvos:fontes.append(['REPO','site/.github/workflows/postagem-diaria.yml'])
  if 'chat' in alvos and preparacao:fontes.append(['REPO','motor/.github/workflows/chat.yml'])
  if ('chat' in alvos and (not preparacao or status)) or (not alvos and 'operacao' in s):fontes.append(['ACOES','chat'])
  if alvos=={'motor'}:fontes.append(['ACOES',''])
 unicas=[]
 for f in fontes:
  if f not in unicas:unicas.append(f)
 if not unicas or len(unicas)>6:return None
 return {'modo':'automatico','fontes_minimas':unicas,'metodo':'roteador_deterministico','versao_roteador':1}
