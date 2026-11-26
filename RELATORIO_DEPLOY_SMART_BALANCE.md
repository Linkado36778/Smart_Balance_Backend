# Relatório de Deploy — Smart Balance Backend (FastAPI)

Data do deploy: 2026-11-21 (UTC)
Escopo: somente o backend Python/FastAPI deste repositório. Nenhum projeto mobile (KMP/Android/iOS) foi tocado ou publicado.

**API pública:** https://balanca-backend.andreaswilliamporcel.com.br
**Documentação (Scalar):** https://balanca-backend.andreaswilliamporcel.com.br/docs
**Release em produção:** `d59886e-20261121190547` (commit `d59886e`)

---

## 1. Infraestrutura

| Item | Valor |
|---|---|
| Provedor / plano | Hostinger VPS KVM 2 (`srv2185504.hstgr.cloud`) |
| IP | 179.66.157.98 |
| Sistema | Debian GNU/Linux 13 (trixie), kernel 6.12, x86_64 |
| CPU | 2 vCPU AMD EPYC 9354P |
| RAM | 7,8 GiB (sem swap) |
| Disco | 99 GB (≈ 7 % usado após o deploy) |
| Docker / Compose | Docker 29.10.0 / Compose v5.8.0 (já instalados) |
| Pacotes instalados | `nginx` 1.26.3, `certbot` 4.0.0 + `python3-certbot-nginx`, `rsync` |

**Estado encontrado antes do deploy:** VPS recém-criada (2026-11-21 18:37 UTC), sem containers, volumes, Nginx, certificados ou bancos. Não havia firewall no sistema (sem ufw/nftables próprios; grupo de firewall da Hostinger não atribuído). Nenhum serviço pré-existente foi alterado.

**Portas (após o deploy)**

| Porta | Escuta em | Uso | Externa |
|---|---|---|---|
| 22 | 0.0.0.0 | SSH (configuração não alterada) | aberta |
| 80 | 0.0.0.0 | Nginx → redireciona para HTTPS | aberta |
| 443 | 0.0.0.0 | Nginx TLS → API | aberta |
| 8000 | 127.0.0.1 | Uvicorn (container `sb-backend`) | **fechada** |
| 5432 | rede interna Docker | PostgreSQL (container `sb-postgres`) | **fechada** |

---

## 2. Aplicação

| Item | Valor |
|---|---|
| Diretório | `/opt/smart-balance` |
| Releases | `/opt/smart-balance/releases/<commit>-<timestamp>` (cada versão em sua pasta) |
| Estado de versões | `/opt/smart-balance/state/{current_tag,previous_tag,history}` |
| Variáveis | `/opt/smart-balance/.env` (root, `chmod 600`, não versionado) |
| Python | 3.13 (imagem `python:3.13-slim`) |
| Imagem | `sb-backend:<release>` (≈ 2,1 GB; build local na VPS) |
| Módulo | `main:app` |
| Routers | auth, user, food, vision recognition, food recognition (41 rotas no OpenAPI) |

**Comando de inicialização (container):**

```
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips *
```

- 1 worker de propósito: o reconhecimento guarda a "imagem anterior" de cada usuário na memória do processo, e cada processo carrega o SigLIP.
- O TLS termina no Nginx; o Uvicorn não recebe `--ssl-keyfile/--ssl-certfile`, o que evita TLS duplicado.
- A porta 8000 só aceita conexões de `127.0.0.1` (publicada como `127.0.0.1:8000:8000`).

**Arquivos de deploy (versionáveis, sem segredos), em `deploy/`:**

| Arquivo | Função |
|---|---|
| `deploy/Dockerfile` | Imagem de produção: PyTorch **CPU** (mesmas versões do `requirements.txt`), copia só o código necessário e roda com usuário não root |
| `deploy/compose.prod.yml` | API + PostgreSQL, volumes, health check, `restart: unless-stopped`, logs com rotação, limite de 4 GB de RAM na API |
| `deploy/nginx/smart-balance.conf` | Site Nginx (proxy, `client_max_body_size 20m`, timeout de 180 s) |
| `deploy/push_release.sh` | Envia um release (rsync só dos arquivos necessários) e dispara o deploy |
| `deploy/deploy.sh` | Build com tag, sobe a API e espera o `/health`; se falhar, faz **rollback automático** |
| `deploy/rollback.sh` | Volta para a tag anterior ou para uma tag específica |

