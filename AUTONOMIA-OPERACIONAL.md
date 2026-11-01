# Autonomia operacional com limites verificáveis

A autonomia é por tarefa e por permissão, não universal. A execução depende de runners e cotas existentes. Este conjunto não cria cron, infraestrutura, conta nem credencial.

## Continuidade

`trabalhos.py` vincula objetivo e plano à origem da mensagem, salva artefatos e seus SHAs e só entrega depois de reconferi-los. `responder.py` retoma a mesma origem e preserva pendências, inclusive se um checkpoint falhar. Uma tarefa incompleta não impede avaliar a próxima origem, dentro do orçamento da rodada. Falha geral dos motores preserva a fila, sem girar indefinidamente.

Histórico, resposta final, dono e paginação têm uma definição canônica em `varrer.py`, também usada pelo sentinela. Históricos em revisão não são executados nem apagados da fila. Mensagens válidas não expiram por idade. Um único dispatch do sentinela já acorda a fila toda. Isso não é exatamente-uma-vez universal entre plataformas.

## Leitura operacional restrita

Uma mensagem do dono iniciada por `<!--escopo:leitura-operacional-->` restringe as ferramentas a:

- `REPO`: leitura dos repositórios públicos motor, site e chat; sem travessia ou injeção de query;
- `ACOES`: leitura da execução real do motor, com SHA e URL de evidência;
- `TRABALHO`: plano, artefatos e recibo privados vinculados à própria origem.

Outras ferramentas são bloqueadas antes da chamada, inclusive publicação, email, alteração de motores e dispatch de diagnóstico. `casa.disparar` também recusa dispatch nesse contexto. Não se trata de sandbox de todo o Python nem de redução do escopo administrativo do PAT: os limites do token dependem da configuração do dono. Registros auxiliares da conversa continuam sendo memória privada. A restrição não autoriza alterar produção ou gastar.

## Conflitos de memória

`sincronizar.py` mantém comparação de versões e SHA otimista. Uma divergência não sobrescreve o remoto. A versão local é preservada em cópia privada imutável em `MEMORIA/conflitos-sync/`, com conteúdo e proveniência, quando a API confirma o recibo. A origem continua divergente e o processo retorna falha: cópia não significa reconciliação ou entrega. Se a cópia falhar, o diagnóstico declara isso. HTTP409 entre listagem e escrita também tenta essa preservação. Não há transação multi-arquivo.

Logs públicos contêm identificador hash do caminho e motivo, não nome/conteúdo privado. A cópia privada nunca dispara uma ação histórica. Revisão de conflitos incompatíveis permanece necessária.

## Evidência e aceite

As regressões offline são executadas em cópias descartáveis, sem credenciais e com conexões externas bloqueadas na bancada local. O workflow `testes.yml` inclui as novas regressões. Tarefas reais devem ter plano persistido, artefatos conferidos e recibo; êxito de teste não basta para comprovar operação cotidiana. `entregue_para_revisao` é entrega verificável, não aprovação humana automática nem qualidade garantida.

Não declarar autonomia total: permanecem dependências de disponibilidade, cotas, permissão das plataformas e qualidade do modelo. Uma credencial com privilégio excessivo não pode ser substituída automaticamente por este código.
