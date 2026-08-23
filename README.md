# Smart Balance Backend

Backend da aplicacao Smart Balance, desenvolvido como projeto academico da UNISANTA.

Esta API foi criada com FastAPI e PostgreSQL para gerenciar funcionalidades relacionadas a usuarios, alimentos, nutrientes, refeicoes e busca/reconhecimento de alimentos. A aplicacao tambem serve imagens estaticas pela rota `/images`.

## Tecnologias

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Docker
- Docker Compose
- GitHub Actions
- Docker Hub

## Estrutura Principal

```text
.
|-- .github/workflows/deploy.yml
|-- application/
|-- images/
|-- scripts/
|-- shared/
|-- compose.yml
|-- Dockerfile
|-- main.py
|-- requirements.txt
`-- .env.example
```

## Variaveis de Ambiente

Crie um arquivo `.env` na raiz do projeto, ao lado do `compose.yml`.

Exemplo:

```env
POSTGRES_DB=Smart-Balance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-this-password
BASE_URL=http://localhost:8000
```

Essas variaveis sao usadas pelo Docker Compose para criar o banco PostgreSQL e montar a URL de conexao da API:

```text
postgresql://POSTGRES_USER:POSTGRES_PASSWORD@db:5432/POSTGRES_DB
```

Em outra maquina, o `.env` nao precisa ser identico, mas precisa ter as mesmas variaveis. A senha pode mudar, desde que seja a senha usada pelo PostgreSQL daquele ambiente.

## Rodando com Docker Compose

Na pasta raiz do projeto:

```powershell
docker compose up -d
```

Isso sobe dois containers:

- `sb-backend`: API FastAPI publicada na porta `8000`
- `sb-postgres`: banco PostgreSQL usado pela API

Para testar:

```powershell
curl http://localhost:8000/health
```

Resposta esperada:

```json
{
  "status": "healthy",
  "database": "available"
}
```

Tambem e possivel abrir a documentacao da API em:

```text
http://localhost:8000/docs
```

## Publicando a Imagem no Docker Hub

O workflow em `.github/workflows/deploy.yml` publica a imagem:

```text
linkado36778/sb-backend:latest
```

Ele roda automaticamente quando houver push na branch `main` ou em tags no formato `v*.*.*`.

Antes de usar o workflow, configure estes secrets no GitHub:

```text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
```

`DOCKERHUB_USERNAME` deve ser apenas o nome de usuario do Docker Hub.

`DOCKERHUB_TOKEN` deve ser um Access Token do Docker Hub com permissao de escrita. Nao use a senha da conta.

Para disparar a publicacao:

```powershell
git add .
git commit -m "Configure Docker Hub deployment"
git push origin main
```

Depois que o GitHub Actions terminar, a imagem ficara disponivel no Docker Hub.

## Rodando a Imagem em Outra Maquina

Na outra maquina, a pessoa precisa ter o Docker Desktop instalado e rodando.

Ela nao precisa do codigo inteiro para executar a API. O minimo necessario e:

```text
compose.yml
.env
smart-balance.sql
```

Se quiser manter simples, copie o projeto inteiro.

Crie uma pasta para o deploy, por exemplo:

```text
SmartBalanceDeploy
```

Coloque dentro dela os arquivos:

```text
compose.yml
.env
smart-balance.sql
```

O arquivo `.env` pode ser assim:

```env
POSTGRES_DB=Smart-Balance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-this-password
BASE_URL=http://localhost:8000
```

Dentro da pasta onde esta o `compose.yml`, baixe a imagem publicada no Docker Hub:

```powershell
docker compose pull
```

Esse comando baixa a imagem:

```text
linkado36778/sb-backend:latest
```

Suba apenas o banco:

```powershell
docker compose up -d db
```

Copie o dump SQL para dentro do container do Postgres:

```powershell
docker cp smart-balance.sql sb-postgres:/tmp/smart-balance.sql
```

Restaure os dados:

```powershell
docker exec -it sb-postgres psql -U postgres -d Smart-Balance -f /tmp/smart-balance.sql
```

Suba a API:

```powershell
docker compose up -d
```

Teste:

```powershell
curl http://localhost:8000/health
```

Resumo do fluxo:

```powershell
docker compose pull
docker compose up -d db
docker cp smart-balance.sql sb-postgres:/tmp/smart-balance.sql
docker exec -it sb-postgres psql -U postgres -d Smart-Balance -f /tmp/smart-balance.sql
docker compose up -d
curl http://localhost:8000/health
```

## Backup do Banco

O banco do Compose fica em um volume Docker chamado:

```text
app_sb-postgres-data
```

Para transportar os dados para outra maquina, use dump SQL em vez de copiar o volume diretamente.

### Backup do PostgreSQL do Docker Compose

Use este comando quando os dados ja estiverem no banco `sb-postgres` do Docker Compose:

```powershell
.\scripts\backup-db.ps1
```

Linux/Mac:

```bash
sh scripts/backup-db.sh
```

O arquivo gerado sera:

```text
backups/smart-balance.sql
```

### Backup de um PostgreSQL Local Instalado na Maquina

Use este comando quando os dados ainda estiverem em um PostgreSQL instalado localmente no Windows, fora do Docker:

```powershell
.\scripts\backup-local-postgres.ps1
```

Esse script usa a imagem `postgres:18-alpine` apenas como cliente para executar `pg_dump`, entao nao e necessario instalar `pg_dump` no Windows.

Ele vai pedir a senha do usuario `postgres`.

## Restaurando o Banco em Outra Maquina

Coloque o arquivo:

```text
backups/smart-balance.sql
```

na pasta do projeto da outra maquina.

Depois rode:

```powershell
docker compose up -d db
.\scripts\restore-db.ps1
docker compose up -d
```

Linux/Mac:

```bash
docker compose up -d db
sh scripts/restore-db.sh
docker compose up -d
```

Por fim, teste:

```powershell
curl http://localhost:8000/health
```

## Desenvolvimento Local sem Docker

Opcionalmente, a API tambem pode ser rodada diretamente com Python.

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Configure no `.env` uma URL completa do banco:

```env
SQLALCHEMY_DATABASE_URL=postgresql://postgres:senha@localhost:5432/Smart-Balance
BASE_URL=http://localhost:8000
```

Rode a API:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Observacoes Importantes

- Nao publique o arquivo `.env` no Git.
- Troque `POSTGRES_PASSWORD=change-this-password` antes de usar em ambiente real.
- Se voce mudar `POSTGRES_PASSWORD` depois que o volume Docker ja foi criado, a senha do banco existente nao muda automaticamente.
- Para recriar o banco do zero, remova o volume Docker correspondente. Isso apaga os dados.
- Use `/health` para testar API e banco juntos.
