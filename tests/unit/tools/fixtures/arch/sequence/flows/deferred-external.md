---
id: deferred-external
name: Deferred and external
---

```seq
[ ->> pay-api: Inbound webhook
pay-api -) ...settle: Settle later
pay-api -->> ]: Webhook ack
pay-api <- ]: Poll request
...settle -) event-bus
```
