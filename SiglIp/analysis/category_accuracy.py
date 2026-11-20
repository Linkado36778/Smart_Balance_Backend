import pandas as pd
from pathlib import Path

RESULTS_DIR = "results"

CATEGORY_MAP = {
    "white_rice": "Arroz branco",
    "white rice": "Arroz branco",
    "arroz branco": "Arroz branco",

    "black_beans": "Feijão preto",
    "black beans": "Feijão preto",
    "feijão preto": "Feijão preto",

    "french_fries": "Batata frita",
    "french fries": "Batata frita",
    "batata frita": "Batata frita",

    "beef_steak": "Bife bovino",
    "beef steak": "Bife bovino",
    "bife bovino": "Bife bovino",

    "grilled_chicken": "Frango grelhado",
    "grilled chicken": "Frango grelhado",
    "frango grelhado": "Frango grelhado",

    "spinach": "Espinafre",
    "espinafre": "Espinafre",

    "ramen_noodles": "Lámen",
    "ramen noodles": "Lámen",
    "lámen": "Lámen",

    "mashed_potatoes": "Purê de batatas",
    "mashed potatoes": "Purê de batatas",
    "purê de batatas": "Purê de batatas",

    "scrambled_eggs": "Ovos mexidos",
    "scrambled eggs": "Ovos mexidos",
    "ovos mexidos": "Ovos mexidos",

    "cherry_tomato": "Tomate cereja",
    "cherry tomato": "Tomate cereja",
    "tomate cereja": "Tomate cereja"
}

all_data = []

for csv_file in Path(RESULTS_DIR).glob("*.csv"):

    if csv_file.name in [
        "summary.csv",
        "category_comparison.csv"
    ]:
        continue

    df = pd.read_csv(csv_file)

    model = df["model"].iloc[0]

    if "language" in df.columns:
        language = df["language"].iloc[0]
    else:
        language = df["label_language"].iloc[0]

    df["ground_truth"] = (
        df["ground_truth"]
        .astype(str)
        .str.strip()
        .map(CATEGORY_MAP)
        .fillna(df["ground_truth"])
    )

    category_acc = (
        df.groupby("ground_truth")["correct"]
        .mean()
        .mul(100)
        .reset_index()
    )

    category_acc["Modelo"] = model
    category_acc["Idioma"] = language

    all_data.append(category_acc)

final_df = pd.concat(all_data)

pivot = final_df.pivot_table(
    index="ground_truth",
    columns=["Modelo", "Idioma"],
    values="correct"
)

pivot = pivot.round(2)

pivot.columns = [
    f"{modelo}_{idioma}"
    for modelo, idioma in pivot.columns
]

pivot = pivot.reset_index()

pivot = pivot.rename(
    columns={
        "ground_truth": "Categoria"
    }
)

print("\nComparação por categoria:\n")
print(pivot)

pivot.to_csv(
    "results/category_comparison.csv",
    index=False
)

print(
    "\nArquivo salvo em: results/category_comparison.csv"
)