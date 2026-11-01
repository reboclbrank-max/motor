# Histórico completo e progresso da fila — 2026-11-01

## Escopo aceito

Dono pediu continuar o trabalho no GitHub, R$0/sem cartão. Próximo corte pequeno:
paginação do histórico e da deduplicação do respondedor, retirada do teto de duas
respostas da reserva e checkpoints entre itens. Sem novo serviço, cron, segredo,
dispatch manual, alteração do modelo ou remoção de quotas de terceiros.

## Alterações

- Consulta todas as páginas de comentários, sem tratar erro como lista vazia.
  Página repetida integralmente é erro visível, não laço infinito.
- Histórico reconhece respostas assinadas da casa publicadas com o login do dono
  como assistant (antes eram user). A janela enviada ao modelo continua em 60000
  caracteres: ler todas as páginas não significa contexto infinito.
- Deduplicação do respondedor percorre todas as páginas e exige autor da casa e
  assinatura; marca copiada por terceiro não encerra pedido.
- Dreno da reserva não tem teto de duas respostas. Prazo de 180s, conferido ENTRE
  tarefas, preserva restante; não interrompe uma chamada de modelo já iniciada.
- Confere marca remota após publicar, salva retirada de cada item individualmente
  e interrompe se a gravação não for confirmada. Uma falha no segundo item não
  desfaz o checkpoint do primeiro. Reentrada consulta marcas antes de publicar.
- Item inválido é preservado, não apagado. Registro auxiliar falhando depois do
  checkpoint não recoloca uma resposta já entregue na fila.

## Validação e limites

25 arquivos de teste locais passaram, incluindo 12 contratos novos offline:
205 comentários em três páginas, exclusão de comentário atual, autoria,
marca na segunda página, terceiro forjando marca, erro de consulta, página repetida,
cinco entregas/cinco checkpoints, interrupção e reentrada, falha de confirmação,
falha de checkpoint após entrega, prazo, motor indisponível, item inválido.
Os testes simulam serviços e interrupção entre itens, não queda real de runner nem
checkpoint dentro de uma ação externa. Não confundir aprovação offline com prova
funcional em produção.

Persistem JSON remoto sem coordenação entre escritores e janela entre publicar e
salvar (a marca reduz duplicação na reentrada, não é transação). Avisos de falha
antigos com marca de resposta ainda podem ser considerados respondidos; precisamos
separar aviso/entrega/conclusão antes de ativar drenagem geral independente de nova
mensagem. Este corte não altera esse acionamento, não cria execução contínua e não
resolve retomada de uma ferramenta no meio. As 17 mensagens históricas continuam
em revisão. Não prometer ausência absoluta de limites.
