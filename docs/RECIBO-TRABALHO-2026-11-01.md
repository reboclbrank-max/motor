# Recibo de trabalho não depende da escolha de texto

Ensaio real privado#85, run41282395300, SHA720eef17: o modelo executou quatro
chamadas TRABALHO (criar, registrar etapa1, registrar etapa2, entregar), com dois
arquivos reais e estado entregue_para_revisao. Contudo, a comparação de relevância
manteve o primeiro texto em empate e descartou o rastro das ferramentas da segunda
resposta. A resposta publicada não trazia ID/caminhos e rodapé omitia essas ações.

Corrigido: preservar usos da segunda tentativa mesmo se seu texto não vencer;
rastrear ID do trabalho apenas a partir do retorno real da ferramenta; anexar ao
texto escolhido recibo por leitura do registro e reconferência dos SHAs atuais.
O mesmo rastreamento cobre ferramentas no modo pensar bem. Alegação textual do
modelo não produz recibo. Se consulta falha ou arquivo muda, não confirmar entrega.

27 suítes passaram, teste-trabalhos.py com16casos (três novos neste corte).
Primeiro ensaio prova execução do modelo de tarefa interna de análise/redação,
não atuação irrestrita, marketing ou planejamento autônomo geral. Novo ensaio deve
consultar o mesmo trabalho em outra execução e não criar trabalho duplicado.
Nenhuma API paga contratada. Houve HTTP402/504 em rotas durante o primeiro ensaio;
o motor usou alternativas existentes e terminou. Quotas e limitações permanecem.
