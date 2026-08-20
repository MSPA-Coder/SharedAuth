# SharedAuth

Rotinas de base compartilhadas entre os projetos do mantenedor. Não é
framework novo, não é SSO: é o que ConfortoTermico, MegaSena,
ControleBancario e ControleRendaVariavel já faziam cada um por conta própria
— sessão, CSRF, limite de tentativas, hash de senha, controle de acesso por
padrão-nega, mensagens de status, cabeçalhos de segurança, formatação de
números em pt-BR e rota de saúde — extraído uma vez para não divergir de
novo por acidente, como divergiu (piso de senha em 2, 8 e 15; erro do
MegaSena mostrado com a cor de sucesso; `font-src data:` liberado num app que
não tem fonte embutida).

O nome do pacote é anterior a metade do que ele cobre hoje. Renomear
quebraria os imports e o encanamento de token/CI dos apps consumidores por
ganho cosmético — decisão registrada, não descuido.

Plano completo, decisões e histórico: `PLANO_UNIFICAR_AUTENTICACAO.md` e
`PLANO_EQUALIZAR_BASE_COMPARTILHADA.md`, no repositório `_manutencao` dos
outros projetos do mantenedor.

## Escopo

**Não** cobre:

- **Autorização** (papéis, permissões) — cada app tem necessidade real
  diferente (ConfortoTermico com 6 perfis por área, MegaSena
  deliberadamente sem papel nenhum, ControleRendaVariavel com 2 papéis
  binários) e continua decidindo isso sozinho.
- **Identidade visual** — cada app tem paleta própria de propósito. O CSS de
  mensagens de status é a única exceção, e vem daqui.
- **Tela de administração de usuários** — depende do modelo de usuário de
  cada app, que é genuinamente diferente.
- **Login único (SSO)** — cada app continua autenticando por conta própria,
  dentro do próprio processo.

## Módulos

Núcleo — Python puro, sem dependência nenhuma:

| Módulo | O que faz |
|---|---|
| `sharedauth.security` | `SECURITY_HEADERS` + Content-Security-Policy fechada, e o gancho que aplica os dois no Flask |
| `sharedauth.formatting` | número, moeda e percentual no padrão brasileiro |

Extra `flask` — precisa de Flask/Werkzeug:

| Módulo | O que faz |
|---|---|
| `sharedauth.passwords` | hash (Werkzeug) + piso de 8 caracteres |
| `sharedauth.session` | cookie de sessão: HttpOnly, SameSite=Lax, Secure se HTTPS |
| `sharedauth.csrf` | inicialização padrão do Flask-WTF |
| `sharedauth.ratelimit` | Flask-Limiter com limite padrão de login (10/min) |
| `sharedauth.access` | `before_request` de padrão-nega, com ou sem `HX-Redirect` |
| `sharedauth.messages` | mensagens de status: 4 categorias, template normal e OOB para HTMX |
| `sharedauth.health` | `GET /health` que consulta o banco, isento de rate limit |

A divisão existe porque o ControleBancario é Django: ele instala só o núcleo,
para compartilhar a política de cabeçalhos e a conta de formatação sem
arrastar um framework web que não usa. `tests/test_nucleo_sem_flask.py`
guarda essa fronteira — o núcleo importar Flask quebraria o ControleBancario
na instalação, não em runtime.

## Uso

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Cada app consumidor referencia por dependência Git com tag, não PyPI público
— não há razão para publicar isto fora do necessário. Os três apps Flask:

```
sharedauth[flask] @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.2.0
```

O ControleBancario, sem o extra:

```
sharedauth @ git+https://github.com/MSPA-Coder/SharedAuth.git@v0.2.0
```

Acesso por PAT de leitura restrito a este repositório, injetado como secret
de build do Docker — não deploy key SSH. Ver seção 10 do
`PLANO_UNIFICAR_AUTENTICACAO.md` para o mecanismo completo.

## Ordem de adoção

MegaSena e ControleRendaVariavel primeiro (menor risco) → ConfortoTermico
depois → ControleBancario por último, e só o núcleo.

## Verificação

```powershell
python -m pytest -q
```

Sem Docker, sem banco — os testes rodam contra apps Flask mínimos criados na
hora, isolados de qualquer projeto consumidor.
