# Retenção integral na fila de reserva — 2026-11-01

Removidos dois descartes ao enfileirar perguntas quando os motores falham:
- guardar somente as últimas 30 perguntas;
- guardar somente os primeiros 4000 caracteres de cada pergunta.

Agora a gravação mantém todos os itens e o texto completo recebido. Os pontos de
truncamento existiam em duas definições duplicadas; ambos foram corrigidos. A constante
legada MAX_FILA_RESPOSTAS fica zero por compatibilidade, não é usada para cortar.
Teste histórico passou a exigir 43 itens, o mais antigo preservado e texto de 12000
caracteres integral. 24 arquivos de teste locais passaram após a alteração.

Isso não torna armazenamento infinito: limites de arquivo/API continuam. Erros devem
ser tratados, não se deve descartar silenciosamente. A fila ainda usa JSON remoto e
não resolve disputa entre escritores. O dreno ainda tem lote de duas respostas e pode
reconhecer aviso com marca como respondido: pendências técnicas, não capacidade ilimitada.
Contexto de modelo, saída e ciclos de ferramentas não foram alterados nesta correção.
