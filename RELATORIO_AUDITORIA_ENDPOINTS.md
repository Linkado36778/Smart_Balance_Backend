# Relatório de Auditoria Funcional dos Endpoints — Smart Balance Backend

- **Data:** 2026-11-20
- **Branch:** `Andreas` (base `32dacc9`)
- **Escopo:** todas as rotas registradas na aplicação FastAPI (`main.py` + 5 routers)
- **Método:** leitura integral do código → suíte automatizada (pytest + `TestClient`) contra PostgreSQL real em banco isolado → linha de base **sem correções** → correção dos defeitos → nova execução completa → medição de desempenho com servidor uvicorn real.

---

## A. Resumo executivo

| Indicador | Valor |
|---|---|
| Rotas registradas | **51** (47 endpoints de API + `/docs` + `/openapi.json` + 2 montagens estáticas `/images`, `/qr_codes`) |
| Rotas testadas | **51** |
| Aprovadas | **41** |
| Aprovadas com ressalvas (funcionam, mas há problema documentado e **não corrigido**) | **10** |
| Reprovadas (após correções) | **0** |
| Bloqueadas por ambiente | **0** (ver ressalva das 3 rotas de dieta no banco dev, item N03) |
| Rotas reprovadas na linha de base (antes das correções) | **26** |
| Problemas corrigidos | **16** (2 críticos, 4 altos, 9 médios, 1 baixo) |
| Problemas documentados e não corrigidos | **14** (2 críticos, 1 alto, 3 médios, 7 baixos, 1 informativo) |
| Testes automatizados | **126** — linha de base: 37 falhas / 89 aprovados; final: **126 aprovados, 0 falhas** |

**Resultado geral:** os defeitos funcionais encontrados foram corrigidos e cobertos por testes. Todos os endpoints passam na validação funcional, incluindo persistência e pipeline SigLIP real. **Mas a API não está pronta para ficar exposta fora de uma rede confiável.** Nenhum endpoint tem autenticação ou autorização real (N01), e o login por `GET` envia a senha na URL (N02). Esses dois itens críticos dependem de uma decisão de arquitetura e de mudança de contrato com o app e o firmware, então ficaram fora das correções.

### Ambiente da auditoria

- Linux (Nobara, kernel 7.3.1), CPU Intel i5-12600K (16 threads lógicas), 31 GB RAM; sem GPU (`device=cpu`, 4 threads PyTorch).
- Python 3.13.15, FastAPI 0.116.1, SQLAlchemy 2.0.42, torch 2.13.0+cpu, transformers 5.15.0.
- PostgreSQL 18.7 no container `sb-postgres-dev` (`compose.dev.yml`).
- Modelo `google/siglip-base-patch16-224` do cache local do HuggingFace (offline).

### Isolamento e segurança dos dados

- Todos os testes rodaram no banco **`Smart-Balance-test`**, criado no mesmo servidor de desenvolvimento. A suíte recusa rodar se o nome do banco não terminar em `test`.
- A cada execução, o schema é recriado a partir dos modelos SQLAlchemy. O banco recebe só os **dados de referência** do `smart-balance.sql`: 25 alimentos, nutrientes, alérgenos, categorias e associações. **Nenhum usuário real** é importado; usuários, nutricionistas, balanças e refeições são criados com dados fictícios (`*@example.test`).
- O banco de desenvolvimento `Smart-Balance` foi acessado **apenas para leitura** (inspeção de schema e contagens). Contagens antes e depois da auditoria: 7 usuários, 25 alimentos, 4 refeições, sem alteração.
- Os arquivos gravados pela API (uploads, temporários do reconhecimento, `output/`) vão para um diretório temporário. Os de QR code vão para `qr_codes/` do projeto, que já está no `.gitignore` e é apagado no shutdown.
- Nenhuma configuração de produção (`compose.yml`, `Dockerfile`, workflow de deploy, `.env`) foi alterada.

---

## B. Inventário completo

Legenda de status: **Aprovado** = cenários positivos e negativos aplicáveis validados, incluindo persistência. **Aprovado c/ ressalvas** = validado funcionalmente, mas com problema documentado e não corrigido (código em Observações). "Corrigido Pxx" indica que o endpoint estava **reprovado na linha de base** e foi corrigido.

Nenhuma rota exige autenticação (N01). "Autorização" nas rotas de `/foods` e `/meals` significa só comparar com o `user_id` enviado pelo próprio cliente.

### Sistema / auxiliares (`main.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| GET | `/` | Mensagem "API running" | Aprovado | Lista de rotas desatualizada (N10) |
| GET | `/health` | Health check com `SELECT 1` | Aprovado | 503 com banco indisponível testado; não vaza a senha |
| GET | `/docs` | Referência Scalar | Aprovado | `base_server_url` fixo em `https://api.meusite.com` (N10) |
| GET | `/openapi.json` | Schema OpenAPI | Aprovado | Todas as 47 rotas presentes |
| GET | `/images/{path}` | Arquivos estáticos dos alimentos | Aprovado | Os 25 `image_url` do catálogo existem e são servidos |
| GET | `/qr_codes/{path}` | PNGs de pareamento | Aprovado | PNG válido servido após `generate_qr_code` |

### Autenticação (`auth_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| POST | `/auth/commun_user` | Valida credenciais de usuário | Aprovado | Corrigido P07 (retornava 400 em vez de 401). Não emite token (N01) |
| POST | `/auth/nutricionist` | Valida credenciais de nutricionista | Aprovado | Corrigido P07 |

### Usuários e nutricionistas (`user_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| POST | `/user` | Cria usuário (senha argon2) | Aprovado | Corrigido P09 (`nutricionist_id` inexistente gerava 500, agora 409) |
| GET | `/user/{user_id}` | Busca usuário | Aprovado | Corrigido P03 (o parâmetro de rota era ignorado) |
| PATCH | `/update_User/{user_id}` | Atualiza usuário | Aprovado | Corrigido P12 (sem validação de e-mail/duplicidade) |
| DELETE | `/delete_User/{user_id}` | Exclusão física | Aprovado | Corrigido P09 (usuário com refeições gerava 500, agora 409) |
| GET | `/login_User/{email}/{password}` | Login legado | Aprovado c/ ressalvas | Corrigido P01 (vazava hash). **Senha na URL (N02)** |
| POST | `/nutricionist` | Cria nutricionista (valida CRN) | Aprovado | — |
| GET | `/get_Nutricionist/{id}` | Busca nutricionista | Aprovado | Corrigido P01 (vazava hash) |
| PATCH | `/update_Nutricionist/{id}` | Atualiza nutricionista | Aprovado | Corrigido P12 (aceitava CRN/e-mail inválidos) |
| DELETE | `/delete_Nutricionist/{id}` | Exclusão física | Aprovado | Corrigido P09 (com usuários vinculados gerava 500, agora 409) |
| GET | `/login_Nutricionist/{email}/{password}` | Login legado | Aprovado c/ ressalvas | Corrigido P01. **Senha na URL (N02)** |
| POST | `/link_user_nutricionist` | Vincula usuário ↔ nutricionista | Aprovado | — |
| PATCH | `/unlink_user_nutricionist/{user_id}` | Desvincula | Aprovado | — |
| GET | `/list_user_data_by_nutricionist/{id}` | Pacientes do nutricionista | Aprovado | Corrigido P01 (vazava hash de todos os pacientes) |