O `Dockerfile` e o `compose.yml` da raiz, usados pelo CI do Docker Hub, **não foram alterados**.

**Arquivos enviados ao servidor:** `main.py`, `requirements.txt`, `application/`, `shared/`, `SiglIp/test_01_Siglip.py`, `images/` e `deploy/*`. Não foram enviados: testes, datasets e análises do SigLIP, `.venv`, `.env` local e documentação.

**Variáveis em `/opt/smart-balance/.env`** (valores sensíveis omitidos): `APP_ENV=production`, `POSTGRES_DB=Smart-Balance`, `POSTGRES_USER=smartbalance`, `POSTGRES_PASSWORD=<gerada aleatoriamente no servidor, 40 caracteres>`, `POSTGRES_HOST=db`, `POSTGRES_PORT=5432`, `BASE_URL=https://balanca-backend.andreaswilliamporcel.com.br`, `SIGLIP_MODEL_NAME=google/siglip-base-patch16-224`, `HF_HOME=/models/hf`, `TORCH_NUM_THREADS=2`.

---

## 3. Banco de dados

| Item | Valor |
|---|---|
| Motor | PostgreSQL 18 (`postgres:18-alpine`), container `sb-postgres` |
| Banco | `Smart-Balance` |
| Usuário | `smartbalance` (senha só no `.env` do servidor) |
| Host / porta (vistos pela API) | `db:5432`, na rede interna `smart-balance_default` |
| Exposição | nenhuma porta publicada no host |
| Persistência | volume Docker `smart-balance_sb-postgres-18-data` → `/var/lib/postgresql` |
| Pool | padrão do SQLAlchemy (`pool_size=5`, `max_overflow=10`); configuração do código mantida |

**Carga inicial:** a VPS não tinha nenhum banco Smart-Balance. Por escolha do responsável, o banco foi populado com `smart-balance.sql` (dump versionado). A restauração rodou numa única transação (`psql -1 -v ON_ERROR_STOP=1`), sem as linhas `OWNER TO postgres`, porque o usuário de produção é outro.

1. A primeira tentativa foi revertida inteira: o dump não conhece as tabelas `User_Balance` e `CreatedFood`, que o startup já tinha criado com chaves estrangeiras para `User`.
2. Como o banco tinha só tabelas e seeds criados minutos antes (0 usuários, 0 alimentos, 0 refeições), foi feito `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` seguido do dump, **na mesma transação**. Um backup do estado anterior ficou em `/root/backups/pre-restore-*.sql`.
3. No boot seguinte, o startup (`initialize_database`) recriou as tabelas novas e adicionou as colunas que faltavam. Todas as migrations do código são aditivas (`ADD COLUMN IF NOT EXISTS` e `create_all`); nenhuma migration destrutiva foi executada.

**Verificação do schema:** 20 tabelas. As colunas `Meal_Food.food_weight_g`, `Pairing.balance_id`, `Pairing.user_id`, `Pairing.poll_token_hash` e `Nutrient.calories_per_unit` estão presentes.
**Dados restaurados:** 25 alimentos, 2 usuários, 225 relações alimento-nutriente, 7 categorias e 18 nutrientes. Os nomes repetidos nos ids 10 a 18 vêm do próprio `smart-balance.sql`, não de duplicação pelos seeds.

**Testes de banco:** `/health` retorna `database: available`; as consultas de alimentos, categorias e nutrientes respondem; as gravações (usuário, balança, pareamento, refeição) passaram. Contagens antes e depois do restart da stack ficaram idênticas.

---

## 4. SigLIP

| Item | Valor |
|---|---|
| Modelo | `google/siglip-base-patch16-224` (HuggingFace Transformers 5.15 + PyTorch 2.13.0+cpu) |
| Mecanismo | inalterado: mesmos labels, softmax/top-k e mapeamento para o banco; nenhum ONNX |
| Pesos | volume `smart-balance_sb-hf-cache` montado em `/models/hf` (`HF_HOME`), 779 MB |
| Carregamento | sob demanda, na 1ª requisição de reconhecimento (comportamento do código mantido) |
| Pré-processamento | OpenCV headless 4.13 (detecção de região alterada) e Pillow |
| Threads | `TORCH_NUM_THREADS=2` (uma por vCPU) |

