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
|-- SiglIp/
|-- compose.yml
|-- compose.dev.yml
|-- Dockerfile
|-- main.py
|-- run_local.sh
|-- requirements.txt
|-- smart-balance.sql
`-- .env.example
```

## Variaveis de Ambiente

Crie um arquivo `.env` na raiz do projeto, ao lado do `compose.yml`.

Exemplo:

```env
POSTGRES_DB=Smart-Balance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-this-password
POSTGRES_HOST=db
POSTGRES_PORT=5432
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

Ele roda automaticamente quando houver push na branch `untested` ou em tags no formato `v*.*.*`.

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
POSTGRES_HOST=db
POSTGRES_PORT=5432
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

## Ambiente de Desenvolvimento Local (Linux)

Esta secao descreve como rodar a API diretamente na maquina (sem o container da API),
com o PostgreSQL isolado em Docker. Comandos testados em Linux (bash).

### 1. Versao do Python

- Python **3.13** (mesma versao usada no `Dockerfile`, `python:3.13-slim`).
- Python 3.14 tambem funciona, porem os wheels das bibliotecas podem nao estar disponiveis.

```bash
python3 --version
# ou instale com uv:
uv python install 3.13
```

### 2. Ambiente virtual

Na raiz do projeto:

```bash
# com uv (recomendado - rapido e resolve torch CPU automaticamente)
uv venv --python 3.13 .venv

# ou com venv padrao
python3.13 -m venv .venv
```

### 3. Instalacao das dependencias

```bash
# com uv: instala o PyTorch somente-CPU (sem CUDA, ~10x menor)
UV_TORCH_BACKEND=cpu uv pip install --python .venv/bin/python -r requirements.txt

# ou com pip
.venv/bin/pip install -r requirements.txt
```

Observacoes sobre as dependencias:

- `psycopg2-binary` e usado no lugar de `psycopg2` (mesmo modulo `psycopg2` para o
  SQLAlchemy), para nao exigir `libpq-dev`/`pg_config` na maquina de desenvolvimento.
- O `torch` instalado e o build `+cpu`: `torch.cuda.is_available()` retorna `False`
  e a inferencia roda em CPU. Nao e necessario ter GPU ou CUDA.
- `UV_TORCH_BACKEND=cpu` tambem afeta `torchvision`/`torchaudio`, mantendo o conjunto coerente.

### 4. Arquivo `.env`

```bash
cp .env.example .env
```

Ajuste pelo menos `POSTGRES_PASSWORD`. Exemplo de `.env` local:

```env
APP_ENV=development
POSTGRES_DB=Smart-Balance
POSTGRES_USER=postgres
POSTGRES_PASSWORD=sua-senha-local
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
BASE_URL=http://localhost:8000
SIGLIP_MODEL_NAME=google/siglip-base-patch16-224
HF_HOME=/home/<usuario>/.cache/huggingface
TORCH_NUM_THREADS=4
```

Atencao: o `shared/database.py` monta a URL de conexao a partir das variaveis
`POSTGRES_*` (uma `SQLALCHEMY_DATABASE_URL` no `.env` e ignorada).

Para a balanca/firmware na rede local, aponte `BASE_URL` para o IP da maquina
(ex.: `http://192.168.0.13:8000`).

### 5. PostgreSQL local (Docker)

O `compose.dev.yml` sobe somente o banco, com volume e credenciais proprias,
isolado do banco de producao:

```bash
docker compose -f compose.dev.yml up -d
```

Restaure o dump (estrutura + catalogo de alimentos/nutrientes):

```bash
docker exec -i sb-postgres-dev psql -U postgres -d Smart-Balance < smart-balance.sql
```

Verifique:

```bash
docker exec -i sb-postgres-dev psql -U postgres -d Smart-Balance \
  -c 'SELECT count(*) FROM "Food";'
```

Para derrubar o banco (mantendo os dados):

```bash
docker compose -f compose.dev.yml down
```

Para recriar do zero (apaga os dados do banco LOCAL):

```bash
docker compose -f compose.dev.yml down -v
```

### 6. Modelo de reconhecimento de alimentos (SigLIP)

Nao existe um "SigLIP Runtime" como biblioteca separada, nem modelos ONNX neste
projeto. A inferencia usa o modelo **SigLIP** `google/siglip-base-patch16-224`
via **HuggingFace Transformers**, com **dependencia de PyTorch em runtime**
(`SiglIp/test_01_Siglip.py`):

- `transformers.AutoProcessor` / `transformers.AutoModel` carregam o modelo;
- `torch` executa a inferencia (pre-processamento via PIL/processor, pos-processamento
  com `softmax` + `topk` sobre os 25 rotulos definidos no proprio modulo);
