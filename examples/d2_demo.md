---
title: D2 Demo
---

# D2

@kicker Declarative diagramming from text

@speaker name="Slidr" role="Text-to-diagram rendering"

---

## Architecture

```d2
direction: right

user: User {
  shape: person
}

api: API Gateway

db: Database {
  shape: cylinder
}

cache: Redis {
  shape: cylinder
}

user -> api: Request
api -> db: Query
api -> cache: Get/Set
api -> user: Response
```

---

## Flowchart

```d2
start: Start {
  shape: circle
}

process: Process Data
decision: Valid? {
  shape: diamond
}

success: Success {
  shape: circle
}
failure: Retry {
  shape: circle
}

start -> process
process -> decision
decision -> success: Yes
decision -> failure: No
failure -> process
```

---

## Sequence

```d2
shape: sequence_diagram

client: Client
server: Server
database: Database

client -> server: POST /login
server -> database: SELECT user
database -> server: user row
server -> client: JWT token

client -> server: GET /data
server -> database: SELECT *
database -> server: result set
server -> client: JSON response
```

---

## Class Diagram

```d2
User: {
  shape: class
  +id: int
  +name: string
  +email: string
  +login()
  +logout()
}

Order: {
  shape: class
  +id: int
  +user_id: int
  +total: float
  +submit()
}

User -> Order: has many
```

---

## Grid Layout

@layout two-col

```d2
direction: right
AWS -> GCP: Data sync
GCP -> Azure: Failover
```

@col

```d2
direction: right
Client -> LB: HTTPS
LB -> App1: HTTP
LB -> App2: HTTP
```
