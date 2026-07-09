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
