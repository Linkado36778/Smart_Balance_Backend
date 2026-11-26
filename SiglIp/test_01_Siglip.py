from transformers import AutoProcessor, AutoModel
import torch
from PIL import Image
from io import BytesIO
import base64
import binascii
import os
import cv2

from application.controller.food_controller import get_food_nutrients_by_weight
from application.models.application_models import Food
from shared.database import build_model_label
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

# ----------------------------
# CONFIG
# ----------------------------

# DATASET_DIR = "images"
# OUTPUT_CSV = "test01_siglip_results.csv"


####NÃO ALTERAR AQUI####
# MODEL_NAME = "SigLIP"
# LABEL_LANGUAGE = "EN"

# VALID_EXTENSIONS = {
#     ".jpg",
#     ".jpeg",
#     ".png",
#     ".webp"
# }

# LABELS = [
#     "white rice",
#     "brown rice",
#     "fried rice",
#     "quinoa",
#     "couscous",
#     "mashed potatoes",
#     "french fries",

#     "spaghetti",
#     "linguine",
#     "fettuccine",
#     "penne pasta",
#     "macaroni",
#     "ramen noodles",

#     "grilled chicken",
#     "fried chicken",
#     "roasted chicken",
#     "turkey breast",
#     "pork chop",
#     "beef steak",

#     "green salad",
#     "lettuce",
#     "spinach",
#     "kale",
#     "arugula",

#     "tomato",
#     "red apple",
#     "red bell pepper",
#     "strawberry",
#     "cherry tomato",

#     "black beans",
#     "kidney beans",
#     "pinto beans",
#     "lentils",
#     "chickpeas",

#     "carrot",
#     "sweet potato",
#     "pumpkin",
#     "cantaloupe",

#     "mozzarella cheese",
#     "cheddar cheese",
#     "cottage cheese",
#     "yogurt",

#     "scrambled eggs",
#     "fried egg",
#     "boiled egg",
#     "omelet"
# ]
####não alterar acima####



MODEL_NAME = "SigLIP"
LABEL_LANGUAGE = "EN/PT-BR"

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

# Os prompts (labels) do SigLIP ficam no banco, na coluna Food.model_label (os
# curados dos alimentos globais sao semeados por
# shared.database.DEFAULT_FOOD_MODEL_LABELS). Alimento criado pelo usuario sem
# prompt recebe um gerado a partir do nome (shared.database.build_model_label).

# ----------------------------
# MODEL
# ----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"

# Pode ser um identificador do HuggingFace Hub ou o caminho absoluto de uma
# pasta local com o modelo ja baixado (configuravel via variavel de ambiente).
model_name = os.getenv("SIGLIP_MODEL_NAME", "google/siglip-base-patch16-224")

processor = None
model = None

# Cache de embeddings de texto (prompt -> vetor normalizado). Os prompts sao
# codificados uma unica vez; em cada requisicao so a imagem passa pelo modelo.
# Como a chave e o proprio texto, um prompt editado gera um embedding novo.
_text_embedding_cache: dict[str, torch.Tensor] = {}

# ----------------------------
# IMAGE RECOGNITION
# ----------------------------

# ---------------------------------------------------------------------------
# Etapa 1 — OpenCV
# ---------------------------------------------------------------------------

