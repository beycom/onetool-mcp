## ADDED Requirements

### Requirement: Transactional Guided Encrypted-Secrets Setup

The guided `onetool init` encrypted-secrets flow SHALL keep newly entered values
in memory until a confirmed operation can atomically install a secure plaintext
recovery backup and a verified encrypted target.

#### Scenario: Cancellation during entry
- **WHEN** a user cancels at the first key, after one or more complete pairs, or during value entry
- **THEN** the flow SHALL discard all newly entered values
- **AND** no new target, backup, or residual temporary file SHALL remain
- **AND** any prior target and backup SHALL remain byte-identical

#### Scenario: Existing identity reuse accepted
- **WHEN** an identity already exists and the user accepts reuse
- **THEN** the flow SHALL encrypt all new values with that identity
- **AND** SHALL NOT change any private key, public key, or label entry
- **AND** existing ciphertext SHALL remain decryptable

#### Scenario: Existing identity reuse declined or cancelled
- **WHEN** an identity already exists and the user declines or cancels reuse
- **THEN** the flow SHALL abort without offering or invoking identity replacement
- **AND** all keychain entries, the selected target, its backup, and ciphertext in every other file SHALL remain exact

#### Scenario: Returned or raised lifecycle failure
- **WHEN** identity initialization, encryption, or audit returns an error result or raises an exception
- **OR** audit reports `safe` other than `true`
- **THEN** the flow SHALL report failure and SHALL NOT report success
- **AND** no newly entered plaintext SHALL have been written to the target or an incidental temporary file
- **AND** the prior target and backup SHALL remain byte-identical or both SHALL remain absent

#### Scenario: Successful confirmed setup
- **WHEN** the user confirms one or more complete secret pairs
- **AND** identity initialization or reuse, encryption, and audit all succeed
- **THEN** the target SHALL contain only verified ciphertext or null values at mode `0600`
- **AND** `<target>.bak` SHALL contain the exact recovery serialization including the newly entered plaintext at mode `0600`
- **AND** no incidental temporary file SHALL remain
