"""
Converte os CSVs de resultado em tabelas estilizadas (PNG).
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from pathlib import Path

RESULTS_DIR = "analysis"
TABLES_DIR  = "analysis/tables"
Path(TABLES_DIR).mkdir(parents=True, exist_ok=True)

COLOR_HEADER  = "#1E3A5F"
COLOR_HEADER_TXT = "white"
COLOR_ROW_ODD  = "#F0F4FA"
COLOR_ROW_EVEN = "white"
COLOR_BORDER   = "#CBD5E1"

def save(fig, name):
    fig.savefig(f"{TABLES_DIR}/{name}", dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓  {name}")


def draw_table(ax, df, col_widths=None, title=None,
               heatmap_cols=None, fmt_cols=None):
    """
    Desenha uma tabela estilizada no Axes `ax`.

    Parâmetros
    ----------
    df          : DataFrame já preparado para exibição
    col_widths  : lista de larguras relativas (soma = 1); None = automático
    title       : texto do título acima da tabela
    heatmap_cols: lista de nomes de colunas que recebem fundo colorido por valor
    fmt_cols    : dict {col: format_str} para formatar valores, ex. {"Top-1": "{:.0f}%"}
    """
    ax.axis("off")

    n_rows, n_cols = df.shape

    if col_widths is None:
        col_widths = [1 / n_cols] * n_cols

    x_positions = np.cumsum([0] + col_widths[:-1])
    row_height  = 1 / (n_rows + 1)   # +1 para o cabeçalho

    for j, (col, x, w) in enumerate(zip(df.columns, x_positions, col_widths)):
        ax.add_patch(plt.Rectangle(
            (x, 1 - row_height), w, row_height,
            color=COLOR_HEADER, transform=ax.transAxes, clip_on=False
        ))
        ax.text(
            x + w / 2, 1 - row_height / 2, col,
            ha="center", va="center", fontsize=10,
            fontweight="bold", color=COLOR_HEADER_TXT,
            transform=ax.transAxes
        )

    heatmap_cols = heatmap_cols or []
    fmt_cols     = fmt_cols or {}

    heat_norm = {}
    for hc in heatmap_cols:
        vals = pd.to_numeric(df[hc], errors="coerce").dropna()
        heat_norm[hc] = mcolors.Normalize(vmin=vals.min(), vmax=vals.max())

    for i, (_, row) in enumerate(df.iterrows()):
        y_top = 1 - row_height * (i + 2)
        bg    = COLOR_ROW_ODD if i % 2 == 0 else COLOR_ROW_EVEN

        for j, (col, x, w) in enumerate(zip(df.columns, x_positions, col_widths)):
            cell_val = row[col]

            if col in heatmap_cols:
                num = pd.to_numeric(cell_val, errors="coerce")
                cell_color = plt.cm.RdYlGn(heat_norm[col](num)) if not np.isnan(num) else bg
            else:
                cell_color = bg

            ax.add_patch(plt.Rectangle(
                (x, y_top), w, row_height,
                color=cell_color, transform=ax.transAxes, clip_on=False
            ))

            txt = fmt_cols.get(col, "{}").format(cell_val) if col in fmt_cols else str(cell_val)
            if col in heatmap_cols:
                num = pd.to_numeric(cell_val, errors="coerce")
                if not np.isnan(num):
                    rgba = plt.cm.RdYlGn(heat_norm[col](num))
                    luminance = 0.299*rgba[0] + 0.587*rgba[1] + 0.114*rgba[2]
                    txt_color = "white" if luminance < 0.45 else "#1F2937"
                else:
                    txt_color = "#1F2937"
            else:
                txt_color = "#1F2937"

            ax.text(
                x + w / 2, y_top + row_height / 2, txt,
                ha="center", va="center", fontsize=10,
                color=txt_color, transform=ax.transAxes
            )

        ax.plot([0, 1], [y_top, y_top],
                color=COLOR_BORDER, linewidth=0.5,
                transform=ax.transAxes, clip_on=False)

    for spine in ["top","bottom","left","right"]:
        ax.spines[spine].set_visible(False)
    ax.add_patch(plt.Rectangle(
        (0, 1 - row_height * (n_rows + 1)), 1,
        row_height * (n_rows + 1),
        fill=False, edgecolor=COLOR_BORDER, linewidth=1.2,
        transform=ax.transAxes, clip_on=False
    ))

    y_bottom = 1 - row_height * (n_rows + 1)
    for x in x_positions[1:]:
        ax.plot([x, x], [y_bottom, 1],
                color=COLOR_BORDER, linewidth=0.5,
                transform=ax.transAxes, clip_on=False)

    if title:
        ax.set_title(title, fontsize=13, fontweight="bold",
                     color="#1E3A5F", pad=12)


# ─────────────────────────────────────────────────────────────────
# TABELA 1 — Resumo geral
# ─────────────────────────────────────────────────────────────────

summary = pd.read_csv(f"{RESULTS_DIR}/summary.csv")

df1 = summary[["Modelo","Linguagem","Acurácia do TOP 1","Acurácia do TOP 3","Amostras"]].copy()
df1["Acurácia do TOP 1"] = df1["Acurácia do TOP 1"].map("{:.0f}%".format)
df1["Acurácia do TOP 3"] = df1["Acurácia do TOP 3"].map("{:.0f}%".format)
df1.columns = ["Modelo","Idioma","Top-1","Top-3","Amostras"]

fig, ax = plt.subplots(figsize=(8, 2.6))
draw_table(ax, df1,
           col_widths=[0.18, 0.14, 0.22, 0.22, 0.24],
           title="Resumo Geral — Acurácia dos Modelos")
fig.tight_layout()
save(fig, "tabela_resumo.png")


# ─────────────────────────────────────────────────────────────────
# TABELA 2 — Acurácia por categoria (com heatmap nas colunas numéricas)
# ─────────────────────────────────────────────────────────────────

categories = pd.read_csv(f"{RESULTS_DIR}/category_comparison.csv")

df2 = categories.copy()
for col in ["CLIP_EN","CLIP_PT","SigLIP_EN","SigLIP_PT"]:
    df2[col] = df2[col].map("{:.0f}%".format)

df2.columns = ["Categoria","CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]

df2_heat = categories.copy()
df2_heat.columns = ["Categoria","CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]

fig, ax = plt.subplots(figsize=(9, 4.8))

n_rows, n_cols = df2.shape
col_widths = [0.28, 0.18, 0.18, 0.18, 0.18]
x_positions = np.cumsum([0] + col_widths[:-1])
row_height  = 1 / (n_rows + 1)
heatmap_cols = ["CLIP EN","CLIP PT","SigLIP EN","SigLIP PT"]

heat_norm = {}
for hc in heatmap_cols:
    vals = df2_heat[hc]
    heat_norm[hc] = mcolors.Normalize(vmin=0, vmax=100)

ax.axis("off")

for j, (col, x, w) in enumerate(zip(df2.columns, x_positions, col_widths)):
    ax.add_patch(plt.Rectangle(
        (x, 1 - row_height), w, row_height,
        color=COLOR_HEADER, transform=ax.transAxes, clip_on=False
    ))
    ax.text(x + w/2, 1 - row_height/2, col,
            ha="center", va="center", fontsize=10,
            fontweight="bold", color=COLOR_HEADER_TXT,
            transform=ax.transAxes)

for i, (_, row_disp) in enumerate(df2.iterrows()):
    row_num = df2_heat.iloc[i]
    y_top = 1 - row_height * (i + 2)

    for j, (col, x, w) in enumerate(zip(df2.columns, x_positions, col_widths)):
        if col in heatmap_cols:
            num = row_num[col]
            cell_color = plt.cm.RdYlGn(heat_norm[col](num))
            rgba = cell_color
            luminance = 0.299*rgba[0] + 0.587*rgba[1] + 0.114*rgba[2]
            txt_color = "white" if luminance < 0.45 else "#1F2937"
        else:
            cell_color = COLOR_ROW_ODD if i % 2 == 0 else COLOR_ROW_EVEN
            txt_color  = "#1F2937"

        ax.add_patch(plt.Rectangle(
            (x, y_top), w, row_height,
            color=cell_color, transform=ax.transAxes, clip_on=False
        ))
        ax.text(x + w/2, y_top + row_height/2, str(row_disp[col]),
                ha="center", va="center", fontsize=10,
                color=txt_color, fontweight="bold" if col in heatmap_cols else "normal",
                transform=ax.transAxes)

    ax.plot([0, 1], [y_top, y_top],
            color=COLOR_BORDER, linewidth=0.5,
            transform=ax.transAxes, clip_on=False)

ax.add_patch(plt.Rectangle(
    (0, 1 - row_height*(n_rows+1)), 1, row_height*(n_rows+1),
    fill=False, edgecolor=COLOR_BORDER, linewidth=1.2,
    transform=ax.transAxes, clip_on=False
))
y_bottom = 1 - row_height * (n_rows + 1)
for x in x_positions[1:]:
    ax.plot([x, x], [y_bottom, 1],
            color=COLOR_BORDER, linewidth=0.5,
            transform=ax.transAxes, clip_on=False)

ax.set_title("Acurácia Top-1 por Categoria e Linguagem",
             fontsize=13, fontweight="bold", color="#1E3A5F", pad=12)

fig.tight_layout()
save(fig, "tabela_categorias.png")


print(f"\nTabelas salvas em: {TABLES_DIR}")