### Alérgenos e dietas (`user_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| POST | `/add_allergen_to_user` | Associa alérgeno ao usuário | Aprovado | Corrigido P09 (inexistente/duplicado gerava 500) |
| GET | `/list_allergens_by_user/{user_id}` | Alérgenos do usuário | Aprovado | — |
| DELETE | `/remove_allergen_from_user` | Remove associação | Aprovado | — |
| POST | `/add_allergen` | Cadastra alérgeno | Aprovado | Corrigido P06 (**retornava 500 sempre**) |
| GET | `/list_allergens` | Lista alérgenos | Aprovado | — |
| POST | `/create_diet/{nutricionist_id}/{user_id}` | Cria dieta + alimentos | Aprovado c/ ressalvas | Corrigido P11. **Schema divergente no banco dev (N03)** |
| GET | `/list_diets_by_user/{user_id}` | Dietas do usuário | Aprovado c/ ressalvas | **N03** |
| PATCH | `/update_diet/{diet_id}` | Atualiza dieta e alimentos | Aprovado c/ ressalvas | **N03** |

### Balança e pareamento (`user_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| POST | `/register_balance` | Cadastra balança | Aprovado | Campo `id` obrigatório e ignorado (N09) |
| POST | `/generate_qr_code/` | Gera token temporário (5 min) + PNG | Aprovado c/ ressalvas | A URL do QR aponta para uma rota só-POST; token não vinculado à balança (N09) |
| POST | `/pair-scale` | Consome token e associa usuário ↔ balança | Aprovado | Corrigido P10 e P09 |

### Alimentos, marcas, categorias, nutrientes (`food_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| GET | `/foods` | Catálogo + nutrientes + `user_allergic` | Aprovado | Corrigido P05 (**flag de alergia sempre falsa**) |
| GET | `/foods/{food_id}` | Alimento criado pelo usuário | Aprovado | Corrigido P04 (`food_id` era ignorado) |
| POST | `/foods` | Cria alimento do usuário | Aprovado | Corrigido P08 |
| PATCH | `/foods/{food_id}` | Atualiza alimento do usuário | Aprovado | Corrigido P08 (403/404 viravam 400) |
| DELETE | `/foods/{food_id}` | Exclusão física + associações | Aprovado | Corrigido P08 |
| GET | `/brands` | Busca marcas por nome parcial | Aprovado | — |
| POST | `/brands` | Cria marca | Aprovado | Corrigido P13 (falso "já existe") |
| PATCH | `/brands/{brand_id}` | Renomeia marca | Aprovado | — |
| DELETE | `/brands/{brand_id}` | Exclui marca | Aprovado | Corrigido P09 (marca em uso gerava 500) |
| GET | `/categories` | Lista categorias | Aprovado | — |
| GET | `/nutrients` | Lista nutrientes | Aprovado c/ ressalvas | Nutrientes duplicados nos dados (N08) |
| GET | `/nutrients/{food_id}` | Micronutrientes do alimento | Aprovado | — |

### Refeições (`food_controller.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| GET | `/meals` | Refeições do usuário com alimentos | Aprovado | 404 quando não há refeições (N11) |
| POST | `/meals` | Calcula calorias e grava | Aprovado c/ ressalvas | Corrigido P14. `saved_meal=false` retorna `null`; calorias ignoram o peso (N06) |
| PATCH | `/meals/{meal_id}/{user_id}` | Atualiza refeição | Aprovado | Corrigido P14, P15, P16 |
| DELETE | `/meals/{meal_id}/{user_id}` | Exclusão física + associações | Aprovado | Corrigido P16 |

### Visão / reconhecimento (`vision_recognition_controller.py`, `food_recognition.py`)

| Método | Endpoint | Funcionalidade | Status | Observações |
|---|---|---|---|---|
| POST | `/upload-image` | Salva imagem de dataset | Aprovado | Corrigido P02 (**path traversal**). Sem limite de tamanho (N07) |
| POST | `/food-recognition/image` | SigLIP: 1ª imagem inteira; depois só a região alterada | Aprovado c/ ressalvas | Bloqueia o event loop (N04); sem limiar de confiança (N05) |
| POST | `/food-recognition/image/weight` | Igual ao anterior + nutrientes ajustados ao peso | Aprovado c/ ressalvas | N04, N05 |

---

## C. Resultados detalhados

Os IDs de teste citados ficam em `tests/`. "Base → Final" = código HTTP recebido antes e depois das correções, quando houve diferença. Em todos os testes de criação, atualização e exclusão, o estado foi conferido por consulta direta ao banco com uma sessão SQLAlchemy separada. Os testes de erro também verificam que **nada foi persistido parcialmente**.

### C.1 Sistema

| Cenário | Requisição | Esperado | Recebido | Validação |
|---|---|---|---|---|
| Raiz | `GET /` | 200 | 200 | `message == "API running"` |
| Health OK | `GET /health` | 200 | 200 | `{"status":"healthy","database":"available"}` |
| Health com banco fora | engine apontando para `127.0.0.1:1` | 503 | 503 | `unhealthy/unavailable`; a senha da URL não aparece em `detail` |
| Endpoint com banco fora | `GET /categories` com sessão quebrada | 500 | 500 | Requisição seguinte volta a 200 (API não trava) |
| Docs | `GET /docs` | 200 HTML | 200 | — |
| OpenAPI | `GET /openapi.json` | 200 | 200 | As 47 rotas de API estão no schema |
| Imagens | `GET /images/alimentos/<cada image_url>` (25) | 200 `image/*` | 200 | Inclui nomes com acento e espaço |
| Inexistente | `/images/...`, `/qr_codes/...` | 404 | 404 | — |

### C.2 Autenticação

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| Credenciais válidas (usuário/nutricionista) | 200 | 200 | `success=true`, `data=null` |
| Senha errada | 401 | **400 → 401** | `message="Credencial inválida"` |
| E-mail inexistente | 401 | **400 → 401** | idem |
| Campo ausente / corpo vazio / JSON malformado | 422 | 422 | — |

### C.3 Usuários