O modelo foi baixado do HuggingFace Hub na primeira chamada e fica persistido no volume. Rebuilds e rollbacks da imagem **não** apagam os pesos.

**Teste de reconhecimento real (via HTTPS público):**

| Chamada | Resultado | Tempo |
|---|---|---|
| `POST /food-recognition/image/weight` (arroz, 150 g), 1ª chamada com download do modelo | top-1 **"Arroz tipo 1, cozido"**, com nutrientes calculados para 150 g | 24,0 s |
| `POST /food-recognition/image` (banana), 2ª imagem pelo fluxo de região alterada | `changed: true`, top-1 **"Banana prata, crua"** (confiança 0,9998) | 2,1 s |
| `POST /food-recognition/image/weight` (ovo frito) após restart, modelo vindo do volume | 200 | 3,3 s |
| `POST /food-recognition/image` com usuário inexistente | 404 | 0,2 s |

**Consumo observado:** API ≈ 0,3 a 1 GiB de RAM (limite de 4 GiB no compose; ≈ 1,04 GiB medido no teste local equivalente), PostgreSQL ≈ 28 MiB. A RAM total usada na VPS ficou em ≈ 1 GiB de 7,8 GiB. A inferência com o modelo já carregado leva ≈ 1,5 a 2 s em CPU.

---

## 5. HTTPS

