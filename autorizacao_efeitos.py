"""Guarda do dispatcher do modelo para efeitos externos/configuração.
Pedido atual é autoridade; argumento ou texto produzido pelo modelo não é.
Não substitui as permissões do token nem é sandbox de Python.
"""
import re
from intencao_operacional import normalizar
TIPOS={'EMAIL','PUBLICAR','PLANTAR','DIAGNOSTICAR','MEDIR'}
def permitido(tipo,arg,pedido,publicar_autorizado=False):
 if tipo not in TIPOS:return True
 s=normalizar(str(pedido or '').strip());s=re.sub(r'^(?:por favor[, ]+|voce pode |pode |quero que voce |quero que )','',s);s=s.lstrip('/!')
 if tipo=='PUBLICAR':return bool(publicar_autorizado)
 if tipo=='EMAIL':
  if re.search(r'\b(nao|sem)\s+(envie|enviar)\b',s):return False
  return bool(re.match(r'^(email\s*:|e-mail\s*:|(?:envie|enviar|mande|mandar)\s+(?:um\s+)?e-?mail\b)',s))
 if tipo in ('MEDIR','DIAGNOSTICAR'):
  return bool(re.match(r'^(diagnosticar|diagnostique|diagnostico|medir|meca)\b',s))
 if tipo=='PLANTAR':
  partes=str(arg or '').split('|')
  return len(partes)==2 and all(p.strip() and p.strip() in str(pedido or '') for p in partes) and bool(re.match(r'^(plantar|plante|cadastre|cadastrar|adicione|adicionar)\b',s))
 return False
