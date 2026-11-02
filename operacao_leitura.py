"""Executor restrito para leitura operacional: fatos antes de evidência, sem LLM.
Não amplia ferramentas, não publica, não dispara workflow, não apaga versões antigas.
"""
import base64,hashlib,json,re
import comum as C
import trabalhos as T
EXECUTOR='leitura-operacional-v1'
PREFIXO='<!--escopo:leitura-operacional-->'
def eh_operacional(pedido):
 import intencao_operacional as I
 return I.classificar(pedido) is not None
def exige_comprovante(pedido):
 import intencao_operacional as I
 return I.explicito(pedido)
def marcador(marca):return f'<!--entrega-operacional-verificada:{marca}-->'
def sha(b):return hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
def ler_opcional(path):
 try:return C.gh('GET',f'/repos/{C.REPO}/contents/{path}')
 except RuntimeError as e:
  if re.search(r'HTTP 404(?:\D|$)',str(e)):return None
  raise

def imutavel(path,conteudo):
 b=conteudo.encode();info=ler_opcional(path)
 if info is None:
  r=C.gh('PUT',f'/repos/{C.REPO}/contents/{path}',{'message':'operacao: salva evidencia privada imutavel','content':base64.b64encode(b).decode()})
  if not isinstance(r,dict) or r.get('content',{}).get('sha')!=sha(b):raise RuntimeError('recibo de escrita divergente')
  info=ler_opcional(path)
 if not info or info.get('sha')!=sha(b) or base64.b64decode(info.get('content',''))!=b:raise RuntimeError('evidencia privada divergente')
 return {'arquivo':path,'sha_blob':info['sha']}

def fontes_do_pedido(pedido):
 if not pedido.lstrip().startswith(PREFIXO):raise ValueError('escopo restrito ausente')
 fontes=[]
 for filtro in re.findall(r'\bUse ACOES com filtro ([A-Za-z0-9_-]+)',pedido):fontes.append(('ACOES',filtro))
 for arq in re.findall(r'\bLeia REPO ((?:motor|site|chat)/[A-Za-z0-9_./-]+)',pedido):fontes.append(('REPO',arq.rstrip('.')))
 fontes=list(dict.fromkeys(fontes))
 if not fontes or len(fontes)>8:raise ValueError('indique fonte operacional suportada: Use ACOES com filtro ou Leia REPO')
 for tipo,arg in fontes:C._autorizar_leitura_operacional(tipo,arg)
 return fontes

def coletar(fontes):
 resultados=[]
 for tipo,arg in fontes:
  if tipo=='ACOES':
   api=f'/repos/{C.REPO_ROBO}/actions/runs?per_page=100';dados=C.gh('GET',api)
   if not isinstance(dados,dict) or not isinstance(dados.get('workflow_runs'),list):raise RuntimeError('execucoes nao observaveis')
   vistos=set();selecionados=[]
   for r in dados['workflow_runs']:
    nome=r.get('name','')
    if arg.lower() not in nome.lower() or nome in vistos:continue
    vistos.add(nome);selecionados.append({k:r.get(k) for k in ['id','name','status','conclusion','head_sha','html_url','created_at']})
   if not selecionados:raise RuntimeError('nenhuma execucao observada para o filtro')
   import chat_componentes
   texto=chat_componentes.apresentar(selecionados)
   resultados.append({'tipo':tipo,'argumento':arg,'fonte':'https://api.github.com'+api,'dados':selecionados,'relatorio':texto})
  else:
   repo,path=arg.split('/',1);base=f'/repos/reboclbrank-max/{repo}';head=C.gh('GET',base+'/git/ref/heads/main')['object']['sha'];d=C.gh('GET',base+f'/contents/{path}?ref={head}');b=base64.b64decode(d['content']);assert sha(b)==d['sha'];texto=b.decode('utf-8');url=f'https://github.com/reboclbrank-max/{repo}/blob/{head}/{path}'
   rel=f"Fonte fixada no commit `{head}`; SHA do arquivo `{d['sha']}`.\n"
   if path.endswith('postagem-diaria.yml'):
    deps={n:re.search(r'\b'+n+r'==([0-9.]+)',texto) for n in ['Pillow','PyYAML']}
    barreira=texto.find('- name: Barreira offline de autonomia e marca');gif=texto.find('testes-gif-com-selo.py')
    ordem=barreira>=0 and gif>barreira and all(m and m.start()<barreira for m in deps.values())
    rel+='\n'.join(f"- {n}: versão `{m.group(1)}`." if m else f'- {n}: versão não observada.' for n,m in deps.items())
    rel+=f"\n- Instalação textual anterior à barreira offline que inclui testes-gif-com-selo.py: {'sim' if ordem else 'não confirmada'}.\n- Ordem: contrato de preservação; dependências da barreira; barreira offline de autonomia e marca.\n- Esta é análise estática da ordem declarada, não prova de execução ou publicação."
   else:rel+='\nTexto observado:\n```\n'+texto[:12000]+'\n```'
   resultados.append({'tipo':tipo,'argumento':arg,'fonte':url,'head':head,'sha_blob':d['sha'],'relatorio':rel})
 return resultados