def find_changed_region(
    prev_path,
    curr_path,
    output_dir="output",
    min_area=800,
    thresh_value=25,
    kernel_size=5,
    morph_iterations=2,
    padding=10,
    merge_boxes=False,
):
    """
    Compara a imagem anterior e a imagem atual e encontra a região
    que sofreu alteração.

    A comparação é feita em escala de cinza.

    IMPORTANTE:
        A escala de cinza NÃO é enviada ao SigLIP.

        Depois que a região alterada é encontrada, o recorte é feito
        diretamente sobre a imagem atual colorida.

    Retorna:
        crop_path
        bbox = (x, y, width, height)
    """

    os.makedirs(output_dir, exist_ok=True)

    # -----------------------------------------------------------------------
    # Carrega as imagens
    # -----------------------------------------------------------------------

    prev_color = cv2.imread(prev_path)
    curr_color = cv2.imread(curr_path)

    if prev_color is None:
        raise FileNotFoundError(
            f"Não foi possível abrir a imagem anterior: {prev_path}"
        )

    if curr_color is None:
        raise FileNotFoundError(
            f"Não foi possível abrir a imagem atual: {curr_path}"
        )

    print("\n--- Imagens carregadas ---")
    print(f"Anterior: {prev_path}")
    print(f"Atual:    {curr_path}")

    # -----------------------------------------------------------------------
    # Garante que as imagens tenham o mesmo tamanho
    # -----------------------------------------------------------------------

    if prev_color.shape != curr_color.shape:

        print(
            "\nAs imagens possuem tamanhos diferentes."
            "\nRedimensionando a imagem anterior para o tamanho da atual..."
        )

        prev_color = cv2.resize(
            prev_color,
            (curr_color.shape[1], curr_color.shape[0])
        )

    # -----------------------------------------------------------------------
    # Escala de cinza
    #
    # A escala de cinza é usada APENAS para comparação.
    # -----------------------------------------------------------------------

    prev_gray = cv2.cvtColor(
        prev_color,
        cv2.COLOR_BGR2GRAY
    )

    curr_gray = cv2.cvtColor(
        curr_color,
        cv2.COLOR_BGR2GRAY
    )

    # -----------------------------------------------------------------------
    # Suavização
    #
    # Reduz pequenas diferenças causadas por ruído da câmera.
    # -----------------------------------------------------------------------

    prev_gray = cv2.GaussianBlur(
        prev_gray,
        (5, 5),
        0
    )

    curr_gray = cv2.GaussianBlur(
        curr_gray,
        (5, 5),
        0
    )

    # -----------------------------------------------------------------------
    # Diferença absoluta
    # -----------------------------------------------------------------------

    diff = cv2.absdiff(
        prev_gray,
        curr_gray
    )

    # -----------------------------------------------------------------------
    # Threshold
    #
    # Pixels cuja diferença é maior que thresh_value tornam-se brancos.
    # -----------------------------------------------------------------------

    _, mask = cv2.threshold(
        diff,
        thresh_value,
        255,
        cv2.THRESH_BINARY
    )

    # -----------------------------------------------------------------------
    # Operações morfológicas
    #
    # OPEN:
    #     Remove pequenos pontos isolados.
    #
    # CLOSE:
    #     Une regiões próximas que pertencem à mesma alteração.
    # -----------------------------------------------------------------------

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size)
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel,
        iterations=morph_iterations
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=morph_iterations
    )

    # -----------------------------------------------------------------------
    # Encontra os contornos das regiões alteradas
    # -----------------------------------------------------------------------

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        raise ValueError(
            "\nNenhuma região de diferença foi encontrada.\n"
            "Verifique se as imagens realmente representam estados "
            "diferentes da balança ou reduza --thresh."
        )

    # -----------------------------------------------------------------------
    # Filtra contornos muito pequenos
    # -----------------------------------------------------------------------

    valid_boxes = []

    for contour in contours:

        area = cv2.contourArea(contour)

        if area >= min_area:

            x, y, w, h = cv2.boundingRect(contour)

            valid_boxes.append(
                (x, y, w, h)
            )

    if not valid_boxes:

        raise ValueError(
            f"\nNenhum contorno com área >= {min_area}px foi encontrado.\n"
            "Tente reduzir --min-area ou examine mask.png."
        )

    # -----------------------------------------------------------------------
    # Seleção das bounding boxes
    # -----------------------------------------------------------------------

    if merge_boxes:

        # Une todas as regiões válidas em uma única bounding box.

        xs = [
            x
            for x, y, w, h in valid_boxes
        ]

        ys = [
            y
            for x, y, w, h in valid_boxes
        ]

        x2s = [
            x + w
            for x, y, w, h in valid_boxes
        ]

        y2s = [
            y + h
            for x, y, w, h in valid_boxes
        ]

        x = min(xs)
        y = min(ys)

        x2 = max(x2s)
        y2 = max(y2s)

        w = x2 - x
        h = y2 - y

    else:

        # Seleciona somente a maior região.

        x, y, w, h = max(
            valid_boxes,
            key=lambda box: box[2] * box[3]
        )

    # -----------------------------------------------------------------------
    # Padding
    #
    # Adiciona uma pequena margem ao redor da região detectada.
    # -----------------------------------------------------------------------

    img_h, img_w = curr_color.shape[:2]

    x0 = max(
        0,
        x - padding
    )

    y0 = max(
        0,
        y - padding
    )

    x1 = min(
        img_w,
        x + w + padding
    )

    y1 = min(
        img_h,
        y + h + padding
    )

    # -----------------------------------------------------------------------
    # Recorte
    #
    # IMPORTANTE:
    # O recorte é feito na imagem ATUAL COLORIDA.
    # -----------------------------------------------------------------------

    crop_color = curr_color[
        y0:y1,
        x0:x1
    ]

    # -----------------------------------------------------------------------
    # Caminhos dos artefatos
    # -----------------------------------------------------------------------

    diff_path = os.path.join(
        output_dir,
        "diff.png"
    )

    mask_path = os.path.join(
        output_dir,
        "mask.png"
    )

    mask_overlay_path = os.path.join(
        output_dir,
        "mask_overlay.png"
    )

    crop_path = os.path.join(
        output_dir,
        "crop.png"
    )

    overlay_path = os.path.join(
        output_dir,
        "boxes_overlay.png"
    )

    # -----------------------------------------------------------------------
    # Salva diferença
    # -----------------------------------------------------------------------

    cv2.imwrite(
        diff_path,
        diff
    )

    # -----------------------------------------------------------------------
    # Salva máscara
    # -----------------------------------------------------------------------

    cv2.imwrite(
        mask_path,
        mask
    )

    # -----------------------------------------------------------------------
    # Salva somente a região detectada pela máscara
    #
    # Isso ajuda a verificar visualmente o que o OpenCV realmente detectou.
    # -----------------------------------------------------------------------

    mask_overlay = curr_color.copy()

    mask_overlay[
        mask == 0
    ] = 0

    cv2.imwrite(
        mask_overlay_path,
        mask_overlay
    )

    # -----------------------------------------------------------------------
    # Salva recorte colorido
    # -----------------------------------------------------------------------

    cv2.imwrite(
        crop_path,
        crop_color
    )

    # -----------------------------------------------------------------------
    # Desenha bounding box sobre a imagem atual
    # -----------------------------------------------------------------------

    overlay = curr_color.copy()

    cv2.rectangle(
        overlay,
        (x0, y0),
        (x1, y1),
        (0, 255, 0),
        2
    )

    cv2.imwrite(
        overlay_path,
        overlay
    )

    # -----------------------------------------------------------------------
    # Informações
    # -----------------------------------------------------------------------

    print("\n--- Detecção de região alterada (OpenCV) ---")

    print(f"Diff salvo em:          {diff_path}")
    print(f"Máscara salva em:       {mask_path}")
    print(f"Mask overlay salvo em:  {mask_overlay_path}")
    print(f"Recorte salvo em:       {crop_path}")
    print(f"Overlay salvo em:       {overlay_path}")

    print(
        f"\nBounding box:"
        f" x={x0},"
        f" y={y0},"
        f" w={x1 - x0},"
        f" h={y1 - y0}"
    )

    return crop_path, (
        x0,
        y0,
        x1 - x0,
        y1 - y0
    )


