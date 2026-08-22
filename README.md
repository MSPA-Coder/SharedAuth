# SharedAuth

Biblioteca Python interna e versionada com contratos transversais já usados
por mais de um aplicativo do mantenedor. O pacote reúne segurança,
formatação e componentes de interface que precisam permanecer iguais entre
consumidores; não é SSO, framework de aplicação nem um `commons` genérico.

O nome `SharedAuth` permanece mesmo com o escopo atual além de autenticação.
Renomeá-lo agora mudaria imports e dependências dos consumidores sem melhorar
os contratos oferecidos.

## Escopo e critérios de entrada

Um contrato novo só pertence a este pacote quando atende a todos os critérios:

- há necessidade real em pelo menos dois consumidores atuais;
- o contrato é coeso e pode ser testado de forma isolada;
- o núcleo permanece neutro de framework, ou a integração usa um extra
  explícito;
- não há dependência de banco de dados nem de regras de domínio.

Conveniência futura, uma única chamada duplicada ou a tentativa de uniformizar
regras que são legitimamente diferentes entre aplicativos não justificam uma
adição.

Permanecem nos consumidores:

- atomicidade, transações, modelos, migrations e persistência em Django ou
  SQLAlchemy;
- regras de domínio e autorização por papéis ou permissões;
- modelo de usuário e telas administrativas associadas;
- `SECRET_KEY`, outros segredos e strings de conexão;
- identidade visual específica e decisões operacionais de infraestrutura.

## Instalação e fronteira de dependências

A versão atual é `0.3.0`. Os consumidores instalam diretamente da tag Git,
sem acompanhar branch ou usar instalação editável.

Aplicativo que usa somente o núcleo:

```text
sharedauth @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.3.0
```

Aplicativo Flask:

```text
sharedauth[flask] @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.3.0
```

O pacote-base não declara dependências. Estes módulos podem ser importados
sem carregar Flask, Werkzeug, Flask-WTF ou Flask-Limiter:

- `sharedauth.security` — constantes e montagem de cabeçalhos/CSP; a função de
  registro recebe um app ou blueprint pronto por tipagem estrutural;
- `sharedauth.formatting` — números, inteiros, moedas e percentuais em pt-BR;
- `sharedauth.ui` — caminhos dos assets, severidades e geração de SVG; os
  imports necessários à integração Flask ficam dentro das funções de registro.

O extra `[flask]` instala Flask, Flask-WTF, Flask-Limiter e Werkzeug para os
demais módulos e para as funções Flask de `security` e `ui`.

## Módulos públicos

| Módulo | Contrato |
|---|---|
| `sharedauth.security` | Cabeçalhos defensivos, CSP fechada por padrão, `montar_csp` e registro em Flask/Blueprint. |
| `sharedauth.formatting` | `numero`, `inteiro`, `moeda`, `moeda_com_sinal` e `percentual`, com opções explícitas de ausência e zero. |
| `sharedauth.ui` | Assets CSS/JS, caminho para estáticos no Django, blueprint estático no Flask, severidades, ícones SVG e global Jinja. |
| `sharedauth.passwords` | Piso de senha, validação, hash e conferência por Werkzeug. |
| `sharedauth.session` | Configuração dos cookies de sessão e de “lembrar-me” no Flask. |
| `sharedauth.csrf` | Inicialização isolada de `CSRFProtect` por app Flask. |
| `sharedauth.ratelimit` | Inicialização isolada de `Limiter` por app e política padrão de login de 10 tentativas por minuto. |
| `sharedauth.access` | Proteção padrão-nega para rotas Flask, com redirect HTML, resposta de API e `HX-Redirect`. |
| `sharedauth.messages` | Blueprint com templates de flash normal/OOB para HTMX e CSS das quatro severidades. |
| `sharedauth.health` | Registro de `GET /health`, sonda opcional e isenção explícita do limiter. |

`sharedauth.ui` entrega `CAMINHO_ESTATICO` para `STATICFILES_DIRS` do Django e
`registrar_ui(app)` para Flask. Já `messages`, `health`, `access`, `session`,
`csrf`, `passwords` e `ratelimit` exigem o extra `[flask]`.

## Rate limit e topologia

`sharedauth.ratelimit` fornece a inicialização e a política de login; ele não
escolhe a arquitetura de armazenamento nem a proteção de borda. O armazenamento
em memória é local ao processo e não coordena contadores entre workers,
contêineres ou servidores. Portanto, `memory://` não deve ser tratado como
proteção completa de produção.

Nos VPS atuais, o Nginx compartilhado também limita `POST /login`. Uma topologia
diferente precisa manter proteção equivalente na borda ou configurar storage
compartilhado para o Flask-Limiter. Essa decisão e sua operação pertencem a
cada consumidor.

## Versionamento

Tags publicadas são imutáveis e nunca são reescritas. Toda mudança de contrato
público ou de comportamento compartilhado exige nova versão/tag e validação em
cada consumidor que adotar a atualização. Mudança incompatível de assinatura
ou semântica requer incremento de versão compatível com esse impacto; os
aplicativos podem atualizar em momentos diferentes porque suas dependências
continuam fixadas em tags.

Além da suíte desta biblioteca, a adoção deve validar no consumidor ao menos o
build, os testes, o login real, a expiração da sessão e uma ação protegida por
CSRF/confirmação, conforme o contrato alterado.

## Validação local sem instalar ferramentas no host

O repositório não possui `compose.yaml` nem `Dockerfile`. Com Docker Desktop
disponível, execute a suíte em um contêiner efêmero oficial do Python, montando
a fonte somente para leitura:

```powershell
docker run --rm `
  --mount "type=bind,source=$($PWD.Path),target=/workspace,readonly" `
  --workdir /workspace `
  python:3.13-slim `
  sh -lc "python -m pip install --disable-pip-version-check '.[dev]' && python -m pytest -q -p no:cacheprovider"
```

O `pip` desse comando existe apenas no contêiner. A montagem somente para
leitura e o cache do pytest desativado evitam artefatos na árvore de trabalho.
