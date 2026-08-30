---
id: attachments-bad
name: Attachments bad
---

```seq
attach files/place-order-request.json
customer ->> pay-api: Place order
attach files/missing.json
attach ../escape.json
attach files/bad name.json
attach files/binary.bin
```
