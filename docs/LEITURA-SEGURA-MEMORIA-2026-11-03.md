# Bloqueio de fontes inseguras na sincronização — 2026-11-03

## Problema constatado
A verificação de `baixar` já recusava raiz simbólica e arquivos especiais, mas `subir` testava `isdir` (que segue links) e `_ler_local` abria o caminho seguindo links, podendo ler arquivos indevidos ou bloquear ao tentar abrir FIFO.

## Corte de correção
- Antes de ler manifesto ou consultar remoto no envio, a origem `MEMORIA` deve existir como diretório real (lstat, sem seguir symlink).
- `_ler_local` usa `O_NOFOLLOW` e `O_NONBLOCK`, aceita somente arquivo regular com um vínculo físico, confere inode e versão de leitura e recusa conteúdo alterado durante a leitura.
- Quatro novos testes com arquivos fictícios: raiz substituída por link; hardlink externo; FIFO sem bloqueio; leitura de symlink direto. Nenhum dado privado real é acessado.
- Os mecanismos já existentes de trava local, versão remota, recibo de PUT e preservação de conflitos permanecem. Erros são sanitizados.

## Limitações
A proteção não é uma sandbox, não implementa transações entre processos que ignorem a trava, não evita todos os ataques de corrida contra diretórios pais e não comprova restauração integral dos dados. Leitura que falha deve bloquear o arquivo, nunca permitir substituição silenciosa. CI completa e revisão da PR obrigatórias antes de integração.

## Reversão
Reverter a PR por fluxo normal; rever o pin do worker privado conforme a versão de main efetivamente implantada. Não remover dados nem históricos para destravar.