def recognize_changed_foods(
    prev_path: str,
    curr_path: str,
    db: Session,
    weight: float | None = None,
    user_id: int | None = None,
):
    crop_path, bbox = find_changed_region(prev_path, curr_path)

    with open(crop_path, "rb") as crop_file:
        crop_bytes = crop_file.read()

    recognition = image_recognition_endpoint(crop_bytes, db, weight=weight, user_id=user_id)

    return {
        "changed": True,
        "first_image": False,
        "items": [
            {
                "bbox": bbox,
                "recognized_food": recognition,
            }
        ],
    }

# ---------------------------------------------------------------------------
# Etapa 2 - SigLIP
# ---------------------------------------------------------------------------

def _normalize_image_bytes(image_data: bytes | str) -> bytes:
    if isinstance(image_data, str):
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        try:
            return base64.b64decode(image_data, validate=True)
        except binascii.Error:
            return image_data.encode("utf-8")

    return image_data


def _get_model():
    global processor, model

    if processor is None or model is None:
        print(f"Using device: {device}")

        # Numero de threads do PyTorch durante a inferencia (opcional).
        num_threads = os.getenv("TORCH_NUM_THREADS")
        if num_threads:
            torch.set_num_threads(int(num_threads))

        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name).to(device)
        model.eval()
        _text_embedding_cache.clear()

    return processor, model


# ---------------------------------------------------------------------------
# Candidatos ao reconhecimento
# ---------------------------------------------------------------------------