def executar(pedido,fontes_planejadas=None):
 if fontes_planejadas is not None:
  import planejamento_operacional as P
  if not P.eh_planejamento(pedido):raise ValueError("plano exige escopo próprio")
  fontes=P.validar_fontes(fontes_planejadas)
 else:fontes=fontes_do_pedido(pedido)
 ident=T.id_da_origem()
 if not ident:raise ValueError('origem obrigatoria')
 registro=T.recuperar_da_origem()
 if registro and registro.get('executor')==EXECUTOR:
  if registro.get('fontes_planejadas')!=[list(f) for f in fontes]:raise ValueError('plano mudou; requer revisao')
  if registro['estado']=='entregue_para_revisao':return T.recibo(ident)
 else:
  dados=coletar(fontes)  # Nenhum checkpoint de evidência antes de ler fontes reais.
  objetivo=pedido.split('Objetivo:',1)[-1].split('Critério de aceite:',1)[0].strip()
  rel='# Conferência operacional verificada\n\nObjetivo: '+objetivo+'\n\nObservado em: '+C.agora().isoformat()+'\n\n'
  for d in dados:rel+='## '+d['tipo']+': '+d['argumento']+'\n\nFonte: '+d['fonte']+'\n\n'+d['relatorio']+'\n\n'
  rel+='## Limites\n\nSomente leitura de produção; nenhum workflow foi disparado pelo executor desta tarefa. Nenhuma publicação, email ou gasto foi efetuado por este executor. Status de job não comprova conclusão de tarefa; em andamento não significa sucesso. Arquivos e recibo são privados. Análise determinística de fontes observadas, sem chamada de LLM; não é aprovação humana nem garantia de autonomia geral.\n'
  if fontes_planejadas is not None:
   import intencao_operacional as I
   if (I.classificar(pedido) or {}).get('modo')=='automatico':
    rel+='\n## Planejamento automático\n\nPedido reconhecido sem marcador técnico. Fontes selecionadas pelo roteador determinístico, sem chamada de modelo para esse plano. Plano privado: MEMORIA/planos-operacionais/'+ident+'.json. Apenas leituras reconhecidas são roteadas; não é interpretação universal de qualquer objetivo.\n'
   else:rel+='\n## Planejamento\n\nFontes propostas por modelo, validadas pelo controlador e executadas sem ferramenta de escrita em produção. Plano privado: MEMORIA/planos-operacionais/'+ident+'.json. A validação estrutural não garante que o modelo escolheu todas as fontes adequadas ao objetivo; relatório entregue para revisão. A ausência de LLM citada acima refere-se à coleta/análise determinística, não à proposta do plano.\n'
  ev=imutavel(f'MEMORIA/operacao-leitura/{ident}/{hashlib.sha256(rel.encode()).hexdigest()}.md',rel)
  arquivo=T.caminho(ident);info=ler_opcional(arquivo);anterior_sha=info['sha'] if info else None
  if registro:
   if not info or json.loads(base64.b64decode(info['content']))!=registro:raise RuntimeError('registro mudou durante coleta')
   copia=imutavel(f'MEMORIA/trabalhos-revisoes/{ident}/{info["sha"]}.json',base64.b64decode(info['content']).decode())
   revisoes=registro.get('revisoes_anteriores',[])+[{'registro':copia,'motivo':'evidencia anterior sem proveniencia verificavel; preservada, nao reutilizada como aceite'}]
  else:revisoes=[]
  if registro is None:
   T.executar(json.dumps({'acao':'criar','objetivo':objetivo,'etapas':['Conferir as fontes operacionais autorizadas e salvar relatorio verificavel']}));registro,anterior_sha=T.carregar(ident)
  registro.update(objetivo=objetivo,estado='planejado',bloqueio=None,executor=EXECUTOR,fontes_planejadas=[list(f) for f in fontes],fontes_observadas=dados,evidencia_operacional=ev,revisoes_anteriores=revisoes,etapas=[{'numero':1,'descricao':'Conferir fontes reais e salvar relatorio verificavel','estado':'pendente'}])
  T.salvar(registro,anterior_sha)
 registro,_=T.carregar(ident);ev=registro['evidencia_operacional'];info=ler_opcional(ev['arquivo'])
 if not info or info['sha']!=ev['sha_blob'] or sha(base64.b64decode(info['content']))!=ev['sha_blob']:raise RuntimeError('artefato mudou apos coleta')
 if registro['etapas'][0]['estado']=='pendente':T.executar(json.dumps({'acao':'registrar_etapa','id':ident,'etapa':1,'arquivo':ev['arquivo'],'sha_esperado':ev['sha_blob']}))
 registro,_=T.carregar(ident)
 if registro['estado']!='entregue_para_revisao':T.executar(json.dumps({'acao':'entregar','id':ident,'resultado':'Relatorio operacional com fontes observadas e SHAs conferidos; somente leitura de producao.'}))
 return T.recibo(ident)