| Item | Valor |
|---|---|
| Domínio | `balanca-backend.andreaswilliamporcel.com.br` |
| DNS | Cloudflare (proxy ativo), registro A → 179.66.157.98 (alterado pelo responsável) |
| Certificado de origem | Let's Encrypt (emissor YE2), válido de 2026-11-21 a **2027-02-19** |
| Emissão | `certbot --nginx` (HTTP-01), conta registrada **sem e-mail** (nenhum dado pessoal enviado ao Let's Encrypt) |
| Renovação | automática pelo `certbot.timer` (systemd, habilitado) |
| Proxy reverso | Nginx: `/etc/nginx/sites-available/smart-balance.conf` (link em `sites-enabled`) |
| Redirecionamento | HTTP → HTTPS (301), inserido pelo certbot |

O `nginx.conf` global e o site `default` não foram alterados. O backup dos diretórios de sites ficou em `/root/backups/nginx-*`.

**Validação:**
- Pela Cloudflare: `GET https://…/health` retorna 200 `{"status":"healthy","database":"available"}`.
- Direto na origem (`--resolve` para 179.66.157.98): o certificado é válido (`ssl_verify_result=0`) e HTTP:80 redireciona para HTTPS.
- `certbot renew --dry-run`: todas as renovações simuladas tiveram sucesso.
- Recomendado na Cloudflare: SSL/TLS em **Full (strict)**, já possível porque a origem tem certificado válido.

---

## 6. Operação

Todos os comandos abaixo rodam no servidor (`ssh -i ~/.ssh/id_buildroot root@179.66.157.98`), dentro de `/opt/smart-balance`:

```bash
cd /opt/smart-balance
export IMAGE_TAG=$(cat state/current_tag)
DC="docker compose -f compose.prod.yml --env-file .env"
```

| Ação | Comando |
|---|---|
| Status | `$DC ps` ou `docker ps` |
| Health | `curl -s http://127.0.0.1:8000/health` |
| Logs da API | `docker logs -f --tail 200 sb-backend` |
| Logs do banco | `docker logs --tail 100 sb-postgres` |
| Logs do Nginx | `tail -f /var/log/nginx/access.log /var/log/nginx/error.log` |
| Reiniciar a API | `$DC restart api` |
| Reiniciar a stack | `$DC restart` |
| Verificar o PostgreSQL | `docker exec sb-postgres sh -c 'pg_isready -U $POSTGRES_USER -d $POSTGRES_DB'` |
| Consultar o banco | `docker exec -it sb-postgres sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB'` |
| Verificar o SigLIP | `docker exec sb-backend du -sh /models/hf` e `docker logs sb-backend \| grep "Using device"` (aparece no 1º reconhecimento) |
| Recursos | `docker stats --no-stream` |
| Versões disponíveis | `docker images sb-backend` e `cat state/history` |
| Certificado | `certbot certificates` / `certbot renew --dry-run` |

Os logs ficam no driver `json-file` do Docker (20 MB × 5 arquivos por container) e podem ser consultados com `docker logs`.

**Inicialização automática:** `docker`, `containerd` e `nginx` estão habilitados no systemd, e os containers usam `restart: unless-stopped`. A aplicação independe da sessão SSH.

### Atualizar (nova versão)

Na máquina local, na raiz do repositório, com o código commitado:

```bash
deploy/push_release.sh                # usa ~/.ssh/id_buildroot; SB_SSH_KEY= para usar o ssh padrão
```

O script faz o seguinte:
1. Envia os arquivos para `/opt/smart-balance/releases/<commit>-<timestamp>`.
2. Constrói `sb-backend:<release>`; a imagem anterior permanece.
3. Recria **somente** o serviço `api`; banco e volumes não são tocados.
4. Espera o `/health`. Se falhar, volta sozinho para a tag anterior.

**Validar uma atualização:** `curl -s https://balanca-backend.andreaswilliamporcel.com.br/health`, depois um reconhecimento e `docker logs --tail 100 sb-backend`.

### Reconstruir a imagem de um release já enviado

```bash
bash /opt/smart-balance/releases/<release>/deploy/deploy.sh <release>
```

### Rollback

```bash
/opt/smart-balance/rollback.sh              # volta para a tag anterior
/opt/smart-balance/rollback.sh <release>    # volta para um release específico (ver docker images sb-backend)
```

O rollback troca só a imagem da API. Os dados do PostgreSQL (`sb-postgres-18-data`), os pesos do SigLIP (`sb-hf-cache`) e as imagens enviadas (`sb-static-images`) ficam em volumes nomeados e são preservados. Nunca use `docker compose down -v` nem `docker volume rm` nesses volumes.

**Backup do banco:**

```bash
docker exec sb-postgres sh -c 'pg_dump -U $POSTGRES_USER -d $POSTGRES_DB' > /root/backups/smart-balance-$(date -u +%Y%m%d%H%M%S).sql
```

---

## 7. Resultado final

**Status: deploy concluído e validado com requisições reais pelo HTTPS público.**

### Endpoints testados (https://balanca-backend.andreaswilliamporcel.com.br)

| Grupo | Endpoint | Esperado | Resultado |
|---|---|---|---|
| Sistema | `GET /`, `GET /health`, `GET /docs`, `GET /openapi.json` (41 rotas) | 200 | OK |
| Usuários | `POST /user`, `GET /user/{id}`, `GET /login_User/{email}/{senha}` | 200 | OK |
| Autenticação | `POST /auth/commun_user` (senha correta / errada) | 200 / 401 | OK |
| Alimentos | `GET /foods?user_id`, `GET /foods?name=Arroz`, `GET /nutrients/{food_id}` | 200 | OK |
| Alimentos do usuário | `POST /foods`, `GET /foods/{id}?user_id` | 200 | OK |
| Referência | `GET /categories` (7), `GET /nutrients`, `GET /list_allergens` | 200 | OK |
| Arquivos estáticos | `GET /images/alimentos/arroz-tipo-1-cozido.jpg` | 200 image/* | OK |
| Balanças | `POST /register_balance` | 200 | OK |
| Pareamento | `POST /generate_qr_code/?balance_id`, `GET /qr_codes/pairing_*.png` | 200 / image/png | OK |
| Pareamento | `GET /pairing/{id}/status` (pending → paired; sem token → 401) | 200 / 401 | OK |
| Pareamento | `POST /pair-scale` (1º uso / reuso do token) | 200 / 400 | OK |
| SigLIP | `POST /food-recognition/image/weight`, `POST /food-recognition/image` | 200 (alimento correto) | OK |
| SigLIP | usuário inexistente | 404 | OK |
| Refeições | `POST /meals`, `GET /meals`, `DELETE /meals/{id}/{user}` | 200 | OK |
| HTTPS | Cloudflare e origem direta, redirecionamento 80 → 443 | válido | OK |
| Persistência | restart da stack: contagens iguais, modelo mantido no volume | — | OK |

### Critérios de aceite

- [x] Somente o backend Smart Balance foi publicado.
- [x] Nenhum projeto mobile foi modificado ou publicado.
- [x] FastAPI inicializa corretamente (5 routers, 41 rotas).
- [x] PostgreSQL funcional e persistente (volume nomeado, sem porta pública).
- [x] SigLIP carrega e reconhece corretamente (arroz e banana).
- [x] Endpoints principais respondem corretamente.
- [x] HTTPS funciona (Let's Encrypt atrás da Cloudflare).
- [x] Logs acessíveis (`docker logs`, logs do Nginx).
- [x] Inicialização automática configurada (systemd + `restart: unless-stopped`).
- [x] Dados persistentes preservados após restart.
- [x] Serviços preexistentes da VPS continuam funcionando (não havia outros; SSH intacto).
- [x] Procedimento de atualização e rollback documentado e automatizado.
- [x] Relatório final criado.

### Problemas encontrados

1. **Acesso SSH:** inicialmente a VPS só aceitava senha. O responsável instalou a chave `~/.ssh/id_buildroot` com `ssh-copy-id`. Nenhuma outra configuração SSH foi alterada.
2. **Build lento:** o CDN do PyPI baixa a ≈ 0,4 a 0,7 MB/s a partir desse datacenter, e o primeiro build levou ≈ 25 min. Os próximos builds reaproveitam o cache de camadas enquanto o `requirements.txt` não mudar.
3. **Dump incompatível com o schema atual:** `smart-balance.sql` não tem `User_Balance` nem `CreatedFood`. Foi resolvido com o reset do schema recém-criado e a restauração atômica (seção 3).
4. **Comportamentos do código observados (não alterados):**
   - `GET /foods/{id}` devolve só alimentos criados pelo usuário (`CreatedFood`). Um id de alimento base retorna 404 "Created food not found".
   - `POST /foods` responde `data: null`, sem o id criado.
   - O estado "imagem anterior" do reconhecimento fica em memória. Depois de um restart, a próxima foto de cada usuário é tratada como "primeira imagem".
   - Os QR codes são temporários e apagados no shutdown da API.

### Pendências e recomendações

- **Registros de teste em produção:**
  - usuários `deploy-smoke-*@example.invalid` (ids 4 e 5);
  - balança `deploy-smoke-1795289165` (id 3);
  - pareamento 13 e o vínculo `User_Balance (5,3)`;
  - `CreatedFood` id 1 ("deploy smoke food").

  A remoção automática foi bloqueada pela política de permissões da sessão. Remova quando quiser, por exemplo `DELETE /foods/1?user_id=5` seguido de `DELETE /delete_User/4` e `DELETE /delete_User/5`, e apague a balança 3 pelo banco.
- **Instância antiga:** antes da virada do DNS, o domínio era servido por outra origem, também uma Smart Balance API com banco próprio. Os dados dela **não** foram migrados (decisão: usar `smart-balance.sql`). Avalie desligá-la ou fazer backup dela.
- **Cloudflare:** confirme SSL/TLS em *Full (strict)*.
- **Pastas vazias:** `/opt/smart-balance/releases/d59886e-20261121185758` e `…185923` vieram das tentativas de envio anteriores ao rsync existir no servidor. Estão vazias e podem ser removidas.
- **Opcional:** definir `HF_TOKEN` no `.env` (remove o aviso de requisições anônimas ao HuggingFace) ou `HF_HUB_OFFLINE=1`, já que o modelo está em cache. Também é opcional ativar o firewall da Hostinger liberando só 22, 80 e 443.
- **Observações de segurança do código (fora do escopo do deploy):** `GET /login_User/{email}/{senha}` e `GET /login_Nutricionist/...` enviam a senha na URL, o que a deixa nos logs de acesso. As rotas não exigem token de sessão. O mecanismo atual foi preservado, como pedido.
- **Reboot completo da VPS:** não executado, por causar indisponibilidade. A inicialização automática está configurada (serviços habilitados + `restart: unless-stopped`). Para validar, rode `reboot` e depois `curl https://balanca-backend.andreaswilliamporcel.com.br/health`.
