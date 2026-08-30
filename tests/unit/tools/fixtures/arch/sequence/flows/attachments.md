---
id: attachments
name: Attachments
---

participant customer
participant pay-api

## Order placement

```seq
customer ->> pay-api: Place order [i-0001]
attach files/place-order-request.json
attach files/place-order-response.json
alt Declined
  pay-api -->> customer: 402 Declined
  attach files/declines.csv
end
pay-api -->> customer: 202 Accepted
attach files/place-order-response.json
```
