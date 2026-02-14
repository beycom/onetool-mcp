# sync-system Specification

## Purpose
TBD - created by archiving change standardize-backends. Update Purpose after archive.
## Requirements
### Requirement: sync.py MUST synchronize files from onetool-common/shared/ to backends

A Python script MUST copy shared files from onetool-common to backend projects based on manifest.yaml rules.

#### Scenario: Developer syncs shared files to a backend

**Given** onetool-common/shared/ contains updated files
**When** developer runs `uv run python ../onetool-common/sync.py` from a backend directory
**Then** files are copied according to manifest.yaml rules
**And** .shared-sync.yaml metadata file is created/updated
**And** developer sees which files were synced

#### Scenario: Developer checks sync status without making changes

**Given** a backend project has synced files
**When** developer runs `sync.py --status`
**Then** they see which files are synced and their last sync time
**And** they see which files are outdated
**And** no files are modified

#### Scenario: Developer previews sync changes

**Given** shared files have been updated in onetool-common
**When** developer runs `sync.py --dry-run`
**Then** they see what would be synced
**And** no files are actually modified
**And** they can review changes before applying

### Requirement: sync.py MUST track sync metadata

The sync system MUST record when files were last synced and from which version to enable status checking.

#### Scenario: Checking if synced files are outdated

**Given** a backend has .shared-sync.yaml with sync timestamps
**When** files in onetool-common/shared/ are modified
**Then** `sync.py --status` shows which files are outdated
**And** developer knows which files need re-syncing

### Requirement: sync.py MUST handle errors gracefully

The sync script MUST provide clear error messages and MUST NOT corrupt existing files on failure.

#### Scenario: Sync fails due to missing source file

**Given** manifest.yaml references a file that doesn't exist in shared/
**When** sync.py is run
**Then** a clear error message shows which file is missing
**And** no partial sync corrupts the destination
**And** sync.py exits with non-zero status

