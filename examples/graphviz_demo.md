---
title: Graphviz Demo
---

# Graphviz

@kicker Declarative graph rendering with dot

@speaker name="Slidr" role="Text-to-graph rendering"

---

## Architecture

@layout two-col

Graphviz renders directed and undirected
graphs from DOT language descriptions.
Nodes and edges are auto-positioned by
the layout engine.

- Hierarchical layouts
- Cluster subgraphs
- CSS class inheritance
- Theme color variables

@col

```dot
digraph {
    rankdir=TB
    node [shape=box]
    subgraph cluster_main {
        app [label="Application" class="green"]
        mem [label="Memory" class="cyan"]
        comp [label="Compute" class="cyan"]
        gpu [label="GPU" class="green"]
        app -> mem -> comp -> gpu
    }
}
```

---

## Flowchart

@layout two-col

Flowcharts use decision diamonds and
process boxes with directional edges
to show logic flow.

- Box shapes for processes
- Diamond shapes for decisions
- Edge labels for branches

@col

```dot
digraph {
    node [shape=box]
    subgraph cluster_main {
        start [label="Start" class="green"]
        process [label="Process" class="cyan"]
        decision [label="Valid?" shape=diamond class="yellow"]
        done [label="Done" class="green"]
        retry [label="Retry" class="red"]
        start -> process
        process -> decision
        decision -> done [label="Yes"]
        decision -> retry [label="No"]
        retry -> process
    }
}
```

---

## Cluster Diagram

```dot
digraph {
    compound=true
    subgraph cluster_main {
        label="System Architecture"
        style=filled
        node [shape=box]
        subgraph cluster_backend {
            label="Backend Services"
            style=filled
            api [label="API" class="cyan"]
            db [label="Database" shape=cylinder class="green"]
            api -> db
        }
        subgraph cluster_frontend {
            label="Frontend"
            style=filled
            web [label="Web App" class="cyan"]
            mobile [label="Mobile" class="cyan"]
        }
        web -> api
        mobile -> api
    }
}
```

---

## State Machine

@layout two-col

State machines model system behavior
with states and transitions. Each state
is a node with specific styling.

@col

```dot
digraph {
    rankdir=LR
    node [shape=circle width=1.2]
    subgraph {
        idle [label="Idle" class="green"]
        running [label="Running" class="cyan"]
        error [label="Error" class="red"]
        done [label="Done" class="green"]
        idle -> running [label="Start"]
        running -> error [label="Fail"]
        running -> done [label="OK"]
        error -> running [label="Retry"]
        done -> idle [label="Reset"]
    }
}
```
