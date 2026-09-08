# matricula-disciplinas

Servico responsavel pela oferta de turmas: mantem o catalogo de disciplinas e as turmas disponiveis para matricula.

Este repositorio contem **apenas o esqueleto do servico**: aplicacao FastAPI com
endpoints de identificacao e health, configuracao via variaveis de ambiente,
testes, imagem Docker e pipeline de CI/CD. As regras de negocio, o modelo de
dados, a conexao com o banco e o consumo de filas sao entregas posteriores.

| Item | Valor |
| --- | --- |
| Porta | `8001` |
| Imagem Docker | `nadertaha06/matricula-disciplinas` |
| Container na EC2 | `matricula-disciplinas` |
| Banco de dados | `disciplinas_db` |
| Rede Docker | `rede` |

## Endpoints

| Metodo | Rota | Resposta |
| --- | --- | --- |
| `GET` | `/` | `{"service": "matricula-disciplinas"}` |
| `GET` | `/health` | `{"status": "ok", "service": "matricula-disciplinas"}` |

Documentacao interativa gerada pelo FastAPI em `http://localhost:8001/docs`.

## Rodando local

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # ajuste os valores; o .env nao vai para o git

uvicorn app.main:app --reload --port 8001
```

Conferindo:

```bash
curl http://localhost:8001/health
# {"status":"ok","service":"matricula-disciplinas"}
```

## Rodando os testes

```bash
pytest
```

O `pyproject.toml` ja configura `--cov=app --cov-report=term-missing
--cov-report=html:coverage --cov-fail-under=80`, entao o comando falha sozinho
se a cobertura cair abaixo de 80%.

### Painel de cobertura

Alem da tabela no terminal, o `pytest` gera um relatorio HTML navegavel em
`coverage/index.html` — o equivalente ao relatorio do JaCoCo usado nos projetos
em Java. Ele mostra o percentual por arquivo e, clicando em cada um, o codigo
linha a linha em verde (coberto) e vermelho (nao coberto).

```bash
pytest
open coverage/index.html      # no Linux: xdg-open coverage/index.html
```

O relatorio e versionado de proposito, para ficar visivel no repositorio. Ele e
regerado a cada `pytest`, entao aparece como alteracao no `git status` sempre
que os testes rodam.

## Buildando a imagem

```bash
docker build -t nadertaha06/matricula-disciplinas:latest .

docker run --rm -p 8001:8001 --env-file .env \
  nadertaha06/matricula-disciplinas:latest
```

Para rodar junto da infraestrutura do repositorio `matricula-infra`, suba o
container na mesma rede:

```bash
docker run -d --name matricula-disciplinas --network rede --restart unless-stopped \
  -p 8001:8001 --env-file .env \
  nadertaha06/matricula-disciplinas:latest
```

## Variaveis de ambiente

Todas sao lidas por `app/config.py` (`Settings` do `pydantic-settings`).
Veja `.env.example` para um modelo preenchido com valores de exemplo.

| Variavel | Descricao | Exemplo |
| --- | --- | --- |
| `APP_NAME` | Nome do servico, devolvido em `/` e `/health` | `matricula-disciplinas` |
| `PORT` | Porta em que o uvicorn escuta | `8001` |
| `DB_HOST` | Host do Postgres. Na EC2 e o `container_name` definido no `matricula-infra` | `postgres` |
| `DB_PORT` | Porta do Postgres | `5432` |
| `DB_NAME` | Banco usado por este servico | `disciplinas_db` |
| `DB_USER` | Usuario do Postgres | `postgres` |
| `DB_PASSWORD` | Senha do Postgres. Vem do secret `DB_PASSWORD` | *(secret)* |
| `RABBITMQ_URL` | URL AMQP do RabbitMQ. Vem do secret `RABBITMQ_URL` | `amqp://usuario:senha@rabbitmq:5672/` |
| `AUTH0_DOMAIN` | Dominio do tenant Auth0. Vem do secret `AUTH0_DOMAIN` | `seu-tenant.us.auth0.com` |
| `AUTH0_AUDIENCE` | Audience da API no Auth0. Vem do secret `AUTH0_AUDIENCE` | `https://api.matricula.exemplo` |

`get_settings()` e decorada com `@lru_cache`, o que implementa o padrao
**Singleton**: a instancia de `Settings` e construida uma unica vez por processo.

## CI/CD

`.github/workflows/deploy.yml` tem dois jobs:

- **test** — roda em `push` na `main` e em `pull_request`. Sobe um `postgres:16`
  real pelo bloco `services:` do GitHub Actions (healthcheck com `pg_isready`),
  instala as dependencias e roda o `pytest` com o corte de cobertura.
- **deploy** — depende do `test` (`needs`) e roda **somente** em `push` na
  `main`. Faz login no DockerHub, builda e publica a imagem com as tags
  `${{ github.sha }}` e `latest`, e entao conecta por SSH na EC2 para trocar o
  container.

Para adaptar o workflow a outro servico basta editar o bloco `env:` do topo do
arquivo (`IMAGE`, `CONTAINER`, `PORT`, `DB_NAME`).

### Secrets necessarios neste repositorio

| Secret | Para que serve |
| --- | --- |
| `DOCKERHUB_TOKEN` | Access token do DockerHub do usuario `nadertaha06` |
| `HOST_TEST` | IP ou DNS publico da EC2 |
| `KEY_TEST` | Chave SSH privada do usuario `ubuntu` |
| `DB_PASSWORD` | Senha do Postgres, igual a do `matricula-infra` |
| `RABBITMQ_URL` | URL AMQP completa do RabbitMQ |
| `AUTH0_DOMAIN` | Dominio do tenant Auth0 |
| `AUTH0_AUDIENCE` | Audience da API no Auth0 |