- o PyTorch instalado e o build `+cpu`: `torch.cuda.is_available()` retorna `False`
  e a inferencia roda em **CPU**, sem exigir CUDA ou GPU.

- Os pesos (~780 MB) sao baixados automaticamente do HuggingFace Hub na primeira
  requisicao de reconhecimento e ficam no cache: `$HF_HOME/hub/models--google--siglip-base-patch16-224`.
- Para usar uma copia local, baixe o modelo e aponte `SIGLIP_MODEL_NAME` para a
  pasta absoluta (ou para o identificador do Hub).
- Download manual (opcional):

```bash
.venv/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('google/siglip-base-patch16-224'))"
```

- `TORCH_NUM_THREADS` controla as threads de inferencia (opcional).

### 7. Iniciando a FastAPI

```bash
./run_local.sh
```

O script exporta as variaveis do `.env`, avisa se o banco estiver fora do ar e roda:

```bash
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Para encerrar: `Ctrl+C` (e `docker compose -f compose.dev.yml down` para o banco).

Para deixar a API rodando em background (sobrevive ao fechamento do terminal):

```bash
set -a; . ./.env; set +a
setsid nohup .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
  > /tmp/sb_api.log 2>&1 < /dev/null &
# encerrar: pkill -f "uvicorn main:app"
```

### 8. Enderecos

- API: `http://localhost:8000` (rede local: `http://<IP-da-maquina>:8000`)
- Swagger (Scalar): `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/health`

### 9. Testando os endpoints

```bash
# usuarios
curl http://localhost:8000/users/get_User/2

# alimentos (catalogo + nutrientes)
curl "http://localhost:8000/foods?user_id=2"

# reconhecimento de alimentos (primeira imagem)
curl -X POST "http://localhost:8000/food-recognition/image?user_id=2" \
  -F "file=@images/alimentos/arroz-tipo-1-cozido.jpg;type=image/jpeg"

# reconhecimento com peso (nutrientes ajustados)
curl -X POST "http://localhost:8000/food-recognition/image/weight?user_id=2&weight=150" \
  -F "file=@images/alimentos/feijao-preto-cozido.jpg;type=image/jpeg"

# refeicao
curl -X POST http://localhost:8000/meals \
  -H "Content-Type: application/json" \
  -d '{"name":"Almoco","user_id":2,"consumed_at":"2026-11-20T12:30:00","calories":0,"weight_g":350,"list_foods_ids":[1,2],"saved_meal":true}'
```

As imagens em `images/alimentos/` sao os arquivos de teste reais do projeto
(25 alimentos, correspondentes aos rotulos do modelo).

Atencao ao contrato de `consumed_at` em `POST /meals`: use data-hora ISO 8601
(ex.: `2026-11-20T12:30:00`). O validador `"%H:%M"` existente no codigo nao e
aplicado pelo Pydantic (validacao de tipo acontece antes).

O fluxo de reconhecimento guarda a ultima imagem de cada usuario em memoria:
a primeira chamada classifica a imagem inteira (`"first_image": true`) e as
seguintes comparam com a anterior e classificam apenas a regiao alterada
(`"changed": true`, com `bbox`). Para reiniciar o fluxo, basta reiniciar a API.

Nao existe suite de testes automatizados no repositorio. Os arquivos em
`test/rand/` sao scripts diagnosticos antigos (com credenciais fixas) e nao
devem ser considerados validacao. A validacao real e feita pelos comandos
acima, contra a API rodando e com imagens reais de `images/alimentos/`.

Para evitar o aviso de rate limit do HuggingFace no primeiro download do
modelo, exporte um token (opcional): `export HF_TOKEN=<seu-token>`.

### 10. Compatibilidade com o firmware (rede local)

- Os endpoints sao HTTP direto (JSON + `multipart/form-data`); o firmware em C/C++
  nao precisa de CORS.
- Nao ha middleware de CORS configurado na API. Ele so seria necessario para
  clientes web (browser) consumirem a API de outra origem.
- Para o firmware acessar a API, use `http://<IP-da-maquina>:8000` em `BASE_URL`
  e verifique se a porta 8000 esta liberada no firewall local.

## Observacoes Importantes

- Nao publique o arquivo `.env` no Git.
- Troque `POSTGRES_PASSWORD=change-this-password` antes de usar em ambiente real.
- Se voce mudar `POSTGRES_PASSWORD` depois que o volume Docker ja foi criado, a senha do banco existente nao muda automaticamente.
- Para recriar o banco do zero, remova o volume Docker correspondente. Isso apaga os dados.
- Use `/health` para testar API e banco juntos.
