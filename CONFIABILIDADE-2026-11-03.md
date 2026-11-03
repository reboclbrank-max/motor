# Confiabilidade do Motor — implementação de 2026-11-03

O modelo local agora executa em processo separado, com ambiente mínimo sem chaves dos canais e tempo máximo que inclui carga/geração. Pesos continuam em cache no disco; o modelo é descarregado ao fim de cada chamada. Isso aumenta o custo de recarga; não há benchmark real nesta revisão. Cache interno distingue modelo, arquivo e contexto e fecha a instância anterior. Entrada é preservada e excesso de contexto é recusado, sem corte silencioso. Download passa por temporário e rename, sem promover arquivo parcial; checksum/pin dos pesos ainda depende de catálogo revisado.

O adaptador do componente preserva fonte/diagnóstico completos e restaura a seleção do modelo ao terminar. Proposta idêntica é bloqueada antes de criar commit ou CI. Orçamento, negativas e pausa permanecem; não houve nova tentativa do componente bloqueado.

/status inclui fotografia somente-leitura: pausa geral, agenda e componente, divergência entre pin e main e indisponibilidade de leitura. Compatibilidade de versão não é sucesso de execução. Não expõe política bruta ou conteúdo privado.

Testes novos: contratos de contexto/cache/timeout real com subprocesso fixture, ambiente sem segredo, download falho, fonte/feedback completos, ausência de delta e diagnóstico somente-leitura. As fixtures antigas de reparo foram corrigidas para representar baseline com defeito e proposta diferente; expectativas e testes protegidos permanecem.

Validação: barreira offline e CI na PR antes de promoção. Não houve inferência real, envio de mensagem, dispatch manual, mudança de orçamento ou dependência. Rollback por reversão do conjunto e revisão do pin; não remover guardas nem resetar históricos. Revisão do pin privado da agenda deve ocorrer apenas após CI e confirmação do SHA integrado. O componente pausado permanece pausado.
