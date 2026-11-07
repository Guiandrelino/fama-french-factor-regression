# Preparação para publicação — estado verificável

## O que foi implementado

- Nova navegação de Pesquisa por estações: visão geral, risco/carteira, operações e relatórios; operações renderiza apenas a seção selecionada. Paleta preto/azul industrial, âmbar e ciano, sem vínculo com Bloomberg.
- Cache em memória de preços da página inicial removido: não compartilha provenance privada entre usuários. Cache de preços em disco separado por workspace, TTL explícito e falha de rede sem fallback vencido.
- Expiração absoluta de sessão configurável (`FACTORLAB_SESSION_SECONDS`, padrão 1800 s), logout limpa estado.
- Locks interprocessos para banco/backup/restauração; escrita de snapshots atômica; quota configurável (`FACTORLAB_QUOTA_MB`, padrão 250 MB). Quota é controle operacional, não limite rígido de filesystem; concorrência/SQLite podem temporariamente acrescentar overhead.
- Fila de background limitada a quatro tarefas totais e dois workers por processo. Avaliação rolling e bootstrap em background; owner por análise e assinatura de parâmetros impedem aplicar resultado em estudo/controles diferentes. Tarefa já executando pode continuar após logout, mas não é publicada em outra sessão.
- Avaliação com custos equivalentes em estratégia/referências líquidas, RF compatível da amostra e parâmetros preservados.
- Histórico SQLite salva extras completos em JSON tabular; relatórios permitem selecionar extras; PDF possui gráficos adicionais e tabelas (limites de prévia explícitos).
- Testes de cache/expiração/falha de rede, fila, quota, contabilidade, RF e dois usuários no Chromium.

## Validação local desta etapa

- 81 testes offline aprovados.
- 23 testes live aprovados.
- Teste Chromium de upload/relatório aprovado.
- Teste Chromium com Alice/Bob simultâneos: login, análise sintética, salvamento privado, isolamento e logout aprovado.
- Docker reconstruído; healthcheck healthy, endpoint ok, regressão/PDF executados dentro da imagem. Container de teste removido.
- Lint e formato executados. CI remoto deve ser conferido por commit, não inferido a partir da execução local.

## Publicação HTTPS com proxy

1. Disponibilize servidor com Docker e domínio apontado para ele.
2. Gere hashes PBKDF2 com `factorlab.security.password_hash` em ambiente confiável. Não coloque senhas/hashes no Git.
3. Copie `.env.example` para `.env`, configure domínio e JSON de usuários. Preserve `$` com aspas simples no dotenv.
4. Execute `docker compose config` para validar e `docker compose up -d --build`.
5. Abra portas 80/443; não publique porta do app diretamente. Caddy obtém certificado e Nginx limita requisições/conexões por IP.
6. Teste HTTPS, login/expiração, download, reconexão WebSocket e acesso cruzado com contas de teste. Verifique logs e backups antes de inserir dados privados.

O limite HTTP por IP controla conexões/requests, não cada mensagem WebSocket. Login também limita tentativas por sessão, que não substitui proteção de identidade centralizada. Para serviço aberto com risco elevado use OIDC/SSO/MFA e WAF/limitação de tentativas na camada de identidade. Não se declara proteção perfeita contra brute force.

## Backup/restauração

Administração exporta backup consistente; guarde-o criptografado fora do host. Restauração valida integridade, tabelas permitidas e esquema e usa lock compartilhado com os acessos ao banco. Faça ensaio com banco de teste e confirme contagem e conteúdo após restaurar. Arquivos SQLite enviados devem vir de origem confiável. Backup não contém todos os snapshots; preserve o volume inteiro para recuperação completa. Quotas e retenção precisam de política operacional do responsável.

## Limites que código sozinho não resolve

- Domínio, DNS, firewall, certificado real, backup externo, SLA e monitoramento do host não foram provisionados. Compose é configuração fornecida, não prova de deploy público.
- Não existe histórico completo point-in-time dos fornecedores: não há como certificar backtest investível apenas defasando fatores. Obtenha arquivo licenciado/versionado com timestamps de publicação, universo histórico e preços de ativos extintos antes dessa alegação.
- Nem todas as combinações de bootstrap/restauração/alertas foram testadas ponta a ponta no navegador; existem testes de cálculo/backup e teste de duas sessões. Amplie cenários de restauração concorrente, falhas e carga antes de uso institucional.
- Snapshots privados são isolados; relatórios antigos podem perder evidências após retenção. Exclusão integral de conta requer parar sessões/tarefas e remover o diretório do usuário por procedimento administrativo; não há botão público de apagar conta em execução.
- Threads são limitados por processo, não por cluster. Autenticação por ambiente não substitui gerenciamento de contas, recuperação de senha, MFA e auditoria institucional.

**Critério honesto:** preparado para homologação controlada com dados de teste, não certificado como “100% pronto” para qualquer publicação pública. Execute e aprove o checklist no ambiente real antes de expor dados privados.
