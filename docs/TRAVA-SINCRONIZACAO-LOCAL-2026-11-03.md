# Trava de sincronização local — 2026-11-03

## Problema e decisão
Duas invocações de `sincronizar.py baixar` ou `subir` no mesmo diretório poderiam disputar o manifesto e os arquivos locais. A proteção remota por SHA não elimina essa corrida dentro de um checkout.

Foi adicionado um `flock` não bloqueante sobre `.memoria-sync.lock` (fora de MEMORIA), usado pelas duas operações. Se outra sincronização do mesmo diretório estiver em curso, a segunda retorna falha **antes de ler a rede, invalidar manifesto, alterar bytes ou enviar PUT**. A trava usa `O_NOFOLLOW`, exige arquivo regular com vínculo único e permissões restritas. É liberada pelo sistema com o fechamento do descritor, inclusive se o processo cair; não é removida como forma de destravar.

O arquivo de trava foi excluído do Git. Erros mostram apenas códigos sanitizados, sem caminhos privados ou credenciais.

## Evidência exigida
A suíte `teste-sincronizacao-versao.py` verifica bloqueio de segundo download e envio, ausência de PUT, retomada depois de liberação, rejeição de link simbólico e permissão fraca, além dos testes de versão, conflitos e preservação anteriores. Executar a CI completa do Motor na PR antes de integrar e confirmar o SHA remoto.

## Fronteiras
- A trava opera **somente entre processos que usam este sincronizador e o mesmo diretório**. Um programa que edita arquivo sem respeitar a trava ainda pode escrever simultaneamente; não há transação multi-arquivo nem exclusão distribuída entre runners diferentes.
- A base remota continua com CAS, salvamento de conflito e recusa de PUT incerto. Não há autorização para limpar conflito, apagar pasta, refazer tarefa histórica ou contornar o componente pausado.
- Nenhuma memória privada real é usada nos testes; não cria cron, conta, segredo ou novo sistema de backup.

Rollback: reverter a PR pelo fluxo normal e revisar o pin do worker privado, preservando memória, manifesto, trava e históricos.
