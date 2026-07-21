---
title: Seaborn Demo
---

# Seaborn

@kicker Data visualization with Python

@speaker name="Slidr" role="Code-to-image rendering"

---

## Scatter Plot

```seaborn
tips = sns.load_dataset("tips")
sns.scatterplot(data=tips, x="total_bill", y="tip", hue="day")
```

---

## Bar Plot

```seaborn
penguins = sns.load_dataset("penguins")
sns.barplot(data=penguins, x="species", y="body_mass_g", hue="sex")
```

---

## Memory Oversubscription

```seaborn
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

fig, ax = plt.subplots(figsize=(8, 2.8))

card_color = plt.rcParams["axes.facecolor"]
fg = plt.rcParams["text.color"]
dimmed = plt.rcParams["xtick.color"]
cmap = plt.get_cmap("Paired")
danger = cmap(4.5 / 12)     # muted red
danger_bright = cmap(5 / 12)  # bright red for labels
elastic = cmap(2.5 / 12)   # green
base = cmap(0.5 / 12)      # light blue
ax.set_facecolor("none")
fig.patch.set_facecolor(card_color)

ax.barh(1, 8, color=base, height=0.65)
ax.barh(1, 3, left=8, color=danger, height=0.65)
ax.plot([10, 10], [0.62, 1.38], color=danger, linewidth=2.5, solid_capstyle="butt")

ax.barh(0, 8, color=base, height=0.65)
ax.barh(0, 7, left=8, color=elastic, height=0.65)
ax.plot([10, 10], [-0.38, 0.38], color=fg, linewidth=1.5, linestyle="--")
ax.plot([15, 15], [-0.38, 0.38], color=fg, linewidth=1.5, linestyle="--")

ax.set_xlim(0, 15.2)
ax.spines[["top", "right", "left", "bottom"]].set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

# Bar labels beside bars
ax.text(-0.3, 1, "Without HAMi", ha="right", va="center", fontsize=10, color=fg, fontweight="bold")
ax.text(-0.3, 0, "With HAMi:\nElastic Scaling", ha="right", va="center", fontsize=10, color=fg, fontweight="bold")

# Bar 1 annotations
ax.text(4, 1, "Normal base load", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")
ax.text(9.5, 1, "Traffic spike", ha="center", va="center", fontsize=7.5, color=dimmed, fontweight="bold")
ax.text(10, 1.42, "10 GB limit", ha="center", va="bottom", fontsize=8, color=danger_bright, fontweight="bold")

# Bar 2 annotations
ax.text(4, 0, "Normal base load", ha="center", va="center", fontsize=9, color=fg, fontweight="bold")
ax.text(11.5, 0, "Traffic spike", ha="center", va="center", fontsize=7.5, color=dimmed, fontweight="bold")
ax.text(10, 0.38, "10 GB\nsoft limit", ha="center", va="bottom", fontsize=7.5, color=dimmed)
ax.text(15, 0.38, "15 GB\nburst", ha="center", va="bottom", fontsize=7.5, color=dimmed)

# Legend
legend_patches = [
    mpatches.Patch(color=base, label="Base load"),
    mpatches.Patch(color=danger, label="Traffic spike (OOM risk)"),
    mpatches.Patch(color=elastic, label="Traffic spike (elastic)"),
]
ax.legend(handles=legend_patches, loc="upper center", bbox_to_anchor=(0.5, 0.07), fontsize=8, ncol=3, framealpha=0.8)
```

---

## Heatmap

```seaborn
flights = sns.load_dataset("flights")
flights_pivot = flights.pivot(index="month", columns="year", values="passengers")
sns.heatmap(flights_pivot, annot=True, fmt="d", cmap="YlOrRd")
```

---

## Distribution

@layout two-col

```seaborn
iris = sns.load_dataset("iris")
sns.boxplot(data=iris, x="species", y="sepal_length")
```

@col

- Seaborn builds on matplotlib
- Tight integration with pandas DataFrames
- Statistical visualizations out of the box
- Auto-generated from fenced code blocks