| Cenário | Esperado | Base → Final | Validação / persistência |
|---|---|---|---|
| `POST /user` válido | 200 | 200 | Campos e tipos do `data`; linha no banco; senha com hash argon2 (≠ texto puro); `birthdate` correta |
| E-mail inválido / duplicado | 400 | 400 | Nenhuma linha extra |
| Campo ausente, `weight_kg="abc"`, `birthdate="17/05/1990"`, `{}`, JSON malformado | 422 | 422 | — |
| `nutricionist_id` inexistente | 4xx | **500 → 409** | Usuário não persistido |
| `GET /user/{id}` | 200 | **422 → 200** | Na base, exigia `?route_user_id=`; agora `data.id == id`, sem `password` |
| `GET /user/999999` / `abc` | 404 / 422 | **422 → 404** / 422 | — |
| `PATCH /update_User` válido | 200 | 200 | Banco atualizado; login com a nova senha funciona |
| PATCH com e-mail inválido / e-mail de outro usuário | 400 | **200 → 400** | E-mail original preservado; nenhum e-mail duplicado |
| PATCH mantendo o mesmo e-mail | 200 | 200 | — |
| `DELETE /delete_User` | 200 | 200 | Linha removida (exclusão física) |
| DELETE de usuário com refeição | 409 | **500 → 409** | Usuário e refeição preservados |
| `GET /login_User` válido | 200 sem hash | **200 com `password` → 200 sem** | — |
| Senha errada / inexistente | 401 / 404 | 401 / 404 | — |

### C.4 Nutricionistas e vínculo

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| `POST /nutricionist` válido | 200 | 200 | Resposta exata; linha com hash argon2 |
| E-mail inválido / CRN fora de `CRN-X XXXXX` / duplicado / campos ausentes | 400/400/400/422 | iguais | — |
| `GET /get_Nutricionist` | 200 sem hash | **200 com `password` → 200 sem** | 404 / 422 para inexistente / `abc` |
| `PATCH /update_Nutricionist` válido / inexistente | 200 / 404 | iguais | Banco atualizado |
| PATCH com CRN ou e-mail inválido | 400 | **200 → 400** | CRN original preservado |
| `DELETE` / inexistente | 200 / 404 | iguais | Linha removida |
| DELETE com usuário vinculado | 409 | **500 → 409** | Nutricionista preservado |
| `GET /login_Nutricionist` | 200 sem hash / 401 / 404 | **com hash → sem** | — |
| Link → listar → unlink | 200 | 200 | `User.nutricionist_id` conferido no banco a cada passo; lista sem `password` (base: com hash) |
| Link com usuário/nutricionista inexistente / parâmetro ausente | 404 / 422 | iguais | — |

### C.5 Alérgenos e dietas

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| `POST /add_allergen {"name"}` | 200 | **500 → 200** | Linha criada; aparece em `/list_allergens` com `allergens_id/allergens_name` |
| `add_allergen` sem nome / nome numérico | 422 | 422 | — |
| Associar → listar → remover | 200 | 200 | `User_Allergen` conferido; lista vazia após remover |
| Associar a usuário ou alérgeno inexistente | 404 | **500 → 404** | — |
| Associação duplicada | 400/409 | **500 → 400** | Só uma linha |
| Listar de usuário inexistente / remover inexistente / parâmetro ausente | 404/404/422 | iguais | — |
| `create_diet` válido → list → update | 200 | 200 | `Diet` com metas; `Diet_Food` = [1,3] e depois [2] |
| Usuário / nutricionista inexistente | 404 | 404 | — |
| Alimento inexistente | 400 | 400 | **Nenhuma** `Diet` persistida (rollback confirmado) |
| `user_id` do body ≠ rota | 400 | **200 → 400** | Na base, a dieta era gravada para o usuário do body, que não foi validado |
| `update_diet` com alimento inexistente | 400 | 400 | Nome e as 2 associações originais preservados |

### C.6 Balança e pareamento

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| `register_balance` / sem `name` / vazio | 200 / 422 | iguais | Linha `Balance` |
| `generate_qr_code` | 200 | 200 | `token_hash == sha256(token)`; expira em ~5 min; `used_at` nulo; PNG válido servido |
| `pair-scale` válido | 200 | 200 | `User_Balance` criado; `Pairing.used_at` preenchido |
| Reuso do token | 400 | 400 | `"Token already used"` |
| Token inválido / expirado (ajustado no banco) / parâmetros ausentes | 404 / 400 / 422 | iguais | — |
| Usuário ou balança inexistente | 404 | **500 → 404** | **Token não é consumido** |
| Pareamento duplicado com novo token | 400/409 | **500 → 400** | Segundo token não é consumido |

### C.7 Alimentos

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| `GET /foods?user_id` | 200 | 200 | 25 itens ordenados; estrutura exata; nutrientes iguais a `Food_Nutrient`; URL da imagem |
| Filtro `name=frango` / sem resultado | 200 | 200 | Todos contêm "frango" / `[]` |
| Usuário alérgico ao alérgeno do alimento 8 | `user_allergic=True` nos alimentos com esse alérgeno | **`set()` → `{8}`** | Comparado com `Allergen_Food` |
| Usuário inexistente / sem `user_id` / `abc` | 404/422/422 | iguais | — |
| `POST /foods` válido | 200 | 200 | `CreatedFood`, `CreatedFood_Nutrient {1:10.5, 2:30}`, `CreatedFood_Allergen [1]` |
| Alérgeno inexistente / nutriente inexistente | 400 | 400 | Nenhum `CreatedFood` parcial |
| Campo extra / `{}` / sem `user_id` | 422 | 422 | — |
| Nome duplicado | 400 | 400 | — |
| Usuário inexistente | 404 | **400 com SQL bruto na mensagem → 404** | Nada persistido |
| `GET /foods/{id}` com 2 alimentos criados | retorna o `id` pedido | **retornava sempre o 1º → correto** | Nutrientes do alimento certo |
| Alimento de outro usuário / inexistente / usuário inexistente | 404 | **200 → 404** | — |
| `user_allergic` em alimento criado | False → True após associar alérgeno | iguais | — |
| `PATCH /foods/{id}` válido | 200 | 200 | Nome e associações substituídos |
| PATCH por não dono / inexistente | 403 / 404 | **400 → 403 / 400 → 404** | — |
| PATCH com alérgeno inválido | 400 | 400 | Nome e nutrientes originais preservados (rollback) |
| `DELETE /foods/{id}` não dono / inexistente / dono | 403/404/200 | **400/400 → 403/404**, 200 | Linha e associações removidas |

### C.8 Marcas, categorias, nutrientes

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| Criar → buscar → renomear → excluir | 200 | 200 | Banco conferido a cada passo |
| Duplicada com outra caixa (`MARCA`) | 400 | 400 | — |
| Nome contido em marca existente ("X" com "X Premium" já cadastrada) | 200 | **400 → 200** | — |
| Busca sem resultado / sem parâmetro / POST vazio | 200 `[]` / 422 / 422 | iguais | — |
| PATCH/DELETE inexistente | 404 | 404 | — |
| DELETE de marca usada por alimento | 409 | **500 → 409** | Marca preservada |
| `GET /categories` | 200 | 200 | Ids 1–7 e nomes iguais a `DEFAULT_CATEGORIES` |
| `GET /nutrients` | 200 | 200 | Estrutura; Proteínas 4 kcal/g, Gorduras 9 kcal/g |
| `GET /nutrients/1` / inexistente / `abc` | 200 / `[]` / 422 | iguais | Exclui os macros; `food_id` correto |

