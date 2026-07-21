---
theme: default
variant: light # optional, defaults to light
paginate: true
size: 16:9
# logo: "assets/brand/hami-logo.png"
title: HAMi Demo
footer: "HAMi · Hardware Affinity Manager for Inference"
pygments_style: ayu-mirage
---

@variant dark
@kicker v2.6 · July 2026

# HAMi

@subtitle Hardware Affinity Manager for Inference

@speaker name="Reza Jelveh" role="Solution Architect, Dynamia AI — Makers of HAMi" github=github.com/fishman twitter=@rezaio email=reza@dynamia.io

<!--
Welcome to the HAMi demo. This deck showcases all slidr features: layouts, grids, cards, tables, quotes, speaker notes, and the new @layout directive.
-->

---

@layout two-col

## GPU Architecture

Standard mode routes application calls through library-level
interception for memory and compute. HAMi intercepts CUDA
API calls transparently -- no container modification required.

- Application calls standard CUDA API
- HAMi intercepts memory allocation
- Compute kernels are intercepted
- GPU sees a single unified workload

@col

```dot
digraph standard_mode {
    rankdir=TB;
    compound=true;
    newrank=true;

    subgraph cluster_main {
        label="Standard Mode";
        penwidth=2;
        fontsize=18;
        fontname="sans-serif";
        margin=8;
        node [width=2.2];

        app [label="Application" shape=box style=filled];
        mem [label="Memory Interception" class="cyan" shape=box style=filled];
        comp [label="Compute Interception" class="cyan" shape=box style=filled];
        gpu [label="Physical GPU" class="green" shape=box style=filled];

        app -> mem -> comp -> gpu;
    }
}
```

@row

```dot
digraph standard_mode {
    rankdir=TB;
    compound=true;
    newrank=true;

    subgraph cluster_main {
        label="Standard Mode";
        penwidth=2;
        fontsize=18;
        fontname="sans-serif";
        margin=8;
        node [width=2.2];

        app [label="Application" shape=box style=filled];
        mem [label="Memory Interception" class="cyan" shape=box style=filled];
        comp [label="Compute Interception" class="cyan" shape=box style=filled];
        gpu [label="Physical GPU" class="green" shape=box style=filled];

        app -> mem -> comp -> gpu;
    }
}
```

---

## Agenda

::: grid {cols=2}
::: card{ tag="green" }
### Architecture

How HAMi schedules GPU workloads across heterogeneous clusters
:::

::: card{ tag="cyan" }
### Deployment

Single-node to multi-cluster scaling patterns
:::

::: card{ tag="yellow" }
### Performance

Benchmarks: throughput, latency, GPU utilization
:::

::: card{ tag="red" }
### Roadmap

Q3 2026 priorities and community contributions
:::
:::

::: card
> HAMi reduces GPU fragmentation by 40% in production inference clusters
:::

---

@layout image-right

## GPU Scheduling Architecture

HAMi intercepts CUDA API calls at the library level to enable fine-grained GPU sharing. The scheduler runs as a Kubernetes device plugin and supports MIG, MPS, and time-slicing for NVIDIA GPUs.

- Device plugin registers GPU resources per node
- HAMi-core intercepts `cuInit`, `cuMemAlloc`, `cuLaunchKernel`
- Scheduler bins workloads by memory footprint and priority
- Fractional GPU allocation down to 1% granularity

![Ecosystem Pyramid](assets/ecosystem/hami-ecosystem-pyramid.png)

<!--
Key point: the library-level interception means zero container modification. Just mount the HAMi lib and set resource limits.
-->

---

@layout image-left

## Performance Benchmarks

![CNCF Logo](assets/brand/cncf-logo.png)

HAMi demonstrates near-linear scaling with concurrent inference workloads across 8× A100 GPUs. The key metric is GPU utilization efficiency -- HAMi achieves 92% average utilization vs. 65% baseline with default Kubernetes scheduling.

