# Correção de persistência após confirmação — 2026-11-01

Teste real autorizado detectou confirmação de gravação sem permanência do dado após
encerramento do workflow. A função acrescentar_memoria fazia PUT remoto, mas mantinha
cópia local anterior; sincronizar.subir podia regravar essa cópia e desfazer o acréscimo.

Correção: espelhar o conteúdo confirmado na cópia local antes de retornar sucesso.
Modo estrito no espelho propaga falha de disco em vez de confirmar gravação completa.
A alteração é limitada a acrescentar_memoria; não é reescrita do sincronizador inteiro.

Validação: teste de regressão falhou no código anterior e passou na correção; cinco
casos novos, incluindo duas gravações sucessivas seguidas do subir() real com API
simulada. Todas as 22 suítes locais passaram. Teste obrigatório antes do atendimento.

Limites: não resolve disputa entre hosts, gravações concorrentes, falhas após o PUT
antes do espelho ou toda função que escreve memória. Em erro de disco o PUT pode ter
ocorrido; o estado deve ser reconciliado. Não há garantia exactly-once/transacional.