### C.9 Refeições

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| `POST /meals` (alimentos 1 e 3, `saved_meal=true`) | 200 | 200 | `calories` = Σ(quantidade × kcal/unidade) recalculado a partir do banco; `Meal` e `Meal_Food` [1,3] |
| `consumed_at="12:30"` (formato aceito pelo validador do schema) | 200 | **422 → 200** | — |
| `saved_meal=false` | 200, nada gravado | 200 (corpo `null`) | Nenhuma linha (comportamento atual, N06) |
| Lista vazia / usuário ou alimento inexistente / peso 0 ou negativo | 400 | 400 | **Nenhuma** refeição persistida |
| Campo extra / data inválida / `{}` | 422 | 422 | — |
| `GET /meals` | 200 | 200 | Alimentos da refeição com estrutura exata |
| Usuário sem refeições / sem `user_id` | 404 / 422 | iguais | — |
| `PATCH` válido | 200 | 200 | Nome, peso, `Meal_Food`=[6]; **calorias recalculadas** (base: zeradas pelo default `0.0` do body) |
| PATCH por outro usuário | 404 | 404 | — |
| PATCH com `user_id` de outro usuário no body | dono preservado | **refeição transferida → preservado** | — |
| PATCH com alimento inexistente | 400 | 400 | Estado original preservado |
| DELETE por outro usuário / dono / repetido / `abc` | 404/200/404/422 | iguais | `Meal` e `Meal_Food` removidos (sem o `SAWarning` da base) |

### C.10 Upload de imagem

| Cenário | Esperado | Base → Final | Validação |
|---|---|---|---|
| JPEG com `category=frutas` / sem categoria | 200 | 200 | Bytes gravados idênticos ao enviado |
| `content-type: text/plain` | 400 | 400 | Arquivo não gravado |
| Sem arquivo | 422 | 422 | — |
| `filename="../../fora_do_upload.jpg"` | gravar só dentro de `static/images` | **gravado fora → salvo dentro (basename)** | Varredura do diretório de trabalho |
| `category="../../"` e `category="frutas/../../.."` | 400 | **gravado fora → 400** | — |

### C.11 Reconhecimento SigLIP (modelo real)

Pipeline verificado no código (`SiglIp/test_01_Siglip.py`): o upload passa por `Image.open(...).convert("RGB")`. A primeira imagem do usuário é classificada inteira. A partir da segunda, o OpenCV compara com a anterior (cinza, blur, `absdiff`, threshold 25, morfologia, maior contorno com área ≥ 800 px, padding 10) e recorta a região **colorida**. O SigLIP faz classificação **zero-shot imagem × 25 textos** (`logits_per_image`, softmax, top-3). O rótulo top-1 é buscado por nome exato em `Food`; com `weight`, os nutrientes são escalados por `peso/100`.

**Observação:** o pipeline não usa embeddings de alimentos guardados no banco. As 25 descrições textuais (`LABELS`) são codificadas a cada requisição. Nada no modelo, nos rótulos ou nos limiares foi alterado.

| Cenário | Esperado | Recebido | Validação |
|---|---|---|---|
| Todos os 25 `LABELS[*].db_name` existem em `Food` | sim | sim | Consistência rótulo ↔ banco |
| 1ª imagem (batata frita, WEBP) | 200 | 200 | `first_image=true`, `bbox=null`; 3 predições com confiança decrescente em [0,1] e soma ≤ 1; `model_label` corresponde ao `LABELS`; `food_id` existe no banco com o mesmo nome; categoria e marca batem; o esperado está no top-3 |
| `/weight` com `weight=250` (banana) | 200 | 200 | Cada nutriente = valor por 100 g × 2,5, conferido contra `Food_Nutrient` |
| `/weight` sem `weight` | 200 sem `nutrients` | 200 | — |
| Entradas PNG e WEBP do catálogo | 200 | 200 | — |
| Fluxo do firmware: balança vazia → com alimento (fundo 640×480 e alimento colado em 200,120 com 240×240) | `changed=true` + bbox | 200 | bbox cobre a região colada dentro da margem de padding; nutrientes presentes |
| Imagem 1×1 e imagem 4000×3000 | sem erro 500 | 200 / 200 | — |
| Ruído aleatório | — | 200 com um alimento | **Não há limiar** (N05) |
| Segunda imagem idêntica à primeira | 400 | 400 | `"Nenhuma região de diferença..."` |
| Usuário inexistente | 404 | 404 | — |
| Sem arquivo / sem `user_id` / `weight=abc` | 422 | 422 | — |
| Arquivo vazio (as duas rotas) | 400 | 400 | `"Empty image file."` |
| `.txt`, texto com extensão `.jpg`, JPEG truncado | 400 | 400 | `"Invalid image data..."` |
| Imagem inválida não vira "imagem anterior" do usuário | sim | sim | — |
| Modelo indisponível (falha simulada em `_get_model`) | 5xx controlado | 500 | `detail` com a causa; `/health` segue 200 |

**Acurácia nas 25 imagens do catálogo** (`images/alimentos/`, uma por alimento): **top-1 = 23/25, top-3 = 25/25**. Erros de top-1: "Peito de frango, com pele, assado" → "Peito de frango, sem pele, cozido" (0,92) e "Coxa de frango, com pele, assada" → "Frango inteiro, assado, com pele" (0,53). Essas imagens são as do próprio catálogo, **não um conjunto de teste independente**, então o resultado não mede acurácia em produção.

### C.12 Fluxos de integração (`tests/test_flows.py`)

| Fluxo | Passos | Resultado |
|---|---|---|
| Usuário + nutricionista + dieta | cria nutricionista → login → cria usuário → `/auth` → vincula → lista pacientes → cria dieta → lista dietas | Aprovado |
| Alergia | cria alérgeno → associa ao usuário → cria alimento com o alérgeno → `GET /foods/{id}` marca `user_allergic` → lista alérgenos do usuário | Aprovado |
| Pareamento | cadastra balança → gera QR → baixa PNG → pareia → `User_Balance` no banco | Aprovado |
| Balança → refeição | foto vazia → foto com alimento e peso → alimento reconhecido existe no banco → cria refeição com o `food_id` → lista → atualiza → exclui | Aprovado |

---

## D. Problemas identificados

### D.1 Corrigidos

| ID | Severidade | Endpoint(s) | Descrição | Causa raiz | Correção |
|---|---|---|---|---|---|
| P01 | **Crítico** | `GET /login_User/...`, `GET /login_Nutricionist/...`, `GET /get_Nutricionist/{id}`, `GET /list_user_data_by_nutricionist/{id}` | A resposta incluía o **hash da senha** (argon2). Pela listagem de pacientes, qualquer cliente obtinha os hashes de todos os pacientes de um nutricionista | Retorno direto da entidade ORM (dataclass com todas as colunas) | Serializadores `serialize_user` / `serialize_nutricionist`, com os mesmos campos de antes **exceto `password`** |
| P02 | **Crítico** | `POST /upload-image` | **Path traversal**: `filename` ou `category` com `../` gravava arquivos fora de `static/images`, em qualquer lugar onde o processo pudesse escrever (inclusive sobre o código-fonte). Não exige autenticação | Caminho montado por concatenação com valores do cliente; o Starlette não sanitiza `filename` | `basename` do nome; categoria limitada a `[A-Za-z0-9 _.-]+` (e diferente de `.`/`..`); checagem `commonpath`; entrada inválida → 400 |
| P03 | Alto | `GET /user/{user_id}` | Parâmetro de rota ignorado; exigia `?route_user_id=` (sem ele, 422 sempre) | Função declarava `route_user_id` em vez de `user_id` | Parâmetro renomeado para `user_id` |
| P04 | Alto | `GET /foods/{food_id}` | `food_id` ignorado: retornava o primeiro alimento criado pelo usuário; `/foods/999999` retornava 200 | Função não recebia `food_id`; filtrava só por `user_id` | Filtro por `id` **e** dono; 404 quando não pertence ao usuário |
| P05 | Alto | `GET /foods` | `user_allergic` sempre `false` para o catálogo, mesmo com usuário alérgico (impacto direto na segurança do usuário final) | Consulta usava `CreatedFood_Allergen` (ids de alimentos criados) e comparava com ids de `Food` | Consulta passa a usar `Allergen_Food` |
| P06 | Alto | `POST /add_allergen` | 500 em 100% das chamadas | Modelo SQLAlchemy `Allergen` usado como schema do body | Schema Pydantic `PostCreateAllergenBodyRequest {name}` (mesmo JSON) |
| P07 | Médio | `POST /auth/commun_user`, `POST /auth/nutricionist` | Credencial inválida retornava **400**, não o 401 que o código lança | `except Exception` capturava a própria `ReturnException(401)` e relançava com 400 | `except ReturnException: raise` antes do genérico |
| P08 | Médio | `POST/PATCH/DELETE /foods` | 403/404 viravam 400 com mensagem `"403: ..."`; usuário inexistente no POST retornava 400 com **texto SQL bruto** (tabelas e constraints) | `except Exception` genérico | `HTTPException`/`IntegrityError` relançadas; checagem do usuário no POST (404) |
| P09 | Médio | `POST /user`, `DELETE /delete_User`, `DELETE /delete_Nutricionist`, `DELETE /brands`, `POST /add_allergen_to_user`, `POST /pair-scale` | Violações de FK/PK viravam **500** sem tratamento | Ausência de tratamento de `IntegrityError` | Handler global de `IntegrityError` → 409 no formato padrão `ReturnException`, sem SQL na resposta e com log em `warning`; checagens explícitas (404/400) em `add_allergen_to_user` |
| P10 | Médio | `POST /pair-scale` | Não validava usuário/balança. No banco dev, `User_Balance` **não tem FKs** (N03), então registros órfãos seriam gravados e o token consumido | Ausência de validação | 404 para usuário/balança inexistente e 400 para par duplicado, **antes** de consumir o token |
| P11 | Médio | `POST /create_diet/{n}/{u}` | Validava os ids da rota mas gravava os do body, atribuindo a dieta a um usuário não validado (o banco dev não tem FK em `Diet`) | Uso de `diet.user_id` em vez dos parâmetros validados | 400 se os ids do body forem diferentes dos da rota |
| P12 | Médio | `PATCH /update_User`, `PATCH /update_Nutricionist` | Aceitavam e-mail inválido ou já usado por outra conta e CRN fora do formato, regras que o POST aplica | Validações só no POST | Mesmas validações do POST, ignorando o próprio registro na checagem de duplicidade |
| P13 | Médio | `POST /brands` | "Brand already exists" falso quando o nome novo está contido em outro (`%nome%`); `%` e `_` no nome atuavam como curingas | `ILIKE '%nome%'` usado como verificação de duplicidade | Comparação exata sem diferenciar maiúsculas e minúsculas (`lower(name) = lower(:nome)`) |
| P14 | Médio | `POST/PATCH /meals` | O validador declara aceitar `consumed_at` no formato `H:M`, mas `"12:30"` retornava 422 | `field_validator` em modo `after` roda depois da validação de `datetime` do Pydantic | `mode="before"`, aplicado só a strings curtas `HH:MM` (ISO continua igual) |
| P15 | Médio | `PATCH /meals/{meal_id}/{user_id}` | O body podia **transferir a refeição para outro usuário** (`user_id`), e `calories` era sobrescrito pelo default `0.0` do body | `setattr` de todos os campos do body | `user_id` vem da rota; calorias recalculadas com o mesmo cálculo do POST (função `calculate_meal_calories`) |
| P16 | Baixo | `DELETE /meals`, `PATCH /meals` | `SAWarning: expected to delete 2 row(s); 0 were matched` | O flush do ORM removia `Meal` antes das associações (que já tinham ido pelo `ON DELETE CASCADE`) | Exclusão em lote (`query.delete()`), igual ao padrão já usado em `/foods` |

**Mudanças de contrato (justificadas por defeito comprovado):**

- P01: o campo `password` deixa de existir nas 4 respostas. Clientes que o liam não deveriam usá-lo.
- P03: `GET /user/{id}` passa a usar o id da rota; `?route_user_id=` não é mais lido.
- P04: `GET /foods/{food_id}` retorna o alimento pedido.
- P07/P08: códigos de erro passam a ser os que o código já declarava (401/403/404); nos casos de P08, o corpo de erro passa a ser `{"detail": ...}`, padrão do `HTTPException`, já usado no restante da API.
- P09: 500 → 409.
- P11: um body com ids diferentes da rota passa a receber 400.

Os payloads de sucesso dos demais endpoints não mudaram. **Valide com o app e com o firmware** antes do deploy, principalmente P03 e P04.

### D.2 Documentados e não corrigidos

