# Orientações do projeto

## Papel e limite arquitetural

SharedAuth é uma biblioteca interna, estreita e versionada. Ela mantém
contratos transversais que já são compartilhados por múltiplos aplicativos;
não deve crescer como um `commons` genérico nem assumir responsabilidades das
aplicações consumidoras.

O nome `SharedAuth` pode permanecer mesmo cobrindo segurança, formatação e UI.
Renomear agora imporia mudanças de imports e dependências sem ganho de
contrato.

Não mova para este pacote:

- atomicidade, transações, modelos, migrations ou persistência de Django e
  SQLAlchemy;
- regras de domínio, autorização por papéis ou permissões;
- modelos de usuário;
- `SECRET_KEY`, outros segredos ou strings de conexão;
- decisões operacionais específicas de um consumidor.

Uma funcionalidade nova só entra quando todos estes critérios forem atendidos:

1. existe necessidade concreta em pelo menos dois consumidores atuais;
2. o contrato é coeso e testável isoladamente;
3. o núcleo permanece neutro de framework, ou a integração fica em extra
   explícito;
4. não existe dependência de banco de dados nem de domínio.

Conveniência futura, uma chamada duplicada em apenas um app ou a tentativa de
uniformizar regras diferentes não satisfazem esses critérios.

## Fronteira importável sem Flask

O pacote-base tem `dependencies = []`. Os módulos abaixo precisam continuar
importáveis sem carregar Flask, Werkzeug, Flask-WTF ou Flask-Limiter:

- `sharedauth.security`: constantes e montagem de CSP são Python puro; a
  função de registro recebe o objeto web pronto e não importa Flask em runtime;
- `sharedauth.formatting`: formatação numérica em Python puro;
- `sharedauth.config`: leitura de flag de ambiente e montagem da URL do
  PostgreSQL são `os.environ` e `urllib.parse`, sem driver nem ORM;
- `sharedauth.ui`: caminho dos assets, severidades e SVG são independentes;
  imports de Flask e MarkupSafe permanecem locais às funções de integração.

`tests/test_nucleo_sem_flask.py` guarda essa fronteira em um interpretador
limpo. Tudo que exige Flask/Werkzeug pertence ao extra `[flask]`. Não mova um
import de integração para o topo de `security` ou `ui`.

## Contratos existentes na v0.4.0

- `security`: cabeçalhos defensivos, CSP e registro em Flask/Blueprint;
- `formatting`: números, inteiros, moedas e percentuais em pt-BR;
- `config`: leitura de flag booleana do ambiente (com modo estrito) e
  montagem da URL do PostgreSQL com escape correto;
- `ui`: assets CSS/JS, integração de estáticos com Django ou Flask e ícones;
- `passwords`: validação, hash e conferência de senha com Werkzeug;
- `session`: opções de cookies de sessão e de “lembrar-me” no Flask,
  incluindo a duração de ambos;
- `csrf`: uma instância de `CSRFProtect` por app;
- `ratelimit`: uma instância de `Limiter` por app, limite padrão de login,
  política opcional do consumidor e aplicação/isenção de limite por endpoint;
- `access`: proteção padrão-nega, respostas adequadas a HTML, API e HTMX, e
  verificação binária de papel na camada de view;
- `messages`: templates normal/OOB e CSS de mensagens Flask;
- `health`: rota de saúde, sonda fornecida pelo consumidor e isenção opcional
  do limiter.

### Sobre o critério "não uniformizar regras diferentes"

Ele continua valendo, e continua recusando a tentativa de forçar dois
consumidores a se comportarem igual. Mas ele **não** recusa parametrizar uma
mecânica comum para que cada consumidor declare a sua regra — foi o que
entrou na v0.4.0 em `config.ler_flag` (`estrito=`) e em
`ratelimit.iniciar_limiter` (política do consumidor).

A diferença de teste: se a proposta obriga alguém a mudar de comportamento,
está fora; se ela deixa cada um escrever o comportamento que já tem, num lugar
só e com teste, está dentro.

Preserve a separação entre módulos. Um módulo novo ou uma reorganização exige
necessidade concreta nos consumidores e testes do contrato público.

## Rate limit

A biblioteca inicializa o Flask-Limiter e fornece a política padrão de login,
mas não decide o backend operacional. Storage em memória é por processo e não
coordena contadores entre workers, contêineres ou hosts; `memory://` não é
proteção completa de produção.

Nos VPS atuais, o Nginx compartilhado limita também `POST /login`. Se a
topologia mudar, o consumidor deve configurar storage compartilhado para o
limiter ou proteção equivalente na borda. Configuração, disponibilidade e
monitoramento desse backend permanecem no consumidor.

## Versionamento e consumo

Os consumidores fixam a dependência por tag Git. Use `v0.4.0` nos exemplos
atuais:

```text
sharedauth @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.4.0
sharedauth[flask] @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.4.0
```

Tags publicadas são imutáveis: nunca reescreva uma tag. Toda mudança pública
exige nova versão/tag e validação nos consumidores que a adotarem. Mudanças
incompatíveis de assinatura ou semântica devem incrementar a versão de acordo
com o impacto. A adoção não é implícita nem simultânea: cada app mantém sua tag
fixada até concluir seus próprios testes e deploy.

Antes da atualização de um consumidor, valide o contrato afetado no contexto
real. Para autenticação e segurança, isso inclui build/testes, login no
navegador, expiração de sessão e uma ação protegida por CSRF/confirmação.

## Prática de mudança

- Leia `AGENTS.md`, `README.md`, `pyproject.toml`, os módulos e os testes
  relacionados antes de editar.
- Preserve mudanças locais não relacionadas.
- Não adicione dependência sem satisfazer os critérios de entrada e sem
  confirmar compatibilidade nos consumidores.
- Mantenha defaults de segurança fechados; exceções precisam ser explícitas no
  ponto de consumo e cobertas por teste.
- Toda alteração pública deve ter caminho feliz e caso de recusa ou falha.
- Não grave tokens, credenciais ou strings de conexão no repositório.

## Validação

Não instale Python, dependências, linters ou test runners no host. Este
repositório não possui Compose nem Dockerfile; não adicione infraestrutura só
para executar a suíte. Use a imagem oficial em contêiner efêmero, com a fonte
montada somente para leitura:

```powershell
docker run --rm `
  --mount "type=bind,source=$($PWD.Path),target=/workspace,readonly" `
  --workdir /workspace `
  python:3.13-slim `
  sh -lc "python -m pip install --disable-pip-version-check '.[dev]' && python -m pytest -q -p no:cacheprovider"
```

Se rede, proxy ou CA impedir o download, registre o bloqueio; não improvise uma
instalação no host. Antes de encerrar, execute no host as verificações que não
exigem runtime do projeto:

```powershell
git diff --check
git status --short
```

Faça também buscas por referências obsoletas e confira se todos os caminhos e
links citados existem. No encerramento, informe separadamente os comandos
executados no host e no contêiner.
