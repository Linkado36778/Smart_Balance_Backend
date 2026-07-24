from transformers import AutoProcessor, AutoModel
import torch
import pandas as pd
from PIL import Image
from pathlib import Path

# ----------------------------
# CONFIG
# ----------------------------

DATASET_DIR = "images"
OUTPUT_CSV = "test02_siglip_results.csv"

MODEL_NAME = "SigLIP"
LABEL_LANGUAGE = "PT"

GROUND_TRUTH_PT = {
    "white_rice": "arroz branco",
    "brown_rice": "arroz integral",
    "fried_rice": "arroz frito",
    "quinoa": "quinoa",
    "couscous": "cuscuz",
    "mashed_potatoes": "purê de batatas",
    "french_fries": "batata frita",

    "spaghetti": "espaguete",
    "linguine": "linguine",
    "fettuccine": "fettuccine",
    "penne_pasta": "massa penne",
    "macaroni": "macarrão",
    "ramen_noodles": "lámen",

    "grilled_chicken": "frango grelhado",
    "fried_chicken": "frango frito",
    "roasted_chicken": "frango assado",
    "turkey_breast": "peito de peru",
    "pork_chop": "costeleta de porco",
    "beef_steak": "bife bovino",

    "green_salad": "salada verde",
    "lettuce": "alface",
    "spinach": "espinafre",
    "kale": "couve kale",
    "arugula": "rúcula",

    "tomato": "tomate",
    "red_apple": "maçã vermelha",
    "red_bell_pepper": "pimentão vermelho",
    "strawberry": "morango",
    "cherry_tomato": "tomate cereja",

    "black_beans": "feijão preto",
    "kidney_beans": "feijão vermelho",
    "pinto_beans": "feijão carioca",
    "lentils": "lentilhas",
    "chickpeas": "grão-de-bico",

    "carrot": "cenoura",
    "sweet_potato": "batata-doce",
    "pumpkin": "abóbora",
    "cantaloupe": "melão cantalupo",

    "mozzarella_cheese": "queijo muçarela",
    "cheddar_cheese": "queijo cheddar",
    "cottage_cheese": "queijo cottage",
    "yogurt": "iogurte",

    "scrambled_eggs": "ovos mexidos",
    "fried_egg": "ovo frito",
    "boiled_egg": "ovo cozido",
    "omelet": "omelete"
}

LABELS = list(GROUND_TRUTH_PT.values())

VALID_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

# ----------------------------
# MODEL
# ----------------------------

device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Using device: {device}")

model_name = "google/siglip-base-patch16-224"

processor = AutoProcessor.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name).to(device)

model.eval()

texts = [f"uma imagem de {label}" for label in LABELS]

# ----------------------------
# TEST LOOP
# ----------------------------

results = []

for image_path in Path(DATASET_DIR).rglob("*"):

    if image_path.suffix.lower() not in VALID_EXTENSIONS:
        continue

    try:

        image = Image.open(image_path).convert("RGB")

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

            probs = torch.softmax(
                logits,
                dim=-1
            )

            top3_probs, top3_idx = torch.topk(
                probs,
                k=3
            )

        ground_truth_folder = image_path.parent.name

        ground_truth = GROUND_TRUTH_PT.get(
            ground_truth_folder,
            ground_truth_folder.replace("_", " ")
        )

        top1 = LABELS[top3_idx[0].item()]
        top2 = LABELS[top3_idx[1].item()]
        top3 = LABELS[top3_idx[2].item()]

        results.append({
            "image": image_path.name,
            "ground_truth": ground_truth,

            "model": MODEL_NAME,
            "language": LABEL_LANGUAGE,

            "top1": top1,
            "top1_conf": float(top3_probs[0]),

            "top2": top2,
            "top2_conf": float(top3_probs[1]),

            "top3": top3,
            "top3_conf": float(top3_probs[2]),

            "correct": ground_truth == top1
        })

        print(f"{image_path.name} -> {top1}")

    except Exception as e:

        print(f"Failed: {image_path}")
        print(e)

# ----------------------------
# SAVE CSV
# ----------------------------

df = pd.DataFrame(results)

df.to_csv(
    OUTPUT_CSV,
    index=False
)

accuracy = (
    df["correct"].mean() * 100
)

print("\nResults saved:", OUTPUT_CSV)
print(f"Top-1 Accuracy: {accuracy:.2f}%")