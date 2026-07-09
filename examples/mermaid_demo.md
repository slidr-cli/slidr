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
flowchart TD
    Start([Start]) --> Process[Process Data]
    Process --> Decision{Valid?}
    Decision -->|Yes| Success([Success])
    Decision -->|No| Retry([Retry])
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

## Class Diagram

```mermaid
classDiagram
    class User {
        +int id
        +string name
        +string email
        +login()
        +logout()
    }
    class Order {
        +int id
        +int user_id
        +float total
        +submit()
    }
    User --> Order : has many
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
