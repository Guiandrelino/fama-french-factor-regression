# Terminal Workspace — operação e funcionalidades adicionais

## Interface

Redesign inspirado na densidade visual dos terminais financeiros: superfícies grafite/preto, acentos âmbar, tipografia monoespaçada, cabeçalho de estação, painéis sem cantos arredondados, abas compactas e gráficos azul/âmbar/verde. Não é produto Bloomberg, não utiliza marca, dados proprietários ou feed ao vivo. `terminal.css` concentra a identidade visual e é incluído na distribuição Python. O projeto continua Streamlit, não migrou para SPA React.

## Central de qualidade antes da regressão

Na Pesquisa, use **Inspecionar dados antes da regressão**. A aquisição é feita, mas o código para antes de estimar modelos. Yahoo/CSV exigem confirmação de revisão antes de executar; demonstração é explicitamente sintética. Nova execução revalida dados: não há autorização automática para corrigir valores.

A auditoria apresenta faltantes por ativo, histórico, meses comuns e descartados, extremos com |retorno| >25%, moeda/origem e atualização registrada. O timestamp da auditoria não é o timestamp do download. Fontes mostram idade e status disponível/desatualizada segundo metadados; isso não é um teste de uptime. Falhas de aquisição/processamento geram registro de erro. Para preços diários há tabela de sessões esperadas e ausentes NYSE/BMF, limitada ao intervalo recebido. CSV de retornos mensais não permite auditar pregões diários: não se inventa calendário recebido.

Meses são inspecionados entre início/fim do painel recebido, não antes da listagem do ativo. Dados ausentes são mantidos na auditoria; a regressão continua rejeitando painel incompleto. Não se preenche retorno. O cache de preços tem TTL de uma hora, por ticker/datas e workspace, e registra `cache_used` e timestamp original. Cache vencido não é fallback silencioso se a rede falhar.

## Avaliação rolling da alocação

**EXECUTION LAB** estima mínima variância em janelas móveis, com custos em bps por turnover one-way, drift dos pesos, rebalanceamento mensal/trimestral/por bandas, teto por ativo e limites de grupo em JSON. Exemplo:

```json
{"AAPL":"tech","MSFT":"tech","IWM":"small"}
```

Limites de grupo:

```json
{"tech":0.7,"small":0.5}
```

Grupos são informados pelo usuário, não classificação setorial baixada. Todos os ativos precisam de grupo se houver limites. Turnover = meia soma de negociações absolutas; entrada inicial custa 100% do turnover. Custo descontado antes do retorno. Bandas podem deixar limites serem ultrapassados entre rebalanceamentos. Referências benchmark/equiponderada são brutas; não compare como se também tivessem custos. Sharpe reportado usa RF=0 e é identificado assim. Métricas incluem retorno, volatilidade e drawdown. Seleção do universo, revisões de dados e sobrevivência continuam limitações.

## Relatório integrado

HTML/PDF recebem `extras` da sessão: qualidade, risco, cenários, diagnósticos, comparação salva, otimização e avaliação rolling já executadas. A seleção ativa de risco/diagnóstico gera extras; cenários anteriores da sessão podem permanecer identificados no pacote. PDF exibe até 60 linhas por extra para controlar tamanho; CSVs no ZIP preservam conteúdo completo. Relatório não executa automaticamente uma otimização que o usuário ainda não pediu. Bootstrap em andamento só entra depois de concluído e consultado.

## Incerteza

**UNCERTAINTY** usa moving-block bootstrap com seed fixa para intervalos percentis de betas/contribuições e distribuição de pesos. As amostras preservam dependência dentro do bloco, não mudanças de regime completas. Os pesos bootstrap usam long-only e máximo 100%, sem copiar automaticamente as restrições de outra tela. Sensibilidade avalia janelas 36/60/84 e regularização 0/0.1/0.5 quando há observações suficientes. Não é prova de validade inferencial sob todo processo temporal.

