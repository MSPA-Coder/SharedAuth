# SharedAuth — guia de trabalho

<!-- comum: início. Cópia de _manutencao/compartilhados/AGENTS-comum.md; mude lá e rode sincronizar.py --aplicar. -->
## Regras comuns aos repositórios

**O que espera o "sim" do mantenedor:** commit e push (quando ele pedir),
deploy, qualquer ação no VPS, e apagar dados, volumes ou backups
(`docker compose down -v` inclusive). Na dúvida sobre algo irreversível,
pergunte; no resto, decida e diga o que decidiu.

**Ciclo.** Altere, rode a verificação completa deste repositório (seção
"Validação"), commite direto no `main` e dê `git push`: sem PR, sem push
forçado, sem rebase do `main` publicado. A CI roda depois, só como aviso, mas
vermelho no `main` se investiga. O Dependabot chega por PR, com merge manual. O
deploy é `~/deploy.sh <app>` no VPS1: monta a imagem a partir do `main`,
confere `/health` e volta sozinho se falhar. O VPS só espelha o `main`; nada se
edita lá. Imagem-base nova (correção do Debian ou do Python) só quando ele
pedir: testa na máquina e depois `~/deploy.sh <app> --refresh`. Ao terminar,
diga o que rodou, o resultado e o que deixou de validar.

**Dados e segredos.** Mudança destrutiva ou conversão de dados reais começa por
backup conferido no BackupRestore. Segredos ficam fora do Git (`.secrets/` ou
configuração do usuário) e não aparecem em código, imagem, log, diff,
documento nem relatório.

**Dependências.** Alargue o teto e preserve o piso já verificado: elevar o piso
afirma uma incompatibilidade, e isso exige prova. Vulnerabilidade se corrige
atualizando; exceção só explícita, com motivo e data. Enquanto o Dependabot não
aceitar Python 3.15, ele não propõe atualização de `uv` e o grafo do GitHub fica
parado no lock de 13/10/2026: confira alerta pela versão do `uv.lock`, e
atualize à mão (`uv lock --upgrade-package <pacote>`) quando o `pip-audit` ou o
Trivy apontarem.

**Testes.** `docs/TESTES.md` diz o que testar e como. Diante de vermelho,
decida de quem é o defeito; nunca escreva código para um teste passar. Não
rode duas verificações do mesmo repositório ao mesmo tempo: a segunda recria o
banco de teste e derruba a primeira.

**Cópias.** Este bloco, `docs/TESTES.md` e os arquivos listados em
`_manutencao/compartilhados/sincronizar.py` são cópias: mude a canônica lá e
rode `python compartilhados/sincronizar.py --aplicar` no `_manutencao`.

**Este arquivo.** Guarde aqui só o que o código não diz: limites, decisões com
o motivo, armadilhas e comandos. História fica no `git log`; decisão com
alternativas vira ADR; detalhe de implementação fica no código. Para
acrescentar uma regra, retire ou funda outra: `sincronizar.py` reprova este
arquivo acima de 900 palavras fora deste bloco.
<!-- comum: fim -->

## O pacote

Biblioteca pública, estreita e versionada, com os contratos transversais que
os aplicativos já compartilham: sessão, CSRF, limite de login, senhas,
cabeçalhos e CSP, formatação, segredos por arquivo, UI comum e `/health`. Não
é um `commons` genérico. O nome fica, embora cubra mais que autenticação:
renomear mudaria imports em todos os consumidores sem ganho de contrato. A
tabela "Módulos públicos" do `README.md` é a lista de módulos e contratos.

Fica fora: transação, modelo, migração ou persistência (Django ou SQLAlchemy);
regra de domínio, papéis e permissões; modelo de usuário; segredos e strings de
conexão; decisão operacional de um consumidor só.

Para entrar algo novo, servem de guia: necessidade concreta em pelo menos dois
consumidores atuais, contrato coeso e testável isolado, núcleo neutro de
framework (integração em extra explícito) e nenhuma dependência de banco ou
domínio. São orientação, não portão: um caso fora deles pode entrar com o
motivo registrado. "Não uniformizar regras diferentes" recusa obrigar dois
consumidores a se comportarem igual, mas aceita parametrizar uma mecânica comum
para cada um declarar a sua regra (como `config.ler_flag(estrito=)` e a
política do consumidor em `ratelimit.iniciar_limiter`).

## Validação

```powershell
docker compose --profile quality build --pull quality
docker compose --profile quality run --build --rm --no-deps quality
docker compose --profile quality run --rm --no-deps audit
```

Os três, completos, antes de todo commit. O `.venv` local não é necessário.

- Só documentação: `git diff --check` e
  `python ../_manutencao/compartilhados/sincronizar.py`.
- Antes de um consumidor adotar uma tag nova, valide o contrato afetado nele:
  em autenticação e segurança, build e testes, login no navegador, expiração de
  sessão e uma ação protegida por CSRF ou confirmação.

## Limites que o código não mostra sozinho

- **Layout `src/`.** O pacote só entra no `sys.path` instalado, então a suíte
  exercita o que os consumidores recebem, `package-data` inclusive. No layout
  plano anterior, um CSS fora do wheel passava despercebido.
- **Núcleo sem Flask.** O pacote-base tem `dependencies = []`, e `security`,
  `formatting`, `config`, `secrets`, `ui`, `logs`, `passwords` e `session`
  precisam importar sem Flask, Werkzeug, Flask-WTF ou Flask-Limiter; import de
  integração fica dentro da função ou no extra `[flask]`.
  `tests/test_nucleo_sem_flask.py` guarda isso num interpretador limpo.
- **Defaults fechados.** Exceção de segurança é explícita no ponto de consumo
  e coberta por teste; alteração pública tem caminho feliz e recusa.
- **Rate limit.** A biblioteca inicia o Flask-Limiter e dá a política de login,
  mas o backend é do consumidor: `memory://` conta por processo. Nos VPS, o
  Nginx limita o `POST /login` de verdade.

## Versão e release

Os consumidores fixam a dependência por tag Git
(`sharedauth @ git+https://github.com/MSPA-Coder/SharedAuth.git@vX.Y.Z`, com
`[flask]` onde precisam da integração). Tag publicada é imutável. Toda mudança
pública ganha versão nova, pelo impacto. A tag nasce depois do push, sobre o
commit no `main`, e ganha na hora uma release com o que entra e o que muda na
adoção (`gh release create vX.Y.Z --verify-tag --notes-file notas.md`): a
página de releases é o changelog. A adoção não é simultânea; cada app mantém a
sua tag até passar nos próprios testes e no deploy.
