# Orientações do projeto

## Papel e limite arquitetural

SharedAuth é uma biblioteca interna, estreita e versionada. Ela mantém
contratos transversais que já são compartilhados por múltiplos aplicativos. A
intenção é que continue estreita — sem virar um `commons` genérico nem assumir
responsabilidades das aplicações consumidoras.

O nome `SharedAuth` pode permanecer mesmo cobrindo segurança, formatação e UI.
Renomear agora imporia mudanças de imports e dependências sem ganho de
contrato.

O código fica em `src/sharedauth/`, não na raiz. É o layout `src/`: o
diretório de trabalho nunca coloca o pacote em `sys.path` por acidente, então
`pytest` só o encontra porque ele está instalado -- e a suíte exercita
exatamente o que os aplicativos consumidores recebem, arquivos de
`package-data` inclusive. Com o layout plano anterior, um CSS que ficasse de
fora do wheel passava despercebido, porque o teste lia o arquivo do
repositório.

Em geral, fica fora deste pacote:

- atomicidade, transações, modelos, migrations ou persistência de Django e
  SQLAlchemy;
- regras de domínio, autorização por papéis ou permissões;
- modelos de usuário;
- `SECRET_KEY`, outros segredos ou strings de conexão;
- decisões operacionais específicas de um consumidor.

Para decidir se uma funcionalidade nova entra, estes critérios orientam:

1. existe necessidade concreta em pelo menos dois consumidores atuais;
2. o contrato é coeso e testável isoladamente;
3. o núcleo permanece neutro de framework, ou a integração fica em extra
   explícito;
4. não existe dependência de banco de dados nem de domínio.

Conveniência futura, uma chamada duplicada em apenas um app ou a tentativa de
uniformizar regras diferentes costumam não bastar. São orientação, não portão:
um caso que fuja deles pode entrar, com o motivo registrado na mudança.

## Fronteira importável sem Flask

O pacote-base tem `dependencies = []`. Os módulos abaixo precisam continuar
importáveis sem carregar Flask, Werkzeug, Flask-WTF ou Flask-Limiter:

- `sharedauth.security`: constantes e montagem de CSP são Python puro; a
  função de registro recebe o objeto web pronto e não importa Flask em runtime;
- `sharedauth.formatting`: formatação numérica em Python puro;
- `sharedauth.config`: leitura de flag de ambiente e montagem da URL do
  PostgreSQL são `os.environ` e `urllib.parse`, sem driver nem ORM;
- `sharedauth.secrets`: leitura de segredo por arquivo é `pathlib` e
  `os.environ`, sem framework;
- `sharedauth.ui`: caminho dos assets, severidades e SVG são independentes;
  imports de Flask e MarkupSafe permanecem locais às funções de integração;
- `sharedauth.logs`: sanitização de texto para log, em Python puro;
- `sharedauth.passwords`: a política de senha é Python puro; o Werkzeug entra
  só dentro das funções de hash, na primeira chamada;
- `sharedauth.session`: a amarra entre sessão e senha é Python puro; o Flask
  só entra em `configurar_sessao`.

`tests/test_nucleo_sem_flask.py` guarda essa fronteira em um interpretador
limpo. Tudo que exige Flask/Werkzeug pertence ao extra `[flask]`; um import de
integração no topo de um desses módulos quebra a fronteira, e o teste reprova.

## Contratos públicos

A lista de módulos e o contrato de cada um estão na tabela "Módulos públicos"
do `README.md`, mantida num lugar só.

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

Os consumidores fixam a dependência por tag Git; a atual é `v0.13.0`:

```text
sharedauth @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.13.0
sharedauth[flask] @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.13.0
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
- Dependência nova precisa ter a compatibilidade confirmada nos consumidores.
- Mantenha defaults de segurança fechados; exceções precisam ser explícitas no
  ponto de consumo e cobertas por teste.
- Toda alteração pública deve ter caminho feliz e caso de recusa ou falha.
- Não grave tokens, credenciais ou strings de conexão no repositório.

## Validação

O loop normal é o venv do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

O `.venv/` é uma pasta do projeto, já ignorada pelo Git: não altera o Python
do sistema nem o PATH, e apagar a pasta desfaz a instalação por inteiro. A
proibição que vale é outra -- nada de instalar dependências do projeto no
Python global do Windows.

Este repositório não possui Compose nem Dockerfile. Quando a validação em Linux
importar (antes de publicar uma tag, por exemplo), use a imagem oficial em
contêiner efêmero, com a fonte montada somente para leitura:

```powershell
docker run --rm `
  --mount "type=bind,source=$($PWD.Path),target=/fonte,readonly" `
  python:3.14-slim `
  sh -lc "cp -r /fonte /tmp/src && cd /tmp/src && python -m pip install --disable-pip-version-check '.[dev]' && python -m pytest -q -p no:cacheprovider"
```

A cópia para `/tmp/src` não é enfeite: `pip install` grava metadados de build
ao lado do `pyproject.toml`, e instalar direto sobre a montagem somente-leitura
falha com `Cannot update time stamp of directory`. Copiar preserva a garantia
que a montagem existia para dar -- o contêiner não escreve no repositório -- e
ainda instala o pacote de verdade, não em modo editável, que é o que os
aplicativos consumidores recebem.

Se rede, proxy ou CA impedir o download, registre o bloqueio; não improvise uma
instalação no Python global. Antes de encerrar, execute no host as verificações
que não exigem runtime do projeto:

```powershell
git diff --check
git status --short
```

Faça também buscas por referências obsoletas e confira se todos os caminhos e
links citados existem. No encerramento, informe separadamente os comandos
executados no host e no contêiner.
