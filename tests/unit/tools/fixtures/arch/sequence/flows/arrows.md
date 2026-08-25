---
id: arrow-matrix
name: Arrow matrix
---

```seq
shop -> pay-api: solid single
Pay-API ->> event-bus: solid double
pay-api --> shop: dashed single
pay-api -->> shop: dashed double
pay-api -) event-bus: paren async
pay-api --) event-bus: dashed async
pay-api -x event-bus: lost solid
pay-api --x event-bus: lost dashed
pay-api ~> event-bus: wavy async
customer <- pay-api: reversed solid
customer <-- pay-api: reversed dashed
customer <<- pay-api: reversed double
pay-api <-> event-bus: bidi sync
pay-api <--> event-bus: bidi reply
pay-api <<-->> event-bus: bidi double reply
fraud-check -> charge-fn: component to code
pay-api -> pay-api: self call
pay-api -> event-bus
customer ->> pay-api [i-0001]
```
