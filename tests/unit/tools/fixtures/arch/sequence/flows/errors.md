---
id: broken-flow
name: Broken flow
---

## Reserved

```seq
box Payments team
autonumber
activate pay-api
deactivate pay-api
create participant temp-svc
destroy temp-svc
par Side by side
critical Liveness
break Overload
rect rgb(230, 230, 230)
link pay-api: Dashboard @ https://example.test
note between pay-api, event-bus: nope
state over pay-api: waiting
text left: floating caption
divider delay with height 40: nope
```

## Body errors

```seq
pay-api ->> event-bus: ok [i-9999]
participant ghost-svc
pay-api - event-bus: headless arrow
pay-api <-x event-bus: crossed lost
+pay-api ->> event-bus: open marker on sender
pay-api ->> -event-bus: close marker on receiver
pay-api -) ...dangling: never delivered
...early -) event-bus
end
alt Left open
  pay-api ->> event-bus: inside
```

## Retry & fallback

```seq
pay-api ->> event-bus: fine
```

## Duplicate

```seq
pay-api ->> event-bus: fine
```

## Duplicate

```seq
pay-api ->> event-bus: fine
```
