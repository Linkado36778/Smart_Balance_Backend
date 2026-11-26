# Imagem de PRODUCAO do backend Smart Balance (VPS sem GPU).
#
# Diferencas em relacao ao Dockerfile da raiz (usado pelo CI):
#   - PyTorch/torchvision/torchaudio instalados a partir do indice CPU do
#     PyTorch (evita ~6 GB de bibliotecas CUDA inuteis numa VPS sem GPU).
#     As versoes continuam exatamente as do requirements.txt.
#   - Copia apenas o codigo necessario para a API (sem testes/datasets).
#   - O modelo SigLIP NAO e embutido na imagem: fica no volume HF_HOME
#     (/models/hf), preservado entre rebuilds e rollbacks.
#
# Build (contexto = raiz do release):
#   docker build -f deploy/Dockerfile -t sb-backend:<tag> .

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models/hf

# libgl/libglib nao sao necessarias (opencv-python-headless); libgomp e usada
# pelo PyTorch em CPU.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements.txt

COPY main.py ./
COPY application ./application
COPY shared ./shared
COPY SiglIp/test_01_Siglip.py ./SiglIp/test_01_Siglip.py
COPY images ./images

RUN useradd --system --uid 10001 --home-dir /app sbapp && \
    mkdir -p /app/static/images /app/qr_codes /app/tmp /app/output /models/hf && \
    chown -R sbapp:sbapp /app /models

USER sbapp

EXPOSE 8000

# 1 worker: o estado "imagem anterior por usuario" do reconhecimento fica em
# memoria do processo e o SigLIP ocupa ~1 GB de RAM por processo.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
