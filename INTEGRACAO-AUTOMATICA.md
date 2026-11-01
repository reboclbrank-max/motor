# Integração automática — leituras operacionais da casa

Pedidos reconhecidos não exigem marcador técnico. Exemplos: “Confira a operação”, “Como está o Chat da casa?”, “Confira as barreiras de preparação do Site e do Chat da casa”, “Leia site/.github/workflows/postagem-diaria.yml”. O roteador recebe apenas o pedido atual; não interpreta ordens de histórico. Objetivos ambíguos/fora desse domínio continuam no fluxo normal, sem serem convertidos silenciosamente em auditoria da casa.

A rota reconhecida restringe ferramentas, gera plano privado vinculado à origem/hash, consulta fontes públicas atuais, salva relatório com commit/SHA e só registra recibo após conferir os artefatos. Para os casos mapeados usa planejamento determinístico sem chamada de modelo. Reentrada reutiliza plano/entrega. A rota de proposta por modelo e os marcadores anteriores permanecem compatíveis. Isso não é compreensão irrestrita de qualquer linguagem/objetivo.

Pedidos mistos de leitura e alteração são bloqueados para revisão antes de leituras/efeitos de produção. Negação (“sem publicar”) não autoriza publicação, e outra ordem afirmativa posterior continua bloqueada. Finais naturais antigos não são reabertos por esta integração; registros históricos não são descartados. Novas entregas do controlador têm comprovante.

No dispatcher do modelo, EMAIL, PUBLICAR, PLANTAR e dispatches DIAGNOSTICAR/MEDIR exigem autorização na mensagem atual. Texto gerado pelo modelo não concede essa autorização. Leitura operacional bloqueia esses efeitos mesmo quando o modelo tenta solicitá-los. Isso não é sandbox de Python ou substituição das permissões do PAT. Atalhos diretos e rotinas preexistentes com autorizações próprias não são todos redesenhados aqui.

Corrigido também o produtor de candidatos: novo registro tem nome/tipo/timeout; dados corrompidos não são substituídos por lista vazia; entradas anteriores são preservadas, endpoint privado/credencial/query não é aceito, e escrita sem recibo não vira sucesso. Um candidato antigo pôde ter somente o nome completado; outro ficou inalterado porque o destino foi interno ou não verificável nesta bancada. Não houve sondagem HTTP dos provedores nem promoção de modelo ativo.

## Limites externos, não etapas que possam ser escondidas

- Trocar PAT administrativo exige titular no GitHub; tokens não devem ser colados no Chat. A migração precisa preservar memória e despertar executores, não substituir às cegas por token incompatível. Não foi criada nem alterada credencial.
- Endpoint interno/não verificável não deve ser liberado para fingir correção completa. Permanece retido até revisão/verificação segura.
- Garantia de executar corretamente qualquer objetivo, com qualquer modelo/plataforma, não é uma propriedade alcançável por esta alteração. Planejamento livre permanece sujeito a erro. Fontes observadas e limites ficam explícitos, não são trocados por promessa de autonomia total.

Sem novos crons, contas, serviços contratados ou disparos de marketing.

As barreiras Python dos workflows foram ligadas ao executor isolado já existente: cópia descartável, sem segredos herdados nem TCP externo. A integração pública teste-chat.py continua separada. Fixtures de teste não devem chegar ao checkout que depois baixa/devolve memória privada. Nenhum cron ou gatilho foi criado por essa troca.
