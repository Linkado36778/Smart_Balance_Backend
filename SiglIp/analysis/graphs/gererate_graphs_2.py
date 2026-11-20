"""
Geração de gráficos comparativos CLIP vs SigLIP
Versão aprimorada com visual profissional
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import numpy as np
from pathlib import Path

# ─────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES GLOBAIS
# ─────────────────────────────────────────────────────────────────

RESULTS_DIR = "analysis"
GRAPHS_DIR  = "analysis/graphs"
Path(GRAPHS_DIR).mkdir(parents=True, exist_ok=True)

# Paleta: CLIP=azul, SigLIP=verde; EN=sólido, PT=mais claro
PALETTE = {
    "CLIP EN":    "#2563EB",   # azul forte
    "CLIP PT":    "#93C5FD",   # azul claro
    "SigLIP EN":  "#16A34A",   # verde forte
    "SigLIP PT":  "#86EFAC",   # verde claro
}

plt.rcParams.update({
    "font.family":        "sans-serif",
    "font.size":          11,
    "axes.titlesize":     14,
    "axes.titleweight":   "bold",
    "axes.labelsize":     11,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "grid.color":         "#E5E7EB",
    "grid.linewidth":     0.8,
    "grid.alpha":         0.9,
    "figure.facecolor":   "white",
    "axes.facecolor":     "#FAFAFA",
    "xtick.bottom":       False,
})

# ─────────────────────────────────────────────────────────────────
# CARGA DE DADOS
# ─────────────────────────────────────────────────────────────────

summary    = pd.read_csv(f"{RESULTS_DIR}/summary.csv")
categories = pd.read_csv(f"{RESULTS_DIR}/category_comparison.csv")

summary["Label"] = summary["Modelo"] + " " + summary["Linguagem"]
summary["Color"] = summary["Label"].map(PALETTE)

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def annotate_bars(ax, bars, fmt="{:.0f}%", offset=1.5, fontsize=11):
    """Adiciona rótulo no topo de cada barra."""
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + offset,
            fmt.format(h),
            ha="center", va="bottom",
            fontsize=fontsize, fontweight="bold",
            color="#1F2937",
        )

def legend_patches(keys):
    return [mpatches.Patch(color=PALETTE[k], label=k) for k in keys]

def save(fig, name):
    fig.savefig(f"{GRAPHS_DIR}/{name}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  {name}")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 1 — Top-1 vs Top-3 (barras agrupadas por modelo/idioma)
# ─────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 5.5))

labels   = summary["Label"].tolist()
top1     = summary["Acurácia do TOP 1"].tolist()
top3     = summary["Acurácia do TOP 3"].tolist()
colors   = summary["Color"].tolist()

x     = np.arange(len(labels))
w     = 0.38

b1 = ax.bar(x - w/2, top1, w, color=colors, label="Top-1",
            edgecolor="white", linewidth=0.8, zorder=3)
b3 = ax.bar(x + w/2, top3, w, color=colors, label="Top-3",
            alpha=0.55, edgecolor="white", linewidth=0.8,
            hatch="///", zorder=3)

annotate_bars(ax, b1, offset=1.2, fontsize=10)
annotate_bars(ax, b3, offset=1.2, fontsize=10)

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12)
ax.set_ylabel("Acurácia (%)")
ax.set_ylim(0, 115)
ax.set_title("Acurácia Top-1 e Top-3 por Modelo e Idioma", pad=14)

# legenda manual: modelos (cores) + tipo (padrão)
model_patches = legend_patches(["CLIP EN", "CLIP PT", "SigLIP EN", "SigLIP PT"])
solid  = mpatches.Patch(color="#9CA3AF", label="Top-1 (sólido)")
hatch  = mpatches.Patch(color="#9CA3AF", alpha=0.5, hatch="///", label="Top-3 (hachurado)")
ax.legend(handles=model_patches + [solid, hatch],
          loc="upper center", bbox_to_anchor=(0.5, -0.10),
          ncol=3, framealpha=0.9, fontsize=9.5)

# linha de referência
ax.axhline(y=50, color="#9CA3AF", linestyle="--", linewidth=1, alpha=0.7)
ax.text(3.52, 51.5, "50%", color="#6B7280", fontsize=9)

save(fig, "1_top1_vs_top3.png")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 2 — Impacto da Tradução (EN → PT), ganho/perda
# ─────────────────────────────────────────────────────────────────

def get(modelo, lang, col="Acurácia do TOP 1"):
    return summary[
        (summary["Modelo"] == modelo) &
        (summary["Linguagem"] == lang)
    ][col].iloc[0]

data_impact = {
    "Modelo":  ["CLIP", "SigLIP"],
    "EN":      [get("CLIP","EN"), get("SigLIP","EN")],
    "PT":      [get("CLIP","PT"), get("SigLIP","PT")],
    "Queda":   [get("CLIP","EN") - get("CLIP","PT"),
                get("SigLIP","EN") - get("SigLIP","PT")],
}
di = pd.DataFrame(data_impact)

fig, axes = plt.subplots(1, 2, figsize=(13, 5.5),
                         gridspec_kw={"width_ratios": [1.4, 1]})

# Esquerda: barras EN vs PT lado a lado
ax = axes[0]
xp    = np.arange(len(di))
w     = 0.35
b_en  = ax.bar(xp - w/2, di["EN"], w, color=["#2563EB","#16A34A"],
               label="EN", edgecolor="white", zorder=3)
b_pt  = ax.bar(xp + w/2, di["PT"], w,
               color=["#93C5FD","#86EFAC"],
               label="PT", edgecolor="white", zorder=3)

annotate_bars(ax, b_en, offset=1.2, fontsize=11)
annotate_bars(ax, b_pt, offset=1.2, fontsize=11)

ax.set_xticks(xp)
ax.set_xticklabels(di["Modelo"], fontsize=13)
ax.set_ylabel("Acurácia Top-1 (%)")
ax.set_ylim(0, 115)
ax.set_title("Acurácia EN × PT (Top-1)", pad=12)

clip_p  = [mpatches.Patch(color="#2563EB", label="CLIP EN"),
           mpatches.Patch(color="#93C5FD", label="CLIP PT")]
sig_p   = [mpatches.Patch(color="#16A34A", label="SigLIP EN"),
           mpatches.Patch(color="#86EFAC", label="SigLIP PT")]
ax.legend(handles=clip_p + sig_p, fontsize=9.5, framealpha=0.9)

# Direita: queda em p.p.
ax2 = axes[1]
bar_colors = ["#EF4444" if q > 0 else "#22C55E" for q in di["Queda"]]
bars2 = ax2.bar(di["Modelo"], di["Queda"], color=bar_colors,
                edgecolor="white", width=0.45, zorder=3)

for bar, val in zip(bars2, di["Queda"]):
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        val + 0.8,
        f"−{val:.0f} p.p.",
        ha="center", va="bottom",
        fontsize=13, fontweight="bold",
        color="#1F2937",
    )

ax2.set_ylabel("Queda de Acurácia (p.p.)")
ax2.set_ylim(0, max(di["Queda"]) * 1.35)
ax2.set_title("Impacto da Tradução\n(EN → PT)", pad=12)
ax2.axhline(0, color="#9CA3AF", linewidth=0.8)

fig.suptitle("Efeito do Idioma na Performance dos Modelos",
             fontsize=15, fontweight="bold", y=1.01)
fig.tight_layout()
save(fig, "2_impacto_traducao.png")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 3 — Heatmap por categoria
# ─────────────────────────────────────────────────────────────────

import matplotlib.colors as mcolors

cols = ["CLIP_EN", "CLIP_PT", "SigLIP_EN", "SigLIP_PT"]
col_labels = ["CLIP\nEN", "CLIP\nPT", "SigLIP\nEN", "SigLIP\nPT"]
matrix = categories.set_index("Categoria")[cols].values

fig, ax = plt.subplots(figsize=(9, 7))

cmap = plt.cm.RdYlGn
norm = mcolors.Normalize(vmin=0, vmax=100)
im   = ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

ax.set_xticks(range(len(cols)))
ax.set_xticklabels(col_labels, fontsize=12)
ax.set_yticks(range(len(categories)))
ax.set_yticklabels(categories["Categoria"], fontsize=11)

# células anotadas
for i in range(len(categories)):
    for j in range(len(cols)):
        val = matrix[i, j]
        color = "white" if val < 40 or val > 80 else "#1F2937"
        ax.text(j, i, f"{val:.0f}%",
                ha="center", va="center",
                fontsize=11, fontweight="bold", color=color)

cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cbar.set_label("Acurácia (%)", fontsize=11)
cbar.ax.tick_params(labelsize=10)

ax.set_title("Acurácia Top-1 por Categoria e Configuração",
             pad=14, fontsize=14, fontweight="bold")
ax.tick_params(axis="both", which="both", length=0)

# linhas de separação entre células
for i in range(len(categories) + 1):
    ax.axhline(i - 0.5, color="white", linewidth=1.2)
for j in range(len(cols) + 1):
    ax.axvline(j - 0.5, color="white", linewidth=1.2)

fig.tight_layout()
save(fig, "3_heatmap_categorias.png")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 4 — Barras horizontais por categoria (todos os modelos)
# ─────────────────────────────────────────────────────────────────

cats  = categories["Categoria"].tolist()
n_cat = len(cats)
n_mod = len(cols)
y     = np.arange(n_cat)
h     = 0.18
offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * h
bar_colors = [PALETTE[k] for k in ["CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]]

fig, ax = plt.subplots(figsize=(11, 7))

for idx, (col, color, off, lbl) in enumerate(
        zip(cols, bar_colors, offsets,
            ["CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"])):
    vals = categories[col].values
    bars = ax.barh(y + off, vals, h, color=color,
                   label=lbl, edgecolor="white", zorder=3)
    for bar, v in zip(bars, vals):
        if v > 0:
            ax.text(v + 1, bar.get_y() + bar.get_height()/2,
                    f"{v:.0f}%", va="center", fontsize=8.5,
                    color="#374151")

ax.set_yticks(y)
ax.set_yticklabels(cats, fontsize=11)
ax.set_xlabel("Acurácia Top-1 (%)")
ax.set_xlim(0, 125)
ax.set_title("Comparativo por Categoria de Alimento", pad=14)
ax.legend(handles=legend_patches(["CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]),
          loc="lower right", framealpha=0.9)
ax.axvline(x=60, color="#9CA3AF", linestyle="--", linewidth=1, alpha=0.7)
ax.text(61, n_cat - 0.3, "60%", color="#6B7280", fontsize=9)
ax.invert_yaxis()

fig.tight_layout()
save(fig, "4_barras_categorias.png")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 5 — Radar chart (spider) por modelo/idioma
# ─────────────────────────────────────────────────────────────────

from matplotlib.patches import FancyArrowPatch

angles = np.linspace(0, 2 * np.pi, n_cat, endpoint=False).tolist()
angles += angles[:1]   # fechar o polígono

radar_labels = ["CLIP EN", "CLIP PT", "SigLIP EN", "SigLIP PT"]
radar_data   = {
    "CLIP EN":   (categories["CLIP_EN"].tolist()   + [categories["CLIP_EN"].iloc[0]]),
    "CLIP PT":   (categories["CLIP_PT"].tolist()   + [categories["CLIP_PT"].iloc[0]]),
    "SigLIP EN": (categories["SigLIP_EN"].tolist() + [categories["SigLIP_EN"].iloc[0]]),
    "SigLIP PT": (categories["SigLIP_PT"].tolist() + [categories["SigLIP_PT"].iloc[0]]),
}

fig, ax = plt.subplots(figsize=(8, 8),
                       subplot_kw=dict(polar=True))

for lbl in radar_labels:
    vals = np.array(radar_data[lbl]) / 100   # normaliza 0-1
    ax.plot(angles, vals, color=PALETTE[lbl], linewidth=2.2, label=lbl)
    ax.fill(angles, vals, color=PALETTE[lbl], alpha=0.12)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(cats, size=10)
ax.set_yticks([0.25, 0.50, 0.75, 1.0])
ax.set_yticklabels(["25%","50%","75%","100%"], size=9, color="#6B7280")
ax.set_ylim(0, 1)
ax.set_title("Perfil de Acurácia por Categoria (Radar)",
             pad=20, fontsize=14, fontweight="bold")
ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15),
          framealpha=0.9, fontsize=10)
ax.grid(color="#D1D5DB", linewidth=0.8)

save(fig, "5_radar_categorias.png")


# ─────────────────────────────────────────────────────────────────
# GRÁFICO 6 — Dashboard resumo (painel 2×2)
# ─────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(16, 11), facecolor="white")
fig.suptitle("Dashboard: CLIP vs SigLIP — Avaliação de Reconhecimento de Alimentos",
             fontsize=16, fontweight="bold", y=0.98)

gs = gridspec.GridSpec(2, 2, figure=fig,
                       hspace=0.38, wspace=0.32)

# ── Painel A: Top-1 ──────────────────────────────────────────────
axA = fig.add_subplot(gs[0, 0])
bA  = axA.bar(summary["Label"], summary["Acurácia do TOP 1"],
              color=summary["Color"], edgecolor="white", zorder=3)
annotate_bars(axA, bA, offset=1.5, fontsize=10)
axA.set_ylim(0, 115)
axA.set_title("A  —  Acurácia Top-1")
axA.set_ylabel("Acurácia (%)")
axA.legend(handles=legend_patches(["CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]),
           fontsize=8, framealpha=0.9)

# ── Painel B: Top-1 vs Top-3 linha ───────────────────────────────
axB = fig.add_subplot(gs[0, 1])
for i, row in summary.iterrows():
    axB.plot(["Top-1","Top-3"],
             [row["Acurácia do TOP 1"], row["Acurácia do TOP 3"]],
             marker="o", linewidth=2.2, markersize=8,
             color=PALETTE[row["Label"]], label=row["Label"])
    axB.annotate(f'{row["Acurácia do TOP 1"]:.0f}%',
                 xy=("Top-1", row["Acurácia do TOP 1"]),
                 xytext=(-22, 4), textcoords="offset points",
                 fontsize=9, color=PALETTE[row["Label"]])
    axB.annotate(f'{row["Acurácia do TOP 3"]:.0f}%',
                 xy=("Top-3", row["Acurácia do TOP 3"]),
                 xytext=(5, 4), textcoords="offset points",
                 fontsize=9, color=PALETTE[row["Label"]])

axB.set_ylim(0, 115)
axB.set_title("B  —  Ganho Top-1 → Top-3")
axB.set_ylabel("Acurácia (%)")
axB.legend(fontsize=8.5, framealpha=0.9)

# ── Painel C: Impacto tradução ────────────────────────────────────
axC = fig.add_subplot(gs[1, 0])
quedas = di["Queda"].values
bC = axC.bar(di["Modelo"], quedas,
             color=["#EF4444","#EF4444"], edgecolor="white",
             width=0.42, zorder=3)
for bar, val in zip(bC, quedas):
    axC.text(bar.get_x() + bar.get_width()/2, val + 0.8,
             f"−{val:.0f} p.p.", ha="center", va="bottom",
             fontsize=12, fontweight="bold", color="#1F2937")
axC.set_ylim(0, max(quedas) * 1.45)
axC.set_title("C  —  Queda EN → PT (Top-1)")
axC.set_ylabel("Pontos percentuais")

# ── Painel D: Heatmap compacto ────────────────────────────────────
axD = fig.add_subplot(gs[1, 1])
im  = axD.imshow(matrix, cmap=plt.cm.RdYlGn,
                 norm=mcolors.Normalize(vmin=0, vmax=100),
                 aspect="auto")
axD.set_xticks(range(len(cols)))
axD.set_xticklabels(col_labels, fontsize=9)
axD.set_yticks(range(len(categories)))
axD.set_yticklabels(categories["Categoria"], fontsize=9)
for i in range(len(categories)):
    for j in range(len(cols)):
        val = matrix[i, j]
        c   = "white" if val < 40 or val > 80 else "#1F2937"
        axD.text(j, i, f"{val:.0f}", ha="center", va="center",
                 fontsize=9, fontweight="bold", color=c)
axD.set_title("D  —  Heatmap por Categoria")
axD.tick_params(length=0)
for i in range(len(categories)+1):
    axD.axhline(i-0.5, color="white", linewidth=1)
for j in range(len(cols)+1):
    axD.axvline(j-0.5, color="white", linewidth=1)
fig.colorbar(im, ax=axD, fraction=0.045, pad=0.02).set_label("Acurácia %", fontsize=9)

save(fig, "0_dashboard.png")

print("\nTodos os gráficos gerados em:", GRAPHS_DIR)