def get_recognition_candidates(db: Session, user_id: int | None = None) -> list[dict]:
    """Monta os candidatos do reconhecimento para um usuario.

    - Alimentos globais (Food.user_id NULL) que possuem model_label preenchido.
    - Alimentos criados SOMENTE pelo proprio usuario (Food.user_id == user_id);
      os de outros usuarios nunca entram.

    "source" indica a origem ("food" = global, "created_food" = do usuario);
    "food_id" e sempre o id da tabela Food.
    """
    global_foods = (Food.user_id.is_(None)) & Food.model_label.isnot(None) & (Food.model_label != "")
    condition = or_(global_foods, Food.user_id == user_id) if user_id is not None else global_foods

    foods = (
        db.query(Food)
        .filter(condition)
        .order_by(Food.user_id.is_not(None), Food.id)
        .all()
    )

    return [
        {
            "source": "food" if food.user_id is None else "created_food",
            "food_id": food.id,
            "name": food.name,
            "model_label": build_model_label(food.name, food.model_label),
            "category_id": food.category_id,
            "brand_id": food.brand_id,
        }
        for food in foods
    ]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def _pooled_features(output) -> torch.Tensor:
    # transformers >= 5 devolve BaseModelOutputWithPooling; versoes antigas, o tensor
    return output.pooler_output if hasattr(output, "pooler_output") else output


def _get_text_embeddings(texts: list[str]) -> torch.Tensor:
    """Embeddings normalizados dos prompts, codificando apenas os ainda nao cacheados."""
    missing = [text for text in dict.fromkeys(texts) if text not in _text_embedding_cache]

    if missing:
        processor, model = _get_model()

        inputs = processor(
            text=missing,
            return_tensors="pt",
            padding="max_length"  # o SigLIP foi treinado com max_length
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            features = _pooled_features(model.get_text_features(**inputs))
            features = features / features.norm(p=2, dim=-1, keepdim=True)

        for text, feature in zip(missing, features):
            _text_embedding_cache[text] = feature

    return torch.stack([_text_embedding_cache[text] for text in texts])


def _get_image_embedding(image: Image.Image) -> torch.Tensor:
    processor, model = _get_model()

    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        features = _pooled_features(model.get_image_features(**inputs))
        features = features / features.norm(p=2, dim=-1, keepdim=True)

    return features[0]


def _score_candidates(image: Image.Image, texts: list[str]) -> torch.Tensor:
    """Probabilidade (softmax) de cada prompt; equivale a model(...).logits_per_image."""
    image_embedding = _get_image_embedding(image)
    text_embeddings = _get_text_embeddings(texts)
    _, model = _get_model()

    with torch.no_grad():
        logits = text_embeddings @ image_embedding
        logits = logits * model.logit_scale.exp() + model.logit_bias
        return torch.softmax(logits, dim=-1)


# ---------------------------------------------------------------------------
# Reconhecimento
# ---------------------------------------------------------------------------

def image_recognition_endpoint(
    image_data: bytes | str,
    db: Session,
    top_k: int = 3,
    weight: float | None = None,
    user_id: int | None = None,
):
    image_bytes = _normalize_image_bytes(image_data)

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("Invalid image data. Send a valid JPG, PNG or WEBP image.") from exc

    candidates = get_recognition_candidates(db, user_id)

    if not candidates:
        raise HTTPException(status_code=404, detail="No foods available for recognition.")

    top_k = min(top_k, len(candidates))

    probs = _score_candidates(image, [candidate["model_label"] for candidate in candidates])
    top_probs, top_idx = torch.topk(probs, k=top_k)

    top_confidences = top_probs.detach().cpu().tolist()
    top_indices = top_idx.detach().cpu().tolist()

    predictions = [
        {
            "label": candidates[int(index)]["name"],
            "model_label": candidates[int(index)]["model_label"],
            "source": candidates[int(index)]["source"],
            "food_id": candidates[int(index)]["food_id"],
            "confidence": float(prob)
        }
        for prob, index in zip(top_confidences, top_indices)
    ]

    recognized_food = build_recognized_food(db, candidates[int(top_indices[0])], weight)

    return {
        "model": MODEL_NAME,
        "language": LABEL_LANGUAGE,
        "recognized_food": recognized_food,
        "confidence": predictions[0]["confidence"],
        "predictions": predictions
    }


def build_recognized_food(db: Session, candidate: dict, weight: float | None = None):
    """Monta o alimento reconhecido; com peso, inclui os nutrientes ajustados."""
    recognized_food = {
        "message": "Food found in the database.",
        "source": candidate["source"],
        "food_id": candidate["food_id"],
        "food_name": candidate["name"],
        "category_id": candidate["category_id"],
        "brand_id": candidate["brand_id"],
    }

    if weight is not None:
        nutrient_amounts = get_food_nutrients_by_weight(db, candidate["food_id"], weight)
        recognized_food["nutrients"] = nutrient_amounts["nutrients"]

    return recognized_food

