---
id: activation-modes
name: Activation modes
end_in: m1
---

## Auto

```seq
customer ->> pay-api: Place order
pay-api -->> customer: OK
```

## Manual

```seq
customer ->> +pay-api: Place order
pay-api -) event-bus: OrderPlaced
-pay-api -->> customer: OK
```