- 3.2× throughput improvement on BERT-large inference
- < 2% latency overhead from CUDA interception
- 40% reduction in GPU idle time across the cluster
- Supports mixed-precision (FP16/BF16/INT8) workloads

---

@layout two-col

## Deployment Patterns

**Standalone**: Single binary with embedded etcd, suitable for edge inference
- **Kubernetes Native**: Helm chart with device plugin, custom scheduler, and CRDs
- **Multi-Cluster**: Federation via HAMi-gateway with cross-cluster GPU sharing
- **Air-Gapped**: Offline mode with signed container images and local model registry

@col

**Monitoring**: Prometheus metrics for GPU utilization, memory pressure, scheduling latency
- **Autoscaling**: HPA integration based on GPU queue depth and pending workload count
- **Security**: OPA/Gatekeeper policies for GPU resource quotas and tenant isolation

<!--
The two-col layout auto-splits content after the heading. First half goes left, second half goes right.
-->

---

## Resource Specification

| Resource | Minimum | Recommended | Maximum |
|----------|---------|-------------|---------|
| GPUs per node | 1 | 8 | 16 |
| GPU memory (GB) | 4 | 40 | 80 |
| CPU cores | 2 | 8 | 32 |
| System RAM (GB) | 8 | 64 | 512 |
| Nodes per cluster | 1 | 10 | 100 |
| Concurrent workloads | 1 | 50 | 200 |

> HAMi supports all NVIDIA GPUs from T4 to H100, plus upcoming B200 Blackwell architecture

---

## Community & Ecosystem

::: card{ tag="green" }
### CNCF Sandbox

Accepted Q1 2026. Currently in incubation review with 12 maintainers across 6 organizations.
:::

::: card{ tag="cyan" }
### Integrations

Native support for PyTorch, TensorFlow, vLLM, TGI, Ollama. One-click integration with KServe and Ray Serve.
:::

::: card{ tag="yellow" }
### Contributors

850+ GitHub stars, 120 contributors, monthly community calls, Slack with 2k+ members.
:::

::: card{ tag="red" }
### Enterprise

Production deployments at ByteDance, Alibaba Cloud, Xiaohongshu, and 15+ Fortune 500 companies.
:::

<!--
The grid system auto-detects 2×2 cards and places them in a responsive grid. Cards with tags get colored left borders.
-->

---

@layout compare
@variant dark

## Before & After

::: card {tag=compare}
### Without HAMi

GPU utilization at 65%, idle GPUs
across the cluster, manual bin-packing
required for each workload
:::

::: arrow

{icon:arrow-right cls=accent-primary size=50}
:::

::: card {tag=compare}
### With HAMi

GPU utilization at 92%, automatic
fractional allocation, zero manual
intervention needed
:::

::: notes{ tag="green" }
> HAMi is the only CNCF project that provides hardware-level GPU sharing without requiring vendor-specific drivers or kernel modifications.
:::

---

## Enterprise vs Open Source

| Feature | Open Source | Enterprise |
|---------|------------|------------|
| GPU sharing | ✓ | ✓ |
| Fractional GPU | ✓ | ✓ |
| MIG support | ✓ | ✓ |
| Multi-cluster federation | - | ✓ |
| SSO / RBAC | - | ✓ |
| Audit logging | - | ✓ |
| SLA guarantee | - | ✓ |
| 24/7 support | Community | Dedicated |

---

@hidden

## Architectural Detail

This slide is hidden from output. Use `@hidden` or `@hide` to
exclude slides from the rendered deck while keeping them in the
markdown source for reference or future use.

---

@layout two-col

## Installation

```bash
helm repo add hami https://project-hami.github.io/charts
helm install hami hami/hami \
  --set devicePlugin.version=v2.6.0 \
  --set scheduler.enabled=true
```

@col

