from transformers import AutoProcessor, AutoModel
import torch
from PIL import Image
from io import BytesIO
import base64
import binascii

from application.models.application_models import Food
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

LABELS = [
    {
        "model_label": "an image of cooked white rice",
        "db_name": "Arroz tipo 1, cozido",
    },
    {
        "model_label": "an image of raw black beans",
        "db_name": "Feijão preto, cru",
    },
    {
        "model_label": "an image of cooked black beans",
        "db_name": "Feijão preto, cozido",
    },
    {
        "model_label": "an image of raw curly lettuce",
        "db_name": "Alface crespa, crua",
    },
    {
        "model_label": "an image of grilled beef liver",
        "db_name": "Fígado bovino, grelhado (bife de fígado)",
    },
    {
        "model_label": "an image of a fried egg",
        "db_name": "Ovo de galinha, frito",
    },
    {
        "model_label": "an image of a Fuji apple with peel",
        "db_name": "Maçã Fuji, com casca, crua",
    },
    {
        "model_label": "an image of a raw banana",
        "db_name": "Banana prata, crua",
    },
    {
        "model_label": "an image of a raw salad tomato",
        "db_name": "Tomate salada, cru",
    },
    {
        "model_label": "an image of french fries",
        "db_name": "Batata inglesa, frita",
    },
    {
        "model_label": "an image of raw whole chicken with skin",
        "db_name": "Frango inteiro, cru, com pele",
    },
    {
        "model_label": "an image of roasted whole chicken with skin",
        "db_name": "Frango inteiro, assado, com pele",
    },
    {
        "model_label": "an image of raw skinless chicken breast",
        "db_name": "Peito de frango, sem pele, cru",
    },
    {
        "model_label": "an image of cooked skinless chicken breast",
        "db_name": "Peito de frango, sem pele, cozido",
    },
    {
        "model_label": "an image of raw chicken breast with skin",
        "db_name": "Peito de frango, com pele, cru",
    },
    {
        "model_label": "an image of roasted chicken breast with skin",
        "db_name": "Peito de frango, com pele, assado",
    },
    {
        "model_label": "an image of raw chicken thigh with skin",
        "db_name": "Coxa de frango, com pele, crua",
    },
    {
        "model_label": "an image of roasted chicken thigh with skin",
        "db_name": "Coxa de frango, com pele, assada",
    },
    {
        "model_label": "an image of raw chicken wing with skin",
        "db_name": "Asa de frango, com pele, crua",
    },
    {
        "model_label": "an image of roasted chicken wing with skin",
        "db_name": "Asa de frango, com pele, assada",
    },
    {
        "model_label": "an image of raw chicken hearts",
        "db_name": "Coração de frango, cru",
    },
    {
        "model_label": "an image of grilled chicken hearts",
        "db_name": "Coração de frango, grelhado",
    },
    {
        "model_label": "an image of raw chicken liver",
        "db_name": "Fígado de frango, cru",
    },
    {
        "model_label": "an image of grilled chicken liver",
        "db_name": "Fígado de frango, grelhado",
    },
    {
        "model_label": "an image of breaded chicken fillet",
        "db_name": "Filé de frango à milanesa",
    },
]

# ----------------------------
# MODEL
# ----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"

model_name = "google/siglip-base-patch16-224"

processor = None
model = None

# Prepare text labels once
texts = [label["model_label"] for label in LABELS]

# ----------------------------
# IMAGE RECOGNITION
# ----------------------------

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
        processor = AutoProcessor.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name).to(device)
        model.eval()

    return processor, model


def image_recognition_endpoint(image_data: bytes | str, db: Session, top_k: int = 3):
    image_bytes = _normalize_image_bytes(image_data)
    top_k = min(top_k, len(LABELS))

    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("Invalid image data. Send a valid JPG, PNG or WEBP image.") from exc

    processor, model = _get_model()

    inputs = processor(
        text=texts,
        images=image,
        return_tensors="pt",
        padding="max_length"
    )

    inputs = {
        k: v.to(device)
        for k, v in inputs.items()
    }

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits_per_image[0]
        probs = torch.softmax(logits, dim=-1)
        top_probs, top_idx = torch.topk(probs, k=top_k)

    top_confidences = top_probs.detach().cpu().tolist()
    top_indices = top_idx.detach().cpu().tolist()

    predictions = [
        {
            "label": LABELS[int(index)]["db_name"],
            "model_label": LABELS[int(index)]["model_label"],
            "confidence": float(prob)
        }
        for prob, index in zip(top_confidences, top_indices)
    ]

    recognized_food = recognize_food_from_database(db, predictions[0]["label"])

    return {
        "model": MODEL_NAME,
        "language": LABEL_LANGUAGE,
        "recognized_food": recognized_food,
        "confidence": predictions[0]["confidence"],
        "predictions": predictions
    }

def recognize_food_from_database(db: Session, prediction: str):
    db_search = db.query(Food).filter(Food.name == prediction).first()

    if not db_search:
        raise HTTPException(status_code=404, detail="Food not found in the database.")
    else:
        return {
            "message": "Food found in the database.",
            "food_id": db_search.id,
            "food_name": db_search.name,
            "category_id": db_search.category_id,
            "brand_id": db_search.brand_id
        }
