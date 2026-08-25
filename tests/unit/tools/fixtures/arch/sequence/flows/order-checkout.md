---
id: order-checkout
name: Order checkout
description: How an order is placed, authorised, and confirmed.
tags: [payments]
start_in: m1
---

participant customer
participant PSP as Worldline PSP
actor ops as Ops Engineer

## Happy path

The customer pays and the order is confirmed.

```seq
%% comment lines are ignored
# so are hash comment lines
customer ->> pay-api: Place order [i-0001]
pay-api ->> PSP: Authorise card
PSP -->> pay-api: Approved
pay-api -) event-bus: OrderPlaced
pay-api -->> customer: 202 Accepted
```

## Declined

```seq
customer ->> pay-api: Place order [i-0001]
pay-api ->> PSP: Authorise card
alt Soft decline
  PSP -->> pay-api: Soft decline
  pay-api ->> PSP: Retry authorisation
  divider delay: cooldown
  PSP -->> pay-api: Approved
else Hard decline
  pay-api -x PSP: Authorise card
  pay-api -->> customer: 402 Declined
end
note over customer, pay-api: Customer sees the outcome
```
