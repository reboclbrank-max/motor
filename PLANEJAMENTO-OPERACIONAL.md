# Planejamento proposto por modelo e execução controlada

Ativação interna: mensagem do dono iniciada por `<!--escopo:planejamento-operacional-->`, seguida do objetivo em linguagem natural. Usa o mesmo workflow do Chat. Não exige comandos literais `Use ACOES`/`Leia REPO` da rota anterior.

O modelo recebe somente o pedido atual, seu hash e o esquema fechado de proposta. Pode escolher de uma a seis fontes públicas: REPO em motor/site/chat ou ACOES com filtro. Não pode propor publicação, email, comandos, instalação, mudanças ou ferramentas privadas. O controlador valida tipos, chaves, caminho, escopo e vínculo com o pedido. Nenhum texto “concluído” do modelo é executado como prova.

Há no máximo duas chamadas ao mecanismo de modelos para propor/corrigir JSON por origem; cada chamada usa a cadeia de provedores já existente, que pode fazer tentativas internas. Não é limite global de tokens/minutos ou garantia de custo de qualquer configuração futura. Nenhuma conta/credencial/cron/contratação é criada. A proposta aceita, ou bloqueio, é salva em memória privada imutável. Reentrada reutiliza o plano. Bloqueio persistido exige revisão, sem novas chamadas repetidas indefinidamente.

A execução fica com o controlador de leitura: lê fontes reais antes da evidência, fixa commit/SHA, grava relatório privado e só entrega depois de conferir arquivos. Falha após salvar plano não obriga nova inferência na retomada. O mesmo controle de fila, contexto, recibo e versões anteriores se aplica. O planejamento não amplia autorização.

**Limites:** validação estrutural não é verificação semântica do objetivo; o modelo ainda pode selecionar fontes insuficientes. Isso não torna seguro planejamento livre universal nem libera modificações em produção. A troca do PAT administrativo depende do titular. A rota antiga determinística continua disponível e não passou a depender de LLM.
