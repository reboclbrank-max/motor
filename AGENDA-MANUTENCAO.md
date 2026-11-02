# Agenda privada de manutenção — autorização de 2026-11-02

Missão escolhida pelo dono: manter/melhorar o Chat. Comunicação privada, R$0.
Exceção explícita: publicar somente código/testes técnicos necessários no Motor
público, após CI e revisão. Sem marketing, contas, credenciais, exclusões, mensagens
externas ou autoedição irrestrita dos executores privilegiados.

O relógio de10min já existente de chat.yml chama a agenda antes da fila comum.
Sem cron/conta/serviço novo. Política privada POLITICAS/agenda-manutencao.json,
ativação separada da implantação, worker fixado por commit. Troca de worker exige
revisão do pin; não concede automaticamente poderes a nova versão. O comando
pausar autonomia da política principal também interrompe a agenda antes de efeitos.

Prioridades determinísticas, sem LLM:
1. Falhas NOVAS (posteriores à ativação) dos workflows técnicos autorizados, do
   dono, workflow_dispatch e commit aprovado. Até3tentativas totais no mesmo run.
   Testes públicos podem ser reexecutados. CI privada só pode ser retomada com
   PR conferido e sem recibo, ou resultado positivo no mesmo run/head/contrato
   (p.ex. falha de entrega). Resultado negativo de código pertence ao reparador
   existente: a agenda não o trata como infraestrutura nem muda contrato/testes.
2. Verificação de regressões em testes.yml, no main aprovado, a cada24h.
3. Registrar evidências/resultados e necessidade de revisão em diário PRIVADO.
   Isso não é um pedido do dono: mensagens começam com 🤖, não viram novas ordens.

Máximo1ação técnica por ciclo,2por diaUTC. Orçamento reservado em checkpoint ANTES
do POST. Falha de resposta não autoriza reenviar: reconciliar run/ator/tempo/SHA;
mais de uma correlação é bloqueio, não escolha inventada. Registro privado também
reconcilia marcadores após POST incerto. Não há exatamente-uma-vez universal.

Estado em MEMORIA/agenda-manutencao/estado.json, CAS por SHA; sem truncar histórico.
Máximo500eventos/5páginas de conferência do diário; ao atingir limite pede revisão.
Consulta100runs recentes: interrupções longas podem deixar incidentes fora dessa
janela, não alegar auditoria completa. Agenda sem política ou pausada não cria nada.
Seus problemas não derrubam o Chat; log público mostra só classe de erro, não dados.

Esta é uma agenda operacional de saúde, testes e retomadas seguras, não um agente
que decide toda a estratégia de negócio ou programa qualquer plataforma. Falhas
persistentes, código de produção com segredos e situações incertas viram revisão.
Correção semântica universal é impossível de garantir; a CI e os testes não provam
que toda intenção foi entendida. Orçamentos continuam limitados, não infinitos.

Rotinas legadas não são reativadas por esta mudança. Não dispara sentinela/rotina,
email, Telegram ou marketing; usa somente os dois workflows técnicos listados.
