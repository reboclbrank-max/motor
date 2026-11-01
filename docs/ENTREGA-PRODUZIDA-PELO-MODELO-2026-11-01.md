# Entrega produzida pelo modelo

Fechado o buraco entre registro de trabalho e produção de arquivo: registrar_etapa
agora aceita `conteudo` e grava o resultado em MEMORIA/entregas/trabalho-ID/etapa-N.md.
O arquivo não precisa ser preparado pelo operador. Grava, relê, confere conteúdo,
espelha localmente e então registra seu SHA na etapa. Reentrada após gravação mas
antes do checkpoint aceita somente conteúdo idêntico, sem sobrescrever evidência.
`arquivo` preexistente continua compatível. Não executa código arbitrário.

Instruções e retorno da ferramenta orientam o modelo a continuar depois do plano,
produzir os resultados e entregar para revisão. Continua sendo necessário testar
se o modelo obedece; instrução não é garantia de execução nem validação de qualidade.
27 suítes locais passaram; teste-trabalhos.py agora tem 13 contratos, três novos.

O pedido atual autoriza validar o modelo recebendo e executando uma tarefa interna
pelo fluxo existente, sem marketing nem gasto. Ensaio deve verificar registro,
conteúdo dos arquivos, evidências/SHA e resposta entregue, não apenas workflow verde.
Preservar falhas reais. Não declarar humano, consciência ou autonomia geral com um
ensaio controlado. Limite de quatro ciclos de ferramentas ainda existe neste corte.
