## ADDED Requirements

### Requirement: Bounded Incremental Request Bodies

Every Direct API route SHALL consume request bodies through one incremental
bounded reader before HMAC authentication. `POST /run` SHALL allow at most
1,000,000 bytes. `GET /health`, `GET /ready`, and
`GET /api/console/outbox` SHALL each allow at most 65,536 bytes.

The reader SHALL stop requesting ASGI body messages as soon as the applicable
limit is crossed and SHALL retain neither the crossing chunk nor any remainder.
The single crossing chunk needed to detect overflow is the only data that MAY be
received beyond the limit.

A valid non-negative `Content-Length` above the route limit SHALL permit
rejection before body consumption. Missing, invalid, negative, chunked, or
dishonestly short `Content-Length` values SHALL NOT bypass incremental
accounting. Every oversized request SHALL receive a signed HTTP `413` using the
key scoped to that route, and no command, readiness, or outbox work SHALL run.

#### Scenario: Declared oversized body rejects before receive

- **WHEN** any Direct API route receives a valid `Content-Length` above its explicit limit
- **THEN** it SHALL return the route's signed HTTP `413`
- **AND** it SHALL NOT request the first ASGI body message
- **AND** it SHALL NOT perform route work

#### Scenario: Streamed overflow stops at crossing chunk

- **GIVEN** an absent, invalid, negative, chunked, or dishonestly short `Content-Length`
- **WHEN** streamed chunks cross the applicable route limit
- **THEN** the route SHALL return its signed HTTP `413`
- **AND** it SHALL NOT request another ASGI body message after the crossing chunk
- **AND** it SHALL NOT perform route work

#### Scenario: Exact-boundary body authenticates exact bytes

- **GIVEN** a request body whose length equals the route's explicit limit
- **AND** its HMAC signature covers that exact byte sequence
- **WHEN** the route consumes and authenticates the request
- **THEN** the request SHALL pass body-size validation
- **AND** HMAC verification SHALL use the exact accepted bytes without JSON reconstruction
- **AND** normal route behavior SHALL continue
