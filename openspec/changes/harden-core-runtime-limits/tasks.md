## 1. Bounded In-Process Execution

- [x] 1.1 Add a process-global eight-job execution controller whose slots are owned by underlying concurrent futures
- [x] 1.2 Dispatch user code through the controller and return immediate capacity errors without submitting overflow work
- [x] 1.3 Preserve admitted work across timeout and caller cancellation, and make the timeout response disclose possible continued side effects
- [x] 1.4 Open admission at MCP startup and stop admission plus drain all admitted work before dependent shutdown

## 2. Incremental Direct API Bodies

- [x] 2.1 Replace full-body buffering with one streaming reader that accepts an explicit route limit
- [x] 2.2 Apply the 1,000,000-byte run limit and 65,536-byte control-route limit to health, readiness, run, and outbox
- [x] 2.3 Preserve exact accepted bytes for HMAC and return route-key-signed 413 responses before downstream work

## 3. Verification and Contract Synchronization

- [x] 3.1 Test capacity overflow, timeout/cancellation accounting, post-timeout side effects, release, and shutdown draining with real threads
- [x] 3.2 Test raw ASGI bodies for declared, absent, invalid, negative, dishonest, exact-boundary, and streamed lengths across every route
- [x] 3.3 Sync the delta requirements into main specs and update any affected user documentation
- [x] 3.4 Run focused executor, lifecycle, and Direct API tests, strict OpenSpec validation, and `just check`
