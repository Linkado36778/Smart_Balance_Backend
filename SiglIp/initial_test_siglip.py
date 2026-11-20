from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch
import sys

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

model_name = "google/siglip-base-patch16-224"

processor = AutoProcessor.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name).to(device)
model.eval()

LABELS = [
    # Grains / starches
    "white rice",
    "brown rice",
    "fried rice",
    "quinoa",
    "couscous",
    "mashed potatoes",
    "french fries",

    # Pasta
    "spaghetti",
    "linguine",
    "fettuccine",
    "penne pasta",
    "macaroni",
    "ramen noodles",

    # Chicken & meats
    "grilled chicken",
    "fried chicken",
    "roasted chicken",
    "turkey breast",
    "pork chop",
    "beef steak",

    # Leafy greens
    "green salad",
    "lettuce",
    "spinach",
    "kale",
    "arugula",

    # Red fruits/vegetables
    "tomato",
    "red apple",
    "red bell pepper",
    "strawberry",
    "cherry tomato",

    # Beans & legumes
    "black beans",
    "kidney beans",
    "pinto beans",
    "lentils",
    "chickpeas",

    # Orange foods
    "carrot",
    "sweet potato",
    "pumpkin",
    "cantaloupe",

    # Dairy
    "mozzarella cheese",
    "cheddar cheese",
    "cottage cheese",
    "yogurt",

    # Eggs
    "scrambled eggs",
    "fried egg",
    "boiled egg",
    "omelet"
]

def identify(image_path):
    image = Image.open(image_path).convert("RGB")

    inputs = processor(
        text=LABELS,
        images=image,
        padding="max_length",
        return_tensors="pt"
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)

        logits = outputs.logits_per_image[0]

        probs = torch.softmax(logits, dim=0)

    print(f"\nImage = {image_path}")

    print("\n--- SigLIP logits ---")
    for i, score in sorted(enumerate(logits), key=lambda x: x[1], reverse=True):
        print(f"{LABELS[i]}: {score.item():.4f}")

    print("\n--- SigLIP softmax ---")
    for i, prob in sorted(enumerate(probs), key=lambda x: x[1], reverse=True):
        print(f"{LABELS[i]}: {prob.item():.2%}")

if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test_image.jpg"
    identify(image_path)