---
id: warning-flow
name: Warning flow
start_in: m-orphan
---

## Crossed replies

```seq
adhoc-one ->> pay-api: Hello
pay-api ->> event-bus: First call
pay-api ->> event-bus: Second call
event-bus -->> pay-api: Done
```

## Manual mismatch

```seq
customer ->> +pay-api: Start
-event-bus -->> customer: Oops
```
