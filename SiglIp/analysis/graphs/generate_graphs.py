import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

RESULTS_DIR = "analysis"
GRAPHS_DIR = "analysis/graphs"

Path(GRAPHS_DIR).mkdir(exist_ok=True)

# =====================================================
# LOAD FILES
# =====================================================

summary = pd.read_csv(
    f"{RESULTS_DIR}/summary.csv"
)

categories = pd.read_csv(
    f"{RESULTS_DIR}/category_comparison.csv"
)

# =====================================================
# GRAPH 1 - TOP 1 ACCURACY
# =====================================================

plt.figure(figsize=(8,5))

labels = (
    summary["Modelo"]
    + " "
    + summary["Linguagem"]
)

plt.bar(
    labels,
    summary["Acurácia do TOP 1"]
)

plt.title("Acurácia Top-1")
plt.ylabel("Acurácia (%)")
plt.ylim(0, 100)

for i, value in enumerate(summary["Acurácia do TOP 1"]):
    plt.text(
        i,
        value + 1,
        f"{value:.0f}%",
        ha="center"
    )

plt.tight_layout()

plt.savefig(
    f"{GRAPHS_DIR}/accuracy_top1.png",
    dpi=300
)

plt.close()

# =====================================================
# GRAPH 2 - TOP 3 ACCURACY
# =====================================================

plt.figure(figsize=(8,5))

plt.bar(
    labels,
    summary["Acurácia do TOP 3"]
)

plt.title("Acurácia Top-3")
plt.ylabel("Acurácia (%)")
plt.ylim(0, 100)

for i, value in enumerate(summary["Acurácia do TOP 3"]):
    plt.text(
        i,
        value + 1,
        f"{value:.0f}%",
        ha="center"
    )

plt.tight_layout()

plt.savefig(
    f"{GRAPHS_DIR}/accuracy_top3.png",
    dpi=300
)

plt.close()

# =====================================================
# GRAPH 3 - TRANSLATION IMPACT
# =====================================================

clip_en = summary[
    (summary["Modelo"] == "CLIP")
    & (summary["Linguagem"] == "EN")
]["Acurácia do TOP 1"].iloc[0]

clip_pt = summary[
    (summary["Modelo"] == "CLIP")
    & (summary["Linguagem"] == "PT")
]["Acurácia do TOP 1"].iloc[0]

siglip_en = summary[
    (summary["Modelo"] == "SigLIP")
    & (summary["Linguagem"] == "EN")
]["Acurácia do TOP 1"].iloc[0]

siglip_pt = summary[
    (summary["Modelo"] == "SigLIP")
    & (summary["Linguagem"] == "PT")
]["Acurácia do TOP 1"].iloc[0]

translation_drop = [
    clip_en - clip_pt,
    siglip_en - siglip_pt
]

plt.figure(figsize=(6,5))

plt.bar(
    ["CLIP", "SigLIP"],
    translation_drop
)

plt.title("Impacto da Tradução (EN → PT)")
plt.ylabel("Queda de Acurácia (p.p.)")

for i, value in enumerate(translation_drop):
    plt.text(
        i,
        value + 1,
        f"{value:.0f}"
    )

plt.tight_layout()

plt.savefig(
    f"{GRAPHS_DIR}/translation_impact.png",
    dpi=300
)

plt.close()

# =====================================================
# GRAPH 4 - CATEGORY COMPARISON
# =====================================================

fig, ax = plt.subplots(
    figsize=(14,7)
)

x = range(len(categories))

width = 0.2

ax.bar(
    [i - 1.5*width for i in x],
    categories["CLIP_EN"],
    width,
    label="CLIP EN"
)

ax.bar(
    [i - 0.5*width for i in x],
    categories["CLIP_PT"],
    width,
    label="CLIP PT"
)

ax.bar(
    [i + 0.5*width for i in x],
    categories["SigLIP_EN"],
    width,
    label="SigLIP EN"
)

ax.bar(
    [i + 1.5*width for i in x],
    categories["SigLIP_PT"],
    width,
    label="SigLIP PT"
)

ax.set_xticks(list(x))
ax.set_xticklabels(
    categories["Categoria"],
    rotation=45,
    ha="right"
)

ax.set_ylabel("Acurácia (%)")
ax.set_title("Acurácia por Categoria")
ax.legend()

plt.tight_layout()

plt.savefig(
    f"{GRAPHS_DIR}/category_accuracy.png",
    dpi=300
)

plt.close()

print("Gráficos gerados com sucesso!")
print(f"Pasta: {GRAPHS_DIR}")