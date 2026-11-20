"""Medicao basica de desempenho/estabilidade dos endpoints (nao e teste de carga).

Uso (a partir da raiz do projeto, com o PostgreSQL de desenvolvimento no ar):

    .venv/bin/python tests/perf_endpoints.py            # 20 repeticoes por endpoint
    .venv/bin/python tests/perf_endpoints.py --reps 50

- Usa o MESMO banco isolado da suite (``Smart-Balance-test``), recriado do zero.
- Sobe a API com uvicorn em 127.0.0.1 numa porta livre (processo local).
- Tempo de banco: soma das consultas SQL da requisicao (eventos do SQLAlchemy).
- Tempo do SigLIP: duracao do forward do modelo (hooks do PyTorch), sem
  alterar o pipeline; o restante e upload, decodificacao, pre-processamento,
  consultas e serializacao.
- Concorrencia: 8 threads x 25 requisicoes em rotas de leitura; verifica erros
  e conexoes abertas no PostgreSQL antes/depois.
"""

import argparse
import hashlib
import os
import socket
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest  # noqa: E402  (configura env/banco de testes exatamente como a suite)

import httpx  # noqa: E402
import uvicorn  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import event, text  # noqa: E402

from application.models.application_models import Base  # noqa: E402
from shared.database import engine, initialize_database  # noqa: E402

PASSWORD = conftest.TEST_PASSWORD
DB_TIME = threading.local()


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    conftest._seed_reference_data()
    initialize_database()


@event.listens_for(engine, "before_cursor_execute")
def _before(conn, cursor, statement, params, context, executemany):
    conn.info.setdefault("t0", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def _after(conn, cursor, statement, params, context, executemany):
    elapsed = time.perf_counter() - conn.info["t0"].pop()
    TOTALS["db"] += elapsed


TOTALS = {"db": 0.0, "model": 0.0}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server():
    os.chdir(conftest.WORK_DIR)
    from main import app

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}"


