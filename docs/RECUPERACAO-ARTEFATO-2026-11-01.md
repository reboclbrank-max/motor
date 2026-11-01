# Arquivo salvo antes do checkpoint

Continuação do funcionário digital: o resultado pode ter sido gravado e a execução
cair antes de registrar a evidência na etapa. Antes, uma nova redação diferente
batia na proteção contra sobrescrita e não havia leitura pela ferramenta TRABALHO.

Adicionada ação inspecionar_etapa: lê arquivo, conteúdo e SHA sem concluir a etapa
nem escrever. A retomada avisa quando a primeira etapa pendente tem arquivo salvo,
orientando inspeção antes de refazer. O modelo pode reaproveitar o arquivo usando
registrar_etapa/arquivo/sha_esperado. Para recuperar arquivo da própria etapa, a
versão lida é obrigatória; se mudar, não confirmar checkpoint. Reconstrói espelho
local desse Markdown para sincronização não devolver versão antiga.

Existência de arquivo não implica qualidade ou tarefa concluída. Inspeção não é
aprovação automática. Artefato vazio, corrompido ou divergente não é reparado nem
apagado automaticamente. A ação cobre entregas textuais UTF-8, não checkpoint de
qualquer ação externa nem transação distribuída.

28 suítes locais passaram. teste-trabalhos.py agora tem22casos, seis novos:
falha entre escrita do arquivo e checkpoint, inspeção só leitura, versão alterada,
SHA obrigatório, ausência404 e erro503. Modelo/API são simulados nesses contratos.
Prova de trabalho real pelo modelo permanece ligada aos runs41282395300/41282896680
e seus SHAs; não afirmar que esta alteração já foi ensaiada em runner com queda real.
Sem dispatch manual/cron novo, marketing, gasto ou hospedagem nova.
