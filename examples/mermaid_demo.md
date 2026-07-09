---
title: Mermaid Demo
---

# Mermaid

@kicker Declarative diagramming from text

@speaker name="Slidr" role="Text-to-diagram rendering"

---

## Architecture

```mermaid
graph LR
    User((User)) --> API[API Gateway]
    API --> DB[(Database)]
    API --> Cache[(Redis)]
    API --> User
```

---

## Flowchart

```mermaid
graph TD
    Start[Start] --> Process[Process Data]
    Process --> Decision{Valid?}
    Decision -->|Yes| Success[Success]
    Decision -->|No| Retry[Retry]
    Retry --> Process
```

---

## Sequence

```mermaid
sequenceDiagram
    Client->>Server: POST /login
    Server->>Database: SELECT user
    Database->>Server: user row
    Server->>Client: JWT token
    Client->>Server: GET /data
    Server->>Database: SELECT *
    Database->>Server: result set
    Server->>Client: JSON response
```

---

## Entity Relationship

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    USER {
        int id
        string name
        string email
    }
    ORDER {
        int id
        float total
    }
```

---

## Grid Layout

@layout two-col

```mermaid
graph LR
    AWS --> GCP
    GCP --> Azure
```

@col

```mermaid
graph LR
    Client --> LB[Load Balancer]
    LB --> App1
    LB --> App2
```