def jpeg(image):
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def pg_connections():
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = :d"), {"d": conftest.TEST_DB_NAME}
        ).scalar()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reps", type=int, default=20)
    args = parser.parse_args()
    reps = args.reps

    reset_db()
    server, base = start_server()
    http = httpx.Client(base_url=base, timeout=120)

    # ---------------------------------------------------------- dados base
    def new_user(**extra):
        email = conftest.unique_email("perf")
        body = {"email": email, "birthdate": "1990-01-01", "weight_kg": 70, "height_m": 1.7, "sex": "M",
                "password": PASSWORD, "is_active": True, **extra}
        return http.post("/user", json=body).json()["data"]

    def new_nutri():
        email = conftest.unique_email("perfn")
        http.post("/nutricionist", json={"email": email, "password": PASSWORD, "phone": "1", "crn": "CRN-1 12345"})
        return http.get(f"/login_Nutricionist/{email}/{PASSWORD}").json()

    user = new_user()
    nutri = new_nutri()
    http.post("/link_user_nutricionist", params={"user_id": user["id"], "nutricionist_id": nutri["id"]})
    http.post("/add_allergen_to_user", json={"user_id": user["id"], "allergen_id": 1})
    http.post("/foods", params={"user_id": user["id"]}, json={"name": "perf-food", "nutrients": [{"id": 1, "amount": 5}]})
    created_food_id = http.get("/foods/1", params={"user_id": user["id"]})  # nao usado; aquece rota
    from application.models.application_models import CreatedFood
    from shared.database import SESSEON_LOCAL

    with SESSEON_LOCAL() as s:
        created_food_id = s.query(CreatedFood).filter_by(user_id=user["id"]).one().id
    meal_body = {"name": "perf", "user_id": user["id"], "consumed_at": "2026-11-20T12:00:00", "weight_g": 200,
                 "list_foods_ids": [1, 3], "saved_meal": True}
    meal_id = http.post("/meals", json=meal_body).json()["id"]
    diet_body = {"name": "perf", "user_id": user["id"], "nutricionist_id": nutri["id"], "list_foods_ids": [1]}
    diet_id = http.post(f"/create_diet/{nutri['id']}/{user['id']}", json=diet_body).json()["data"]["diet_id"]
    http.post("/brands", json={"name": "perf-brand"})
    brand_id = http.get("/brands", params={"query_brand_name": "perf-brand"}).json()["data"][0]["id"]
    balance_id = http.post("/register_balance", json={"id": 0, "name": "perf"}).json()["data"]["id"]

    def token():
        qr = http.post("/generate_qr_code/").json()["data"]
        return parse_qs(urlparse(qr["pairing_url"]).query)["token"][0]

    food_img = (conftest.PROJECT_ROOT / "images/alimentos/batata-inglesa-frita.webp").read_bytes()

    def fresh_user_id():
        return new_user()["id"]

    # (rotulo, funcao que devolve (method, url, kwargs) para cada repeticao)
    E = []
    add = lambda label, fn: E.append((label, fn))  # noqa: E731
    add("GET /", lambda: ("GET", "/", {}))
    add("GET /health", lambda: ("GET", "/health", {}))
    add("GET /docs", lambda: ("GET", "/docs", {}))
    add("GET /openapi.json", lambda: ("GET", "/openapi.json", {}))
    add("GET /images/alimentos/{arquivo}", lambda: ("GET", "/images/alimentos/arroz-tipo-1-cozido.jpg", {}))
    add("POST /auth/commun_user", lambda: ("POST", "/auth/commun_user", {"json": {"email": user["email"], "password": PASSWORD}}))
    add("POST /auth/nutricionist", lambda: ("POST", "/auth/nutricionist", {"json": {"email": nutri["email"], "password": PASSWORD}}))
    add("POST /user", lambda: ("POST", "/user", {"json": {"email": conftest.unique_email("p"), "birthdate": "1990-01-01", "weight_kg": 70,
                                                          "height_m": 1.7, "sex": "M", "password": PASSWORD, "is_active": True}}))
    add("GET /user/{user_id}", lambda: ("GET", f"/user/{user['id']}", {}))
    add("PATCH /update_User/{user_id}", lambda: ("PATCH", f"/update_User/{fresh_user_id()}", {"json": {
        "email": conftest.unique_email("u"), "birthdate": "1990-01-01", "weight_kg": 71, "height_m": 1.7, "sex": "M", "password": PASSWORD, "is_active": True}}))
    add("DELETE /delete_User/{user_id}", lambda: ("DELETE", f"/delete_User/{fresh_user_id()}", {}))
    add("GET /login_User/{email}/{password}", lambda: ("GET", f"/login_User/{user['email']}/{PASSWORD}", {}))
    add("POST /nutricionist", lambda: ("POST", "/nutricionist", {"json": {"email": conftest.unique_email("n"), "password": PASSWORD, "phone": "1", "crn": "CRN-1 12345"}}))
    add("GET /get_Nutricionist/{id}", lambda: ("GET", f"/get_Nutricionist/{nutri['id']}", {}))
    add("PATCH /update_Nutricionist/{id}", lambda: ("PATCH", f"/update_Nutricionist/{new_nutri()['id']}", {"json": {"email": conftest.unique_email("n"), "password": PASSWORD, "phone": "2", "crn": "CRN-2 12345"}}))
    add("DELETE /delete_Nutricionist/{id}", lambda: ("DELETE", f"/delete_Nutricionist/{new_nutri()['id']}", {}))
    add("GET /login_Nutricionist/{email}/{password}", lambda: ("GET", f"/login_Nutricionist/{nutri['email']}/{PASSWORD}", {}))
    add("POST /link_user_nutricionist", lambda: ("POST", "/link_user_nutricionist", {"params": {"user_id": user["id"], "nutricionist_id": nutri["id"]}}))
    add("PATCH /unlink_user_nutricionist/{user_id}", lambda: ("PATCH", f"/unlink_user_nutricionist/{fresh_user_id()}", {}))
    add("GET /list_user_data_by_nutricionist/{id}", lambda: ("GET", f"/list_user_data_by_nutricionist/{nutri['id']}", {}))
    add("POST /add_allergen_to_user", lambda: ("POST", "/add_allergen_to_user", {"json": {"user_id": fresh_user_id(), "allergen_id": 2}}))
    add("GET /list_allergens_by_user/{user_id}", lambda: ("GET", f"/list_allergens_by_user/{user['id']}", {}))

    def remove_allergen():
        uid = fresh_user_id()
        http.post("/add_allergen_to_user", json={"user_id": uid, "allergen_id": 3})
        return ("DELETE", "/remove_allergen_from_user", {"params": {"user_id": uid, "allergen_id": 3}})

    add("DELETE /remove_allergen_from_user", remove_allergen)
    add("POST /add_allergen", lambda: ("POST", "/add_allergen", {"json": {"name": f"perf-{uuid.uuid4().hex[:6]}"}}))
    add("GET /list_allergens", lambda: ("GET", "/list_allergens", {}))
    add("POST /create_diet/{nutri}/{user}", lambda: ("POST", f"/create_diet/{nutri['id']}/{user['id']}", {"json": diet_body}))
    add("GET /list_diets_by_user/{user_id}", lambda: ("GET", f"/list_diets_by_user/{user['id']}", {}))
    add("PATCH /update_diet/{diet_id}", lambda: ("PATCH", f"/update_diet/{diet_id}", {"json": diet_body}))
    add("POST /register_balance", lambda: ("POST", "/register_balance", {"json": {"id": 0, "name": "b"}}))
    add("POST /generate_qr_code/", lambda: ("POST", "/generate_qr_code/", {}))
    add("POST /pair-scale", lambda: ("POST", "/pair-scale", {"params": {"user_id": fresh_user_id(), "balance_id": balance_id, "token": token()}}))
    add("GET /foods", lambda: ("GET", "/foods", {"params": {"user_id": user["id"]}}))
    add("GET /foods?name=frango", lambda: ("GET", "/foods", {"params": {"user_id": user["id"], "name": "frango"}}))
    add("GET /foods/{food_id}", lambda: ("GET", f"/foods/{created_food_id}", {"params": {"user_id": user["id"]}}))
    add("POST /foods", lambda: ("POST", "/foods", {"params": {"user_id": user["id"]}, "json": {"name": f"pf-{uuid.uuid4().hex[:8]}", "nutrients": [{"id": 1, "amount": 3}], "allergen_ids": [1]}}))
    add("PATCH /foods/{food_id}", lambda: ("PATCH", f"/foods/{created_food_id}", {"params": {"user_id": user["id"]}, "json": {"name": "perf-food", "nutrients": [{"id": 2, "amount": 4}]}}))

    def delete_food():
        name = f"del-{uuid.uuid4().hex[:8]}"
        http.post("/foods", params={"user_id": user["id"]}, json={"name": name})
        with SESSEON_LOCAL() as s:
            fid = s.query(CreatedFood).filter_by(name=name).one().id
        return ("DELETE", f"/foods/{fid}", {"params": {"user_id": user["id"]}})

    add("DELETE /foods/{food_id}", delete_food)
    add("GET /brands", lambda: ("GET", "/brands", {"params": {"query_brand_name": "perf"}}))
    add("POST /brands", lambda: ("POST", "/brands", {"json": {"name": f"pb-{uuid.uuid4().hex[:8]}"}}))
    add("PATCH /brands/{brand_id}", lambda: ("PATCH", f"/brands/{brand_id}", {"json": {"name": "perf-brand"}}))

    def delete_brand():
        name = f"db-{uuid.uuid4().hex[:8]}"
        http.post("/brands", json={"name": name})
        bid = http.get("/brands", params={"query_brand_name": name}).json()["data"][0]["id"]
        return ("DELETE", f"/brands/{bid}", {})

    add("DELETE /brands/{brand_id}", delete_brand)
    add("GET /categories", lambda: ("GET", "/categories", {}))
    add("GET /nutrients", lambda: ("GET", "/nutrients", {}))
    add("GET /nutrients/{food_id}", lambda: ("GET", "/nutrients/1", {}))
    add("GET /meals", lambda: ("GET", "/meals", {"params": {"user_id": user["id"]}}))
    add("POST /meals", lambda: ("POST", "/meals", {"json": meal_body}))
    add("PATCH /meals/{meal_id}/{user_id}", lambda: ("PATCH", f"/meals/{meal_id}/{user['id']}", {"json": meal_body}))
    add("DELETE /meals/{meal_id}/{user_id}", lambda: ("DELETE", f"/meals/{http.post('/meals', json=meal_body).json()['id']}/{user['id']}", {}))
    add("POST /upload-image", lambda: ("POST", "/upload-image", {"params": {"category": "perf"}, "files": {"file": ("p.jpg", jpeg(Image.new("RGB", (640, 480))), "image/jpeg")}}))

    # ------------------------------------------------- SigLIP (hooks no forward)
    import SiglIp.test_01_Siglip as siglip

    t0 = time.perf_counter()
    _, model = siglip._get_model()
    model_load = time.perf_counter() - t0
    model_t = {}
    model.register_forward_pre_hook(lambda m, a, k=None: model_t.__setitem__("t", time.perf_counter()), with_kwargs=False)

    def _post_hook(m, a, o):
        TOTALS["model"] += time.perf_counter() - model_t["t"]

    model.register_forward_hook(_post_hook)
    from application.controller import food_recognition

    def recog_first():
        food_recognition.previous_images.clear()
        return ("POST", "/food-recognition/image", {"params": {"user_id": user["id"]}, "files": {"file": ("f.webp", food_img, "image/webp")}})

    def recog_weight_first():
        food_recognition.previous_images.clear()
        return ("POST", "/food-recognition/image/weight", {"params": {"user_id": user["id"], "weight": 150}, "files": {"file": ("f.webp", food_img, "image/webp")}})

    bg = Image.new("RGB", (640, 480), (235, 235, 235))
    fg = bg.copy()
    fg.paste(Image.open(BytesIO(food_img)).convert("RGB").resize((240, 240)), (200, 120))
    bg_b, fg_b = jpeg(bg), jpeg(fg)

    def recog_change():
        food_recognition.previous_images.clear()
        http.post("/food-recognition/image/weight", params={"user_id": user["id"], "weight": 0}, files={"file": ("bg.jpg", bg_b, "image/jpeg")})
        TOTALS["db"] = TOTALS["model"] = 0.0
        return ("POST", "/food-recognition/image/weight", {"params": {"user_id": user["id"], "weight": 150}, "files": {"file": ("fg.jpg", fg_b, "image/jpeg")}})

    add("POST /food-recognition/image (1a imagem)", recog_first)
    add("POST /food-recognition/image/weight (1a imagem)", recog_weight_first)
    add("POST /food-recognition/image/weight (deteccao de mudanca)", recog_change)

    # ------------------------------------------------------------- execucao
    results = []
    for label, build in E:
        times, dbs, models, errors, statuses = [], [], [], 0, set()
        n = reps if "food-recognition" not in label else max(5, reps // 2)
        for _ in range(n):
            method, url, kwargs = build()
            TOTALS["db"] = TOTALS["model"] = 0.0
            start = time.perf_counter()
            response = http.request(method, url, **kwargs)
            times.append(time.perf_counter() - start)
            dbs.append(TOTALS["db"])
            models.append(TOTALS["model"])
            statuses.add(response.status_code)
            if response.status_code >= 400:
                errors += 1
        times.sort()
        results.append({
            "label": label, "n": n, "median_ms": statistics.median(times) * 1000,
            "p95_ms": times[max(0, int(round(0.95 * n)) - 1)] * 1000, "max_ms": times[-1] * 1000,
            "db_ms": statistics.median(dbs) * 1000, "model_ms": statistics.median(models) * 1000,
            "errors": errors, "statuses": sorted(statuses),
        })

    # ----------------------------------------------------- concorrencia/leaks
    conns_before = pg_connections()
    concurrency = {}
    for label, path, params in (("GET /foods", "/foods", {"user_id": user["id"]}), ("GET /meals", "/meals", {"user_id": user["id"]}),
                                ("GET /health", "/health", {})):
        def worker(_):
            codes = []
            with httpx.Client(base_url=base, timeout=60) as c:
                for _ in range(25):
                    codes.append(c.get(path, params=params).status_code)
            return codes
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as pool:
            codes = [code for chunk in pool.map(worker, range(8)) for code in chunk]
        elapsed = time.perf_counter() - start
        concurrency[label] = {"requests": len(codes), "errors": sum(c >= 400 for c in codes), "seconds": elapsed,
                              "rps": len(codes) / elapsed}
    time.sleep(0.5)
    conns_after = pg_connections()

    # concorrencia no reconhecimento: 2 usuarios diferentes ao mesmo tempo (deteccao de mudanca)
    users2 = [new_user()["id"] for _ in range(2)]
    food_recognition.previous_images.clear()
    for uid in users2:
        http.post("/food-recognition/image/weight", params={"user_id": uid, "weight": 0}, files={"file": ("bg.jpg", bg_b, "image/jpeg")})
    def recog_worker(uid):
        with httpx.Client(base_url=base, timeout=120) as c:
            r = c.post("/food-recognition/image/weight", params={"user_id": uid, "weight": 100}, files={"file": ("fg.jpg", fg_b, "image/jpeg")})
            return r.status_code
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        recog_codes = list(pool.map(recog_worker, users2))
    recog_parallel = time.perf_counter() - start

    # ----------------------------------------------------------- relatorio
    import platform
    import torch

    print(f"\nAmbiente: {platform.platform()} | Python {platform.python_version()} | torch {torch.__version__} | "
          f"device={siglip.device} | threads torch={torch.get_num_threads()} | CPU logicos={os.cpu_count()}")
    print(f"PostgreSQL: {engine.dialect.server_version_info} em {os.environ['POSTGRES_HOST']} (banco {conftest.TEST_DB_NAME})")
    print(f"Carga do modelo SigLIP (cache local, a frio): {model_load:.2f}s\n")
    print("| Endpoint | n | mediana (ms) | p95 (ms) | max (ms) | SQL mediana (ms) | modelo mediana (ms) | erros | status |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results:
        print(f"| {r['label']} | {r['n']} | {r['median_ms']:.1f} | {r['p95_ms']:.1f} | {r['max_ms']:.1f} | {r['db_ms']:.1f} | "
              f"{r['model_ms']:.1f} | {r['errors']} | {','.join(map(str, r['statuses']))} |")
    print("\nConcorrencia (8 threads x 25 req):")
    for label, c in concurrency.items():
        print(f"- {label}: {c['requests']} req, {c['errors']} erros, {c['seconds']:.2f}s, {c['rps']:.0f} req/s")
    print(f"- Conexoes PostgreSQL abertas no banco de teste: antes={conns_before} depois={conns_after} (pool padrao: 5 + overflow 10)")
    print(f"- Reconhecimento simultaneo de 2 usuarios: status={recog_codes}, {recog_parallel*1000:.0f} ms no total")

    server.should_exit = True


if __name__ == "__main__":
    main()
