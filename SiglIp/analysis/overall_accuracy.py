import pandas as pd
from pathlib import Path

RESULTS_DIR = "results"

summary = []

for csv_file in Path(RESULTS_DIR).glob("*.csv"):

    # ignora o próprio arquivo de saída
    if csv_file.name == "summary.csv":
        continue

    df = pd.read_csv(csv_file)

    print(f"\n{csv_file.name}")

    # normaliza labels para comparação
    ground_truth = (
        df["ground_truth"]
        .astype(str)
        .str.replace("_", " ", regex=False)
        .str.strip()
    )

    top1 = (
        df["top1"]
        .astype(str)
        .str.strip()
    )

    top2 = (
        df["top2"]
        .astype(str)
        .str.strip()
    )

    top3 = (
        df["top3"]
        .astype(str)
        .str.strip()
    )

    # Top-3 correto
    top3_correct = (
        (ground_truth == top1) |
        (ground_truth == top2) |
        (ground_truth == top3)
    )

    top1_accuracy = df["correct"].mean() * 100
    top3_accuracy = top3_correct.mean() * 100

    print(f"Top-1: {top1_accuracy:.2f}%")
    print(f"Top-3: {top3_accuracy:.2f}%")

    print(
        df[
            ["ground_truth", "top1", "top2", "top3"]
        ].head()
    )

    model = df["model"].iloc[0]

    # compatibilidade com CSVs antigos
    if "language" in df.columns:
        language = df["language"].iloc[0]
    elif "label_language" in df.columns:
        language = df["label_language"].iloc[0]
    else:
        language = "N/A"

    summary.append({
        "file": csv_file.name,
        "Modelo": model,
        "Linguagem": language,
        "Acurácia do TOP 1": round(top1_accuracy, 2),
        "Acurácia do TOP 3": round(top3_accuracy, 2),
        "Amostras": len(df)
    })

summary_df = pd.DataFrame(summary)

print("\nResumo:")
print(summary_df)

summary_df.to_csv(
    "results/summary.csv",
    index=False
)

print("\nArquivo salvo em results/summary.csv")