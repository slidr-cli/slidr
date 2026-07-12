---
theme: default
---

# {icon:zap cls=accent-primary} Lucide Icons Demo

@kicker Inline & everywhere

---

## Basic Syntax

`{icon:star}` renders inline {icon:star cls=accent-primary} in any text.

Parameters: `cls`, `stroke`, `fill`, `width`, `height`, `size`.

---

## Sizes

{icon:star size=16} small
{icon:star size=32} medium
{icon:star size=64} large

`size` sets both `width` and `height`.

---

## Colors via Classes

{icon:check cls=accent-primary} accent-primary
{icon:x cls=accent-secondary} accent-secondary
{icon:triangle-alert cls=accent-contrast} accent-contrast

---

## In Tables

| Feature | Status |
|---------|--------|
| Tests passing | {icon:check cls=accent-primary} |
| CI green | {icon:check cls=accent-primary} |
| Docs updated | {icon:x cls=accent-secondary} |
| Review pending | {icon:clock cls=accent-contrast} |

---

## In Card Headers

::: grid {cols=3, class="card-grid"}
::: card {tag=green}
### {icon:shield-check cls=accent-primary} Security

End-to-end encrypted, SOC 2 certified.
:::
::: card {tag=cyan}
### {icon:zap cls=accent-contrast} Performance

Sub-millisecond latency, 99.99% uptime.
:::
::: card {tag=yellow}
### {icon:refresh-cw cls=accent-contrast} Resilience

Multi-region active-active, zero downtime.
:::
:::

---

## In Arrows (Compare Layout)

@layout compare

## Before & After

::: card {tag=compare}
### {icon:shield-off cls=accent-secondary} Before

Manual process, error-prone, slow.
:::

::: arrow

{icon:arrow-right cls=accent-primary size=48}
:::

::: card {tag=compare}
### {icon:shield-check cls=accent-primary} After

Automated, validated, fast.
:::

---

@kicker Questions

# {icon:message-circle cls=accent-primary} Thank You
