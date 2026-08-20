# SharedAuth

Rotinas de login e mensagens compartilhadas entre os apps Flask do
mantenedor. Não é framework novo, não é SSO: é o que ConfortoTermico,
MegaSena e ControleRendaVariavel já faziam cada um por conta própria —
sessão, CSRF, limite de tentativas, hash de senha, controle de acesso por
padrão-nega e mensagens de status — extraído uma vez para não divergir de
novo por acidente, como divergiu (piso de senha em 2, 8 e 15; erro do
MegaSena mostrado com a cor de sucesso).

Plano completo, decisões e histórico: `PLANO_UNIFICAR_AUTENTICACAO.md`, no
repositório `_manutencao` dos outros quatro projetos do mantenedor.

## Escopo

Cobre o que é o mesmo trabalho nos três apps Flask. **Não** cobre:

- **Autorização** (papéis, permissões) — cada app tem necessidade real
  diferente (ConfortoTermico com 6 perfis por área, MegaSena
  deliberadamente sem papel nenhum, ControleRendaVariavel com 2 papéis
  binários) e continua decidindo isso sozinho.
- **ControleBancario** — é Django, framework incompatível; acompanha só a
  mesma *política* (piso de senha), sem compartilhar código.
- **Login único (SSO)** — cada app continua autenticando por conta própria,
  dentro do próprio processo.

## Módulos

| Módulo | O que faz |
|---|---|
| `sharedauth.passwords` | hash (Werkzeug) + piso de 8 caracteres |
| `sharedauth.session` | cookie de sessão: HttpOnly, SameSite=Lax, Secure se HTTPS |
| `sharedauth.csrf` | inicialização padrão do Flask-WTF |
| `sharedauth.ratelimit` | Flask-Limiter com limite padrão de login (10/min) |
| `sharedauth.access` | `before_request` de padrão-nega, com ou sem `HX-Redirect` |
| `sharedauth.messages` | mensagens de status: 4 categorias, template normal e OOB para HTMX |

## Uso

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

Cada app consumidor referencia por dependência Git com tag, não PyPI público
— não há razão para publicar isto fora do necessário:

```
sharedauth @ git+ssh://git@github.com/MSPA-Coder/SharedAuth.git@v0.1.0
```

Acesso via deploy key somente-leitura, mesmo padrão já usado pelos quatro
projetos para os próprios repositórios.

## Ordem de adoção

MegaSena e ControleRendaVariavel primeiro (já usam Flask-Login, menor
risco) → ConfortoTermico por último (mecanismo de sessão/CSRF inteiramente
próprio hoje, mais a perder) → ControleBancario nunca consome este pacote,
só acompanha a política de piso de senha.

## Verificação

```powershell
python -m pytest -q
```

Sem Docker, sem banco — os testes rodam contra apps Flask mínimos criados na
hora, isolados de qualquer projeto consumidor.