Deploy HAMi with a single Helm command. The device plugin registers GPU
resources and the scheduler handles workload placement. Requires Kubernetes
1.24+ and NVIDIA GPU operator.


---

@layout two-col
@variant dark

## Workload Spec

Request GPU resources via standard Kubernetes resource limits. HAMi supports
fractional allocation down to 1% of a GPU and memory limits in MiB. No
container modification required.

@col

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: inference-test
spec:
  containers:
  - name: bert
    image: hami-demo/bert-inference:latest
    resources:
      limits:
        nvidia.com/gpu: 1
        nvidia.com/gpumem: 8000
```

@tiny HAMi v2.6 supports fractional GPU with memory limits in MiB

---

## GPU Utilization Trends

```seaborn
df = pd.DataFrame({
    "Quarter": ["Q1", "Q1", "Q2", "Q2", "Q3", "Q3"],
    "Cluster": ["Baseline", "HAMi", "Baseline", "HAMi", "Baseline", "HAMi"],
    "Utilization": [65, 78, 62, 85, 68, 92],
})
sns.barplot(data=df, x="Quarter", y="Utilization", hue="Cluster")
```

---


@layout two-col

## Scheduling Flow

HAMi routes GPU requests through device plugins, custom scheduling, and
library-level CUDA interception. The hot path (inference) bypasses the
scheduler entirely after initial placement.

@col

```mermaid
graph LR
    User((User)) --> Scheduler[HAMi Scheduler]
    Scheduler --> GPU_A[GPU Node A]
    Scheduler --> GPU_B[GPU Node B]
    GPU_A --> User
    GPU_B --> User
```

---

## Key Metrics

::: card {metric}
10x
Operational cost improvement
:::

::: card {metric}
50%
GPU utilization improvement
:::

::: card {metric}
10x
Workload density per GPU
:::

::: card {metric}
92%
Average GPU utilization
:::

---

## Key Takeaways

::: grid {cols=3}
::: card
### Zero-Downtime

Live migration of GPU workloads between nodes without service interruption
:::

::: card
### Cost Efficiency

Reduce GPU costs by 40-60% through intelligent bin-packing and fractional allocation
:::

::: card
### Open Standard

Apache 2.0 license, vendor-neutral governance, CNCF-hosted project infrastructure
:::

---

## Lucide Icons

`{icon:star}` syntax inline in text {icon:zap cls=accent-primary} paragraphs {icon:heart cls=accent-secondary} and tables.

| Icon | Check |
|------|-------|
| {icon:check cls=accent-primary} | Pass |
| {icon:x cls=accent-secondary} | Fail |
| {icon:triangle-alert cls=accent-contrast} | Warn |

::: grid {cols=3, class="card-grid"}
::: card {tag=green}
### {icon:shield-check cls=accent-primary} Security

End-to-end encrypted by default. SOC 2 Type II certified infrastructure.
:::
::: card {tag=cyan}
### {icon:zap cls=accent-contrast} Performance

Sub-millisecond P99 latency. 99.99% uptime SLA with automatic failover.
:::
::: card {tag=yellow}
### {icon:refresh-cw cls=accent-contrast} Resilience

Multi-region active-active deployment. Zero-downtime rolling updates.
:::
:::

---

## Open Source vs Enterprise

| Feature | Open Source | Enterprise |
|---------|:-----------:|:----------:|
| Core engine | {icon:check cls=accent-primary} | {icon:check cls=accent-primary} |
| Community support | {icon:check cls=accent-primary} | {icon:check cls=accent-primary} |
| SLA guarantees | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |
| SSO / SAML | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |
| Audit logging | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |
| RBAC | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |
| Priority fixes | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |
| Dedicated support | {icon:x cls=accent-secondary} | {icon:check cls=accent-primary} |

---

@kicker Questions

# {icon:message-circle cls=accent-primary} Thank You


@speaker name="Reza Jelveh" role="reza@dynamia.io"