Worker pool com dois threads executa bootstrap sem chamadas Streamlit no worker. Uma sessão só envia outra tarefa depois de terminar a anterior. Botão consulta resultado e permite cancelar tarefa ainda pendente; tarefas em execução não são interrompidas. Não existe broker distribuído nem quota global entre servidores. Regressões/downloads e rolling permanecem síncronos, com progresso explícito no fluxo principal.

## Alertas

**EXPOSURE MONITOR** compara resumo atual com referência SQLite: beta mercado acima do limite, mudança de sinal HML, aumento de vol. residual, fontes antigas e desvio dos últimos pesos da carteira em relação ao alvo. Referência pode usar outra moeda/amostra: o usuário precisa conferir. Não dispara ordens ou notificações externas.

## Segurança e publicação

Por padrão é um **workspace local**, sem autenticação. Para exigir login defina variáveis no ambiente do servidor:

```text
FACTORLAB_PUBLIC=1
FACTORLAB_USERS_JSON={"analista":"SALT$HASH_PBKDF2"}
FACTORLAB_DATA_DIR=/dados/factorlab
```

Gere o valor de hash com Python, sem gravar senha em código/Git:

```python
from factorlab.security import password_hash

print(password_hash("senha-forte-fornecida-localmente"))
```

O mapa JSON contém hashes PBKDF2-SHA256 com 600.000 iterações. Em modo público sem usuários a UI bloqueia acesso. Um logout limpa o estado da sessão. Diretórios de banco, uploads/snapshots e cache de preços são separados por SHA-256 do identificador do usuário. Cache de fatores públicos permanece compartilhável. Os diretórios antigos `.cache/analyses.sqlite` não são migrados silenciosamente: importe backup se quiser trazê-los para o workspace novo.

A autenticação possui espera após cinco tentativas falhas por sessão, mas **não é rate-limit por IP**; reconectar pode criar nova sessão. Para publicação real use HTTPS, proxy com rate limiting, firewall, segredos do ambiente/secret manager, backups protegidos e revisão de segurança. O aplicativo não configura TLS, SSO/OIDC, MFA, criptografia em repouso ou isolamento em processos. Não é certificado como serviço multi-tenant pronto para produção. Não coloque hashes/credenciais em relatórios ou commits.

Limites: Streamlit upload 10 MB, validação adicional na Pesquisa 10 MB, até 12 ativos incluindo benchmark, 600 meses e bootstrap máximo de 200 réplicas na UI. Não são proteção completa contra abuso. A conta do sistema operacional e os administradores do servidor podem ler diretórios dos usuários.

## Backup, restauração e retenção

**WORKSPACE ADMIN** exporta backup SQLite via API de backup consistente, valida cabeçalho, integridade e colunas antes de restaurar; exige confirmação e mantém cópia anterior. Só importe backups confiáveis. Limite de restauração 25 MB no código (upload global pode ser menor). Backup do banco não contém todos os snapshots: copie também o diretório do usuário em rotina operacional protegida.

Limpeza de snapshots anteriores a N dias é explícita, mínima de um dia; não é job automático. Pode invalidar evidências de manifestos antigos, com aviso. Não apaga banco, relatórios ou cache de preços. Configurar backup/restauração com o app parado é preferível em uso multiusuário.

## Confiabilidade e testes

Testes Chromium preservam screenshot, trace Playwright, console e log de servidor em `test-results/`, publicados no CI por sete dias. Não inclua dados privados nos artefatos. Reruns e upload/download usam estados observáveis e tentativas limitadas; isso não garante ausência de toda intermitência.

Validação desta entrega: 77 testes offline e teste Chromium aprovados antes dos ajustes finais de proteção; repetir suite ao alterar autenticação. Lint/formato executados. Integração live não foi reexecutada nesta entrega; rede externa continua dependência. Relatórios explicam hipóteses, e erros distinguem rede, dados/parâmetros e cálculo/sistema.