| ID | Severidade | Endpoint(s) | Descrição | Por que não foi corrigido / recomendação |
|---|---|---|---|---|
| N01 | **Crítico** | Todos | **Não há autenticação nem autorização.** `/auth/*` só responde "ok", sem emitir token ou sessão. Todas as rotas confiam no `user_id` enviado pelo cliente: qualquer um na rede pode ler, alterar ou excluir usuários, nutricionistas, dietas e refeições de terceiros. Os 403 de `/foods` comparam com um `user_id` que o próprio chamador informa | Exige desenho de autenticação (ex.: JWT emitido por `/auth/*` + dependência `get_current_user`) e mudança de contrato no app e no firmware. É uma decisão de arquitetura, fora do escopo de correção. **Não exponha a API fora de rede confiável até resolver** |
| N02 | **Crítico** | `GET /login_User/{email}/{password}`, `GET /login_Nutricionist/{email}/{password}` | Senha em texto puro **no caminho da URL**, registrada em logs de acesso, proxies e histórico | Removê-las quebraria clientes. Recomendação: migrar os clientes para `POST /auth/*` e então remover as rotas |
| N03 | Alto (ambiente) | `POST /create_diet`, `GET /list_diets_by_user`, `PATCH /update_diet` | O banco dev (e qualquer banco restaurado do `smart-balance.sql`) tem `Diet.goal varchar NOT NULL` e **não tem** `kcal_goal`, `fat_goal`, `carb_goal`, `protein_goal`. O modelo usa estas últimas, então as 3 rotas devem falhar nesse banco (`UndefinedColumn`). Também faltam FKs em `Diet`, `Diet_Food` e `User_Balance`. `create_all` não migra tabelas existentes | **Verificado por inspeção de schema, não executado no banco dev** (política de somente leitura). Alterar schema é decisão do time. Migração sugerida: `ALTER TABLE "Diet" ADD COLUMN kcal_goal float, ADD COLUMN fat_goal float, ADD COLUMN carb_goal float, ADD COLUMN protein_goal float; ALTER TABLE "Diet" ALTER COLUMN goal DROP NOT NULL;` + FKs. Revise antes de aplicar em produção |
| N04 | Médio | `/food-recognition/*` | A inferência (~0,7 s) roda **dentro do event loop** (`async def` sem threadpool). Durante um reconhecimento, toda a API para: `/health` levou **602 ms** contra ~1 ms ocioso, e 2 reconhecimentos simultâneos levaram 1458 ms (serializados). Além disso, `output/crop.png` é um caminho único compartilhado e `previous_images` é um dict em memória: com threadpool ou com múltiplos workers do uvicorn, haveria condição de corrida entre usuários e perda da imagem anterior | A correção envolve o módulo do pipeline (diretório de saída por requisição) e o modelo de concorrência. Recomendação: `await run_in_threadpool(...)`, `output_dir` por requisição e estado da imagem anterior persistido. Não foi aplicada para não alterar o pipeline sem decisão do time |
| N05 | Médio | `/food-recognition/*` | **Não há limiar de confiança**: o softmax sempre escolhe um dos 25 alimentos, até para ruído aleatório (testado), e não existe resposta "não reconhecido" | Restrição da auditoria: não alterar critérios de classificação. Recomendação: o cliente usar `confidence` e `predictions`, ou definir um limiar com dados reais |
| N06 | Médio | `POST /meals` | Com `saved_meal=false`, retorna `null` (200) sem os valores calculados. As calorias somam os valores **por 100 g** de cada alimento e ignoram `weight_g` | Regra de negócio ambígua. Recomenda-se definir o comportamento esperado (retornar a refeição calculada sem gravar? escalar pelo peso?) |
| N07 | Baixo | `/upload-image`, `/food-recognition/*` | Sem limite de tamanho de upload (o arquivo inteiro vai para a memória). `upload-image` sobrescreve arquivo com o mesmo nome. Os temporários em `tmp/food_recognition` acumulam até o shutdown | Exige definir limites. Imagem 4000×3000 processada sem erro |
| N08 | Baixo | `GET /nutrients`, `POST/PATCH /foods` | O banco dev tem **18 nutrientes com 9 nomes** (ids 1–9 do `seed_nutrients`, 10–18 do catálogo `Food_Nutrient`). `GET /nutrients` lista duplicados, e alimentos criados com ids 1–9 usam outro conjunto de ids que o catálogo | Correção de dados; não altera código |
| N09 | Baixo | `/generate_qr_code/`, `/register_balance` | A URL do QR (`/pair-scale?token=`) aponta para uma rota **só POST** (ler o QR no navegador dá 405). O token não fica vinculado à balança (o `balance_id` é escolhido por quem consome). `register_balance` exige `id` e o ignora | Depende do fluxo do app e do firmware |
| N10 | Baixo | `/`, `/docs`, `/health` | `/` lista rotas desatualizadas. `/docs` usa `base_server_url="https://api.meusite.com"` (placeholder), então o "try it" aponta para um servidor inexistente. `/health` devolve a mensagem crua da exceção (host e porta; a senha não aparece, verificado) | Cosmético/informativo |
| N11 | Baixo | `GET /meals`, `GET /list_user_data_by_nutricionist`, `GET /brands` | `GET /meals` retorna 404 quando não há refeições (em vez de `[]`) e não valida o usuário. A listagem de pacientes retorna `[]` para nutricionista inexistente. O `if brands is None` de `/brands` nunca é verdadeiro | Mantidos para não mudar contrato |
| N12 | Baixo | `POST /user`, `PATCH /update_User` | Sem validação de faixa (peso e altura negativos aceitos; `sex` livre) | Análise de código. O código não define essas regras e elas não foram inventadas |
| N13 | Baixo | `POST /foods` | Unicidade do nome do alimento criado é **global** (entre todos os usuários), com `ILIKE` sem escapar `%`/`_` | Regra de negócio a confirmar |
| N14 | Info | — | `@app.on_event` está depreciado no FastAPI. O transformers avisa sobre `bos/eos_token_id` na config do SigLIP. `test/test_endpoint.py` e `test/rand/*` são scripts manuais com caminhos e credenciais fixas, fora da suíte | — |

---

## E. Alterações realizadas

