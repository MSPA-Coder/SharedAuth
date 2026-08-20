# Orientações do projeto

## Papel

Biblioteca Python consumida pelos quatro apps do mantenedor: os três Flask
(ConfortoTermico, MegaSena, ControleRendaVariavel) e o ControleBancario, que
é Django e instala só o núcleo. Não é um app: não sobe sozinha, não tem
banco, não tem contêiner próprio. Existe para não deixar sessão, CSRF, hash
de senha, limite de tentativas, controle de acesso, mensagens de status,
cabeçalhos de segurança, formatação de números e rota de saúde divergirem
de novo por acidente entre os quatro projetos, como já divergiram antes
desta biblioteca existir.

Contexto completo, decisões e histórico:
`PLANO_UNIFICAR_AUTENTICACAO.md` e `PLANO_EQUALIZAR_BASE_COMPARTILHADA.md`,
no repositório `_manutencao` dos outros projetos — leia antes de qualquer
mudança de escopo ou de comportamento.

## A fronteira do núcleo

`sharedauth.security` e `sharedauth.formatting` são o **núcleo**: Python
puro, sem dependência nenhuma. É o que o ControleBancario instala. Fazer
qualquer um dos dois importar Flask ou Werkzeug em tempo de execução quebra
esse app **na instalação**, não em runtime — `tests/test_nucleo_sem_flask.py`
existe para pegar isso. Tudo que fala com Flask vai no extra `[flask]`.

## O que este pacote não decide

- **Autorização** (papéis, permissões) — fica em cada app consumidor, que
  tem necessidade real diferente do outro. Não introduza conceito de papel
  aqui.
- **Modelo de usuário** — cada app mantém o próprio (`User` do SQLAlchemy,
  com campos diferentes). Este pacote opera sobre `Flask`/`Response`/config,
  nunca sobre um modelo de dados específico.
- **`SECRET_KEY` e string de conexão** — bootstrap de cada app, com a
  própria estratégia de segredo (arquivo Docker, variável de ambiente).

## Versionamento e consumo

Os apps consomem por dependência Git fixada em tag
(`sharedauth[flask] @ git+https://.../SharedAuth.git@vX.Y.Z` nos três Flask,
sem o extra no ControleBancario), não por instalação em modo edição nem por
branch. O acesso é por PAT de leitura restrito a este repositório, injetado
como secret de build do Docker — não deploy key SSH. Uma mudança de comportamento em qualquer módulo
já consumido por um app em produção exige:

1. nova tag, nunca reescrever uma tag existente;
2. atualizar a versão fixada no app, um de cada vez, com deploy e
   verificação real antes do próximo;
3. mudança que quebre a assinatura de uma função pública é sempre versão
   maior — os três apps atualizam na hora deles, não simultaneamente.

## Validação proporcional

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
```

Sem Docker, sem banco: os testes constroem apps Flask mínimos na hora.
Qualquer módulo novo entra com teste cobrindo o caminho feliz e pelo menos
um caso de recusa (senha curta, sessão não autenticada, token CSRF ausente).

Antes de qualquer app consumir uma mudança: rodar o app localmente, fazer
login de verdade no navegador, conferir que a sessão expira como esperado e
que uma ação destrutiva continua pedindo confirmação. Bug aqui trava login
de um app em produção — a suíte automatizada não substitui esse passo.

## Prática de mudança

- Mudanças pequenas, de um módulo por vez — a separação entre `session`,
  `csrf`, `ratelimit`, `access`, `messages`, `security`, `formatting` e
  `health` é deliberada, não reorganize sem necessidade concreta de um
  consumidor real.
- Não adicione dependência nova sem que pelo menos dois dos apps
  consumidores já a usem hoje (evita puxar algo que só serve a um caso), e
  nunca no núcleo.
- Ao consolidar uma política de segurança vinda de vários apps, o padrão é
  a variante **mais restritiva**, com exceção explícita por parâmetro para
  quem precisa de folga. A união das políticas seria mais permissiva que
  qualquer uma das originais — foi assim que `img-src data:` quase virou
  regra geral por causa do favicon de dois apps.
- Histórico de decisão vai para o plano em `_manutencao`, não para
  comentário de código.
