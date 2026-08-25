---
id: frames-and-notes
name: Frames and notes
---

```seq
loop Every morning
  pay-api ->> event-bus: Poll
  if backlog > 100
    pay-api ->> fraud-check: Bulk scan
  else if backlog > 0
    pay-api ->> fraud-check: Scan
  else
    pay-api ->> pay-api: Sleep
  end
end
repeat Until drained
  pay-api ->> event-bus: Drain
end
opt Trace enabled
  pay-api -) event-bus: TraceSpan
end
group Cleanup
  pay-api ->> event-bus: Purge
end
divider: Later
divider line: Same day
divider space: Quiet gap
divider delay: 3 days
divider tear: 200 calls elided
note over pay-api: Single note
note over pay-api, event-bus: Spanning note
note left of pay-api: Left note\nsecond line
note right of pay-api: Right note<br/>third line
pay-api ->> event-bus: First line\nSecond line
```