| Arquivo | Tipo | Alteração |
|---|---|---|
| `application/controller/user_controller.py` | Modificado | P01 (serializadores sem `password`), P03, P06 (schema `PostCreateAllergenBodyRequest`), P09/P10 (checagens em `add_allergen_to_user` e `pair-scale`), P11, P12 |
| `application/controller/food_controller.py` | Modificado | P04, P05, P08, P13, P14, P15 (`calculate_meal_calories` compartilhada entre POST e PATCH), P16 |
| `application/controller/auth_controller.py` | Modificado | P07 |
| `application/controller/vision_recognition_controller.py` | Modificado | P02 |
| `main.py` | Modificado | Handler global de `IntegrityError` → 409 (P09), com log |
| `README.md` | Modificado | Seção "11. Testes automatizados"; corrigida a rota de exemplo (`/user/2`) e as notas desatualizadas sobre `consumed_at` e sobre a suíte |
| `requirements-dev.txt` | Novo | `-r requirements.txt` + `pytest==8.4.2` (única dependência nova, só de desenvolvimento) |
| `pytest.ini` | Novo | `testpaths = tests`, marcador `siglip` |
| `tests/conftest.py` | Novo | Banco isolado com trava de nome, recriação do schema, seed de referência a partir do dump, cwd temporário, fábricas de dados fictícios |
| `tests/test_system.py` | Novo | Raiz, health (inclusive banco fora), docs, OpenAPI, estáticos |
| `tests/test_auth.py` | Novo | `/auth/*` |
| `tests/test_users.py` | Novo | Usuários, nutricionistas, login, vínculo |
| `tests/test_allergens_diets.py` | Novo | Alérgenos e dietas |
| `tests/test_balance_pairing.py` | Novo | Balança, QR code, pareamento |
| `tests/test_foods.py` | Novo | Catálogo, alimentos criados, marcas, categorias, nutrientes |
| `tests/test_meals.py` | Novo | Refeições |
| `tests/test_upload_image.py` | Novo | Upload, incluindo path traversal |
| `tests/test_food_recognition.py` | Novo | Pipeline SigLIP real e erros |
| `tests/test_flows.py` | Novo | Fluxos de integração |
| `tests/perf_endpoints.py` | Novo | Medição de desempenho e concorrência (não roda no pytest) |
| `RELATORIO_AUDITORIA_ENDPOINTS.md` | Novo | Este relatório |

Arquivos **não** alterados: modelos SQLAlchemy, `shared/database.py`, `SiglIp/*` (modelo, rótulos, limiares, pipeline), `compose*.yml`, `Dockerfile`, workflow de deploy, `.env`/`.env.example` e `requirements.txt`.

---

## F. Desempenho

**Condições:** `tests/perf_endpoints.py --reps 20` com uvicorn (1 worker) em `127.0.0.1` e cliente httpx **no mesmo processo** (dividem o GIL, então os números de concorrência são um limite inferior). Banco `Smart-Balance-test` no PostgreSQL 18.7 local (Docker). CPU i5-12600K, sem GPU, 4 threads PyTorch. "SQL" = soma do tempo das consultas da requisição (eventos do SQLAlchemy). "Modelo" = duração do `forward` do SigLIP (hooks do PyTorch, sem alterar o pipeline). Carga do modelo a frio, com cache local: **0,21 s**.

| Endpoint | n | mediana (ms) | p95 (ms) | máx (ms) | SQL mediana (ms) | modelo mediana (ms) | erros |
|---|---|---|---|---|---|---|---|
| GET / | 20 | 0.4 | 0.5 | 0.9 | 0.0 | — | 0 |
| GET /health | 20 | 0.5 | 0.7 | 1.1 | 0.1 | — | 0 |
| GET /docs | 20 | 0.3 | 0.4 | 0.5 | 0.0 | — | 0 |
| GET /openapi.json | 20 | 0.5 | 1.0 | 11.1 | 0.0 | — | 0 |
| GET /images/alimentos/{arquivo} | 20 | 0.9 | 1.4 | 2.4 | 0.0 | — | 0 |
| POST /auth/commun_user | 20 | 37.4 | 45.7 | 50.8 | 0.3 | — | 0 |
| POST /auth/nutricionist | 20 | 37.5 | 41.8 | 41.9 | 0.3 | — | 0 |
| POST /user | 20 | 41.5 | 47.6 | 47.7 | 0.8 | — | 0 |
| GET /user/{user_id} | 20 | 1.7 | 2.0 | 2.0 | 0.2 | — | 0 |
| PATCH /update_User/{user_id} | 20 | 42.0 | 47.1 | 50.0 | 1.0 | — | 0 |
| DELETE /delete_User/{user_id} | 20 | 4.5 | 5.2 | 5.5 | 0.5 | — | 0 |
| GET /login_User/{email}/{password} | 20 | 37.4 | 44.1 | 44.3 | 0.3 | — | 0 |
| POST /nutricionist | 20 | 43.2 | 48.3 | 48.4 | 0.8 | — | 0 |
| GET /get_Nutricionist/{id} | 20 | 2.4 | 4.4 | 4.7 | 0.4 | — | 0 |
| PATCH /update_Nutricionist/{id} | 20 | 42.2 | 45.9 | 47.8 | 1.1 | — | 0 |
| DELETE /delete_Nutricionist/{id} | 20 | 4.3 | 5.2 | 5.5 | 0.6 | — | 0 |
| GET /login_Nutricionist/{email}/{password} | 20 | 37.7 | 40.4 | 40.8 | 0.3 | — | 0 |
| POST /link_user_nutricionist | 20 | 4.3 | 9.4 | 10.7 | 0.8 | — | 0 |
| PATCH /unlink_user_nutricionist/{user_id} | 20 | 2.3 | 3.4 | 3.6 | 0.4 | — | 0 |
| GET /list_user_data_by_nutricionist/{id} | 20 | 3.5 | 5.0 | 5.0 | 0.4 | — | 0 |
| POST /add_allergen_to_user | 20 | 5.8 | 7.2 | 7.3 | 0.8 | — | 0 |
| GET /list_allergens_by_user/{user_id} | 20 | 3.5 | 6.4 | 6.6 | 0.7 | — | 0 |
| DELETE /remove_allergen_from_user | 20 | 4.8 | 7.2 | 9.0 | 0.5 | — | 0 |
| POST /add_allergen | 20 | 12.0 | 13.1 | 13.5 | 2.0 | — | 0 |
| GET /list_allergens | 20 | 2.7 | 5.1 | 9.6 | 0.3 | — | 0 |
| POST /create_diet/{nutri}/{user} | 20 | 11.5 | 21.8 | 22.8 | 2.5 | — | 0 |
| GET /list_diets_by_user/{user_id} | 20 | 2.0 | 4.0 | 4.2 | 0.4 | — | 0 |
| PATCH /update_diet/{diet_id} | 20 | 6.2 | 12.6 | 15.5 | 1.0 | — | 0 |
| POST /register_balance | 20 | 8.3 | 13.9 | 15.1 | 1.1 | — | 0 |
| POST /generate_qr_code/ | 20 | 10.6 | 18.5 | 18.5 | 0.5 | — | 0 |
| POST /pair-scale | 20 | 6.8 | 11.0 | 13.2 | 1.3 | — | 0 |
| GET /foods | 20 | 14.9 | 21.7 | 32.6 | 4.7 | — | 0 |
| GET /foods?name=frango | 20 | 11.4 | 35.4 | 54.8 | 3.5 | — | 0 |
| GET /foods/{food_id} | 20 | 2.6 | 3.1 | 3.4 | 0.7 | — | 0 |
| POST /foods | 20 | 9.8 | 24.3 | 26.1 | 2.3 | — | 0 |
| PATCH /foods/{food_id} | 20 | 14.6 | 21.3 | 23.3 | 3.5 | — | 0 |
| DELETE /foods/{food_id} | 20 | 15.1 | 18.5 | 19.7 | 3.1 | — | 0 |
| GET /brands | 20 | 6.6 | 7.6 | 8.2 | 0.9 | — | 0 |
| POST /brands | 20 | 14.1 | 15.9 | 16.2 | 2.6 | — | 0 |
| PATCH /brands/{brand_id} | 20 | 1.9 | 11.8 | 15.5 | 0.3 | — | 0 |
| DELETE /brands/{brand_id} | 20 | 9.5 | 12.6 | 12.9 | 1.8 | — | 0 |
| GET /categories | 20 | 6.5 | 7.6 | 7.9 | 0.9 | — | 0 |
| GET /nutrients | 20 | 7.3 | 9.3 | 11.4 | 1.0 | — | 0 |
| GET /nutrients/{food_id} | 20 | 8.7 | 11.5 | 13.9 | 1.6 | — | 0 |
| GET /meals | 20 | 1.7 | 8.3 | 11.3 | 0.4 | — | 0 |
| POST /meals | 20 | 17.8 | 27.0 | 28.2 | 4.6 | — | 0 |
| PATCH /meals/{meal_id}/{user_id} | 20 | 9.2 | 27.6 | 28.4 | 1.8 | — | 0 |
| DELETE /meals/{meal_id}/{user_id} | 20 | 5.4 | 12.1 | 12.9 | 0.7 | — | 0 |
| POST /upload-image | 20 | 0.8 | 1.4 | 1.5 | 0.0 | — | 0 |
| POST /food-recognition/image (1ª imagem) | 10 | 744.1 | 759.8 | 759.8 | 0.7 | 727.9 | 0 |
| POST /food-recognition/image/weight (1ª imagem) | 10 | 746.5 | 757.1 | 757.1 | 1.1 | 728.4 | 0 |
| POST /food-recognition/image/weight (detecção de mudança) | 10 | 735.9 | 742.0 | 742.0 | 1.1 | 717.1 | 0 |

