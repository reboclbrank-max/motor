# Recuperação da memória sem descarte local — 2026-11-03

## Problemas reproduzidos

Com API em memória e dados fictícios, a sequência baixar → editar localmente → baixar apagava a edição ainda não enviada. A sequência baixar → remover arquivo no remoto → baixar → subir recriava o arquivo removido. Ambas terminavam com código zero antes desta correção.

## Contrato

Antes de escrever qualquer arquivo de memória, baixar confere todos os arquivos já presentes. Só reaproveita um diretório vazio ou uma cópia parcial idêntica aos blobs da árvore remota observada. Conteúdo diferente, arquivo local ausente na árvore, link simbólico, arquivo especial ou erro de leitura bloqueiam a operação. A falha invalida o manifesto para impedir o subir de um passo always(). O log revela somente motivo fechado, sem nomes privados nem conteúdo.

Exceção restrita: as duas cópias públicas de estado já distribuídas no código podem ser substituídas pelo privado apenas quando nome e SHA correspondem à allowlist literal. Se não existem no privado, sua versão é lembrada no manifesto para que não sejam enviadas como memória nova. Uma edição nesses arquivos perde a exceção. Hashes conferidos contra os blobs de main antes da promoção; mudanças futuras nessas sementes exigem revisão da allowlist.

Cópias idênticas podem completar um download interrompido. Cópias antigas diferentes também são bloqueadas, mesmo quando poderiam ser descartadas: o programa não adivinha se são uma edição pendente ou um backup importante. A recuperação deve usar outro diretório vazio após revisar/preservar o diretório anterior; não apagar ou sobrescrever o material anterior para forçar êxito. Nenhum dado real foi migrado ou restaurado nesta sessão.

## Consenso operacional e alternativas

Aceito: guarda de preservação no sincronizador existente, testes com dados fictícios e promoção por PR validada. Recusados: limpar órfãos automaticamente, sobrescrever divergências, mesclar memória por texto, resetar o componente pausado, criar sincronizador paralelo, despachar rotina ou fabricar tráfego real.

## Validação e limites

36 testes de sincronização, incluindo onze regressões novas: edição pendente, remoção remota, varredura antes da primeira escrita, cópia antiga, retomada parcial, raiz simbólica, link interno e restauração em diretório novo sem PUT duplicado, além das sementes públicas exatas/ausentes/editadas. A CI completa deve passar antes da integração.

É prova controlada de preservação e recuperação de bytes confirmados. Não comprova recuperação do incidente Batente, restauração dos espelhos, entrega de canal ou autonomia universal. O diretório de execução continua exigindo um único escritor; não há trava transacional contra alteração concorrente dos arquivos locais durante a sincronização. A escrita remota mantém o controle de versão existente.

Rollback: reverter a PR pelo fluxo normal, revisar o pin da agenda para a versão efetiva de main e preservar os diretórios bloqueados. Não remover arquivos de memória, contadores ou políticas para contornar a guarda.
