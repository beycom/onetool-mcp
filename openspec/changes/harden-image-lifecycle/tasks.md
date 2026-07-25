## 1. Canonical Identity and Storage

- [x] 1.1 Add strict public-reference and internal-name validation for complete SHA-256 image handles
- [x] 1.2 Replace scan-based deduplication and metadata filename trust with exact digest-derived paths
- [x] 1.3 Make reads, writes, summaries, listing, deletion, purge, and cache access reject tampered or redirected paths
- [x] 1.4 Remove custom handles, load passthrough, bare references, legacy fallbacks, and obsolete exports

## 2. Remote Source Boundary

- [x] 2.1 Stream URL responses with the fixed 20 MiB declared and observed byte limit
- [x] 2.2 Normalize expected HTTP and network failures while preserving unexpected exception propagation
- [x] 2.3 Guarantee response closure and prevent downstream processing after overflow

## 3. Cache Configuration

- [x] 3.1 Validate positive session cache capacity through hosted and standalone configuration paths
- [x] 3.2 Verify capacity-one and positive-capacity singleton LRU behavior

## 4. Contracts and Verification

- [x] 4.1 Add public-path, failure-injection, filesystem, symlink, lifecycle, transport, and batch continuation tests
- [x] 4.2 Update the main OpenSpec, tool documentation, examples, and generated tool index to the canonical contract
- [x] 4.3 Run combined focused image tests and all issue-specific validation commands
- [x] 4.4 Run strict OpenSpec validation, documentation validation, and `just check`
- [x] 4.5 Verify the completed OpenSpec change against implementation with no findings