**Leitura dos resultados:**

- **Reconhecimento:** cerca de 98% do tempo total é o forward do SigLIP (~720 ms em CPU). Upload, decodificação, OpenCV, banco e serialização somam ~15–20 ms. O forward codifica a imagem **e** os 25 textos a cada requisição.
- **~37–43 ms** nas rotas com hash ou verificação de senha: custo esperado do argon2 (`PasswordHash.recommended()`). Não é problema.
- `GET /foods` faz 1 consulta de nutrientes por alimento (padrão N+1: 3 consultas fixas + 25). Hoje são ~15 ms; o custo cresce de forma linear com o catálogo.
- **Estabilidade:** 0 erros em todas as ~1.000 requisições sequenciais.
- **Concorrência** (8 threads × 25 requisições): `GET /foods` 200 req / 0 erros / 21 req/s; `GET /meals` 200 / 0 / 30 req/s; `GET /health` 200 / 0 / 615 req/s. Conexões PostgreSQL abertas no banco de teste: 1 antes, **5 depois**, igual ao `pool_size` padrão, sem crescimento (nenhum vazamento observado).
- **Reconhecimento simultâneo** de 2 usuários: ambos 200, mas em 1458 ms no total (serializados). Com uma inferência em andamento, `/health` levou **602 ms** (contra ~1 ms) — evidência do N04.
- Suíte pytest completa: ~19 s (16 testes SigLIP); `-m "not siglip"`: ~8 s.

Não foram definidas metas de desempenho: os números são uma medição de referência, não um critério de aprovação.

---

## G. Pendências

| Item | Motivo |
|---|---|
| Executar as rotas de dieta contra o **banco dev real** (N03) | O banco dev foi tratado como somente leitura. A falha prevista vem da comparação do schema (`inspect`) com o modelo, não de uma execução. Depende de decisão sobre migração |
| Testes de autorização real (usuário sem permissão, token inválido ou expirado) | Não há mecanismo de autenticação para testar (N01). Os testes cobrem só as checagens de dono baseadas em `user_id` que existem no código |
| Validação no **banco de produção** e no ambiente Docker (`compose.yml`) | Fora do escopo por segurança (proibido testar em produção). A imagem Docker não foi construída |
| Compatibilidade com o firmware em hardware real | Não há firmware ou balança neste ambiente. O contrato JSON das rotas de reconhecimento (`changed`, `first_image`, `items[].bbox`, `items[].recognized_food.{model, language, recognized_food, confidence, predictions}`) **não mudou**. Os fluxos foram simulados com imagens sintéticas (fundo + alimento colado) |
| Acurácia do SigLIP em fotos reais da balança | Só as 25 imagens do catálogo foram avaliadas (não independentes). O dataset `SiglIp/images/` usa outras categorias (rótulos em inglês fora dos 25 do banco) e não foi usado para medir acurácia |
| Condição de corrida em `output/crop.png` (N04) | Analisada no código. Hoje não aparece em execução porque o event loop bloqueado serializa as inferências. Só se manifestaria após a correção de concorrência recomendada |
| Imagem acima do limite de "decompression bomb" do Pillow (>178 MP) | Não testada para não consumir memória excessiva. Pelo código, `Image.open` dentro de `try` devolveria 400 |
| Indisponibilidade real do HuggingFace / download do modelo | Os testes rodam offline (`HF_HUB_OFFLINE=1`) com o modelo em cache. A indisponibilidade foi simulada com falha em `_get_model` (retornou 500 controlado) |

---

## H. Como executar os testes

Pré-requisitos: `.env` configurado (mesmo do desenvolvimento), `.venv` criado conforme o README e o modelo SigLIP no cache do HuggingFace (opcional: sem ele, os testes SigLIP são pulados).

```bash
# 1. dependencias de teste (uma vez)
uv pip install --python .venv/bin/python -r requirements-dev.txt
#    (ou: .venv/bin/python -m pip install -r requirements-dev.txt)

# 2. PostgreSQL local
docker compose -f compose.dev.yml up -d

# 3. suite completa (inclui o SigLIP real) — ~20 s
.venv/bin/python -m pytest

# 3b. sem o modelo SigLIP — ~8 s
.venv/bin/python -m pytest -m "not siglip"

# 3c. um arquivo/teste especifico
.venv/bin/python -m pytest tests/test_meals.py -v

# 4. medicao de desempenho (opcional; nao faz parte do pytest)
.venv/bin/python tests/perf_endpoints.py --reps 20
```

Notas:

- A suíte cria e **recria do zero** o banco `Smart-Balance-test` a cada execução. Outro nome pode ser passado com `TEST_POSTGRES_DB=<nome>_test`; nomes que não terminam em `test` são recusados.
- O banco de desenvolvimento `Smart-Balance` não é lido nem escrito pela suíte.
- Os arquivos gerados pela API durante os testes vão para um diretório temporário (`/tmp/smart_balance_tests_*`).
