# Retomada por mensagem de origem

Pedido: continuar funcionário digital existente, GitHub/R$0, sem marketing.

## Contrato novo

O respondedor estabelece contexto por repositório, conversa e marca da mensagem.
O ID do trabalho criado nesse contexto é determinístico. Repetir criar para a
MESMA mensagem recupera o registro existente e não substitui objetivo/etapas.
Outra mensagem na mesma conversa tem outro ID. Fora do contexto, API legada por
UUID continua compatível. Registro guarda origem e hash do texto recebido: se o
pedido for editado depois, recusa retomar silenciosamente um plano antigo.

O contexto é local à execução e restaurado ao sair, mesmo em erro. Cada item do
dreno usa sua própria origem, não a da mensagem que disparou a rodada. SHA de
escrita segue otimista: não há trava distribuída ou transação entre serviços.

## Retomada

Antes dos atalhos, o respondedor procura o trabalho da mensagem. Se incompleto,
instrui o modelo com o estado persistido e ID, para executar só etapas pendentes.
Se já entregue, reconfere evidências e publica o recibo sem pedir nova execução ao
modelo. Aplica-se também ao caso entregar ter terminado, mas a publicação cair.
Uma resposta 'terminei' do modelo não encerra uma mensagem cujo trabalho segue
incompleto: publica aviso pendente, mantém registro/fila e permite nova tentativa
pelas rodadas já existentes. Não cria cron novo nem executor em segundo plano.

Trabalhos antigos sem origem não são migrados automaticamente. Não altera as 18
mensagens históricas em revisão. Não garante recuperação de ação externa no meio,
nem do intervalo entre gravação do artefato e checkpoint se o novo conteúdo for
diferente. Não garante qualidade universal, continuidade infinita ou consciência.

## Validação

28 arquivos de teste locais passaram. Dez novos contratos: identidade estável,
mensagens distintas, restauração de contexto, interrupção depois da etapa1,
retomada sem repetir etapa/evidência, entrega sem publicação, falsa conclusão,
pedido editado, erro503 e origem correta do dreno. Um contrato encerra processo
com os._exit(23) após checkpoint; outro processo retoma e um terceiro confere
dedupe. API/armazenamento remoto e modelo são simulados nesse ensaio: NÃO é queda
real de runner GitHub nem execução nova com LLM real.

Teste antigo do dreno inicialmente deixou escapar consultas GET sem mock, que
retornaram401 sem credencial operacional; corrigido o isolamento antes do corte
final. Credencial operacional REST não foi usada nesses testes. Regressões foram
repetidas, nenhuma alteração externa nesse ensaio e nenhum dispatch manual novo.
