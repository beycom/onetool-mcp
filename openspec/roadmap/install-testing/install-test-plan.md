# Local Install and Upgrade Test Plan

**Status:** Planned

**Primary host:** MacBook Pro M3 Pro, 36 GB RAM, macOS 26

**VM storage:** Corsair EX400U 1 TB USB4 SSD

**Execution model:** Local and manually triggered; never part of GitHub Actions

## 1. Outcome

Create a small local VM lab that can repeatedly verify clean installation,
upgrade, uninstall, and MCP-client integration on macOS, Windows, and Linux.
The normal workflow should be:

1. Revert a VM to its clean snapshot.
2. Start it and run one selected test scenario.
3. Collect logs and a machine-readable result on the Mac.
4. Shut the VM down without changing the clean snapshot.

The first version should favour three manually created VM templates and simple
host scripts over Packer, Vagrant, Ansible, or a permanent cloud environment.
Those tools solve repeatable VM construction, but snapshot reset is faster and
simpler for a lab used only a few times per release.

## 2. Recommended Platform

Use **Parallels Desktop Pro Edition** as the primary hypervisor.

| Option | Appropriate use | Decision |
|---|---|---|
| Parallels Desktop Pro | Windows, Linux, and virtual macOS on Apple silicon; `prlctl` automation; snapshots and clones | **Selected** |
| Parallels Standard | Manual VMs limited to 4 vCPUs and 8 GB RAM | Not selected because it omits the command-line automation required by this plan |
| VirtualBox | Free ARM Windows/Linux experimentation | Not selected because it does not provide the same simple three-OS workflow |
| Docker, Podman, or OrbStack | Very fast Linux userland pre-checks | Optional supplement; containers do not test a clean Windows or macOS installation |
| Cloud VMs | x86-64 coverage or overflow capacity | Optional, on demand only |

Parallels Pro supports `prlctl`/`prlsrvctl`, headless VM execution, snapshots,
cloning, and command-line integration. Parallels Standard meets the proposed
4-vCPU/8-GB ceiling but does not include the CLI, so it would leave snapshot
reset and orchestration as manual steps.

## 3. Initial Target Matrix

Run only one VM at a time during normal testing.

| ID | Guest | Architecture | vCPU | RAM | Virtual disk | Purpose |
|---|---|---:|---:|---:|---:|---|
| `it-macos-26-arm64` | macOS 26 | ARM64 | 4 | 8 GB | 64 GB | Native macOS install and MCP-client path |
| `it-windows-11-arm64` | Windows 11 | ARM64 | 4 | 8 GB | 80 GB | Native Windows PowerShell install and MCP-client path |
| `it-ubuntu-26-arm64` | Ubuntu 26.04 LTS | ARM64 | 4 | 6 GB | 40 GB | Native Linux install and MCP-client path |

This matrix tests the native architecture of the M3 host. Add these only when
release risk justifies them:

- Ubuntu x86-64 in a small AWS or Azure VM.
- Windows x86-64 using a cloud Windows Server image for CLI compatibility.
- A supported x86-64 Parallels VM in emulation mode for a local diagnostic, with
  the expectation that it will be slower than an ARM guest.

Do not treat Windows-on-ARM application emulation as proof that the package
installs correctly on an x86-64 operating system. Architecture-specific wheels
and dependencies still require a real x86-64 test when they are release risks.

## 4. Licences, Accounts, and Expected Cost

| Item | Requirement | Plan |
|---|---|---|
| Parallels Desktop | Separate hypervisor licence | Use the 14-day Pro trial to build the lab, then buy a Pro subscription for ongoing CLI automation. No Business licence is needed for one user and one Mac. |
| Windows | Parallels does not include Windows | Begin with the official Windows 11 Enterprise ARM64 90-day evaluation. Buy a Windows licence when the evaluation conditions below are not suitable. |
| macOS | No separate macOS purchase for a guest on the Apple Mac | The current macOS 26 licence permits up to two additional virtual instances per Apple-branded Mac for software development, development testing, macOS Server, or personal non-commercial use. This plan runs only one macOS guest. |
| Ubuntu | No OS licence fee | Use the official Ubuntu 26.04 LTS ARM64 image. |
| Codex CLI | No guest-specific software licence | Sign in with an eligible ChatGPT account or use an API key. Automated model calls can consume paid API usage or subscription quota. |
| Cloud | Optional account and usage charges | Use short-lived Linux/Windows instances only when x86-64 coverage is required. Set a budget alert before first use. |

### Windows evaluation decision

The Windows 11 Enterprise evaluation is appropriate when all of the following
are true:

- the VM is used only for testing, not as a daily or production desktop;
- Enterprise edition is representative enough for the installer being tested;
- the template can be rebuilt before its 90-day evaluation expires; and
- the test does not need to validate Windows activation or a consumer Pro/Home
  installation path.

The evaluation is not appropriate for a long-lived template, for testing the
licensed Windows 11 Pro experience, or after the evaluation period. Reverting a
snapshot must not be used to extend or evade the evaluation period.

If evaluation media is not suitable, use one of these licensed paths:

1. Buy a retail Windows 11 Pro licence for the single persistent Windows VM and
   keep using snapshots of that same VM.
2. Use development/test rights from an existing Visual Studio subscription or
   organisational Microsoft agreement, after confirming its terms.

Treat each independently runnable clone as another Windows installation. Prefer
one activated VM plus snapshot reverts; confirm licensing before creating
multiple persistent or concurrently usable Windows clones.

Cloud Windows desktop licensing is more complicated than local retail licensing.
For an occasional x86-64 CLI check, prefer a provider Windows Server image whose
OS charge is included in the hourly price. Do not assume an Azure or AWS Windows
11 desktop is covered without checking the relevant Microsoft entitlement.

## 5. External SSD Layout and Safety

Keep the Parallels application on the internal Mac disk and store VM bundles on
the EX400U.

Before creating VMs, erase the EX400U in Disk Utility using:

- Scheme: **GUID Partition Map**
- Format: **APFS** or **APFS Encrypted**, not case-sensitive
- Volume name: `VM-Lab`

Erasing is destructive and must only be done after existing data is backed up.

Use this layout:

```text
/Volumes/VM-Lab/
├── Parallels/
│   ├── it-macos-26-arm64.macvm
│   ├── it-windows-11-arm64.pvm
│   └── it-ubuntu-26-arm64.pvm
├── images/
│   ├── macos/
│   ├── windows/
│   └── linux/
└── transfer/
```

Operational rules:

- Connect the EX400U directly with a 40-Gbps USB4 cable, not through a slow hub.
- Never disconnect or eject it while a VM is running or suspended.
- Shut down guests rather than suspending them before moving or backing up a VM.
- Keep at least 150-200 GB free for snapshots, upgrades, and temporary clones.
- Back up the clean VM bundles to a different physical disk. A snapshot on the
  EX400U is not a backup of the EX400U.
- Do not store the only copy of test scripts or results inside a VM.

One terabyte is sufficient for the three base VMs and several snapshots. Expect
approximately 300-500 GB of practical use after OS updates, previous-version
upgrade snapshots, and temporary test data.

## 6. One-Time VM Construction

### 6.1 Common baseline policy

Each base VM should contain only:

- the installed and fully updated operating system;
- Parallels Tools;
- a non-personal `installtest` administrator account;
- an SSH server and the lab public key, where supported;
- correct time, DNS, and shared-NAT networking; and
- the minimum OS facilities needed for remote orchestration.

The `00-os-clean` snapshot must not contain:

- OneTool, `uv`, a user-installed Python toolchain, Node.js, npm, or Codex CLI;
- OpenAI, package-index, cloud, or service credentials;
- a personal Apple or Microsoft account unless the OS installer requires one;
- the OneTool repository; or
- mutable Parallels shared folders from the host.

This keeps the bootstrap test honest: it must install its own prerequisites and
must work after a new login shell.

### 6.2 macOS 26 ARM64

The fastest path is Parallels **File > New > Install macOS**, followed by
configuration before first use:

- 4 vCPUs;
- 8 GB RAM;
- 64 GB disk;
- shared NAT networking; and
- VM location under `/Volumes/VM-Lab/Parallels`.

For later scripted rebuilds, Parallels Pro supports creating a macOS VM from an
Apple IPSW with `prlctl create <name> -o macos --restore-image <ipsw>`, followed
by `prlctl set <name> --cpus 4 --memsize 8192`. The installed Parallels version's
`prlctl help` output remains authoritative for exact flags.

Enable Remote Login for the `installtest` account, install the lab SSH public
key, apply OS updates, shut down, and create `00-os-clean`.

Use the same major macOS version in host and guest. Parallels only guarantees the
same-major-version combination on Apple silicon, and virtual macOS has additional
Apple Virtualization Framework limitations.

### 6.3 Windows 11 ARM64

Create the VM from either:

- the official Windows 11 Enterprise ARM64 evaluation ISO; or
- Parallels' Windows 11 download followed by activation with the purchased
  Windows licence.

Configure 4 vCPUs, 8 GB RAM, an 80-GB expanding disk, shared NAT networking, and
the EX400U destination. Install all Windows updates and Parallels Tools.

Enable the built-in OpenSSH Server optional feature, restrict it to the lab
account/key, and verify that a non-interactive PowerShell command can run over
SSH. Shut down and create `00-os-clean`.

Record the evaluation expiry date or activation basis in host-side lab metadata,
not inside test logs. Rebuild evaluation media before expiry.

### 6.4 Ubuntu 26.04 LTS ARM64

Create the VM using the official ARM64 image. Configure 4 vCPUs, 6 GB RAM, a
40-GB expanding disk, shared NAT networking, and the EX400U destination.

Choose the minimal installation, install `openssh-server` and Parallels Tools,
apply updates, install the lab SSH public key, shut down, and create
`00-os-clean`.

### 6.5 Back up the templates

After all three snapshots are verified:

1. Shut every VM down completely.
2. Copy each `.pvm`/`.macvm` bundle to a second physical disk.
3. Record the OS version, architecture, snapshot ID, creation date, Windows
   evaluation expiry or licence basis, and bundle checksum in a small host-side
   inventory.

## 7. Automation Design

### 7.1 Keep version 1 small

Add a future host-side runner rather than automating the OS installers first:

```text
scripts/install-test/
├── lab.sh                    # macOS host orchestrator
├── config.yaml               # VM names, snapshot IDs, addresses, resources
├── guest-posix.sh            # macOS/Linux scenario runner
├── guest-windows.ps1         # Windows scenario runner
├── mcp-smoke.py              # protocol-level initialize/list/call test
└── README.md                 # operator commands and recovery
```

Expose it through future local-only `just` recipes such as:

```bash
just install-test macos install
just install-test windows upgrade FROM_VERSION=3.0.0
just install-test linux mcp
just install-test all install
```

These commands are developer conveniences, not CI jobs.

### 7.2 Host runner sequence

For each selected VM, the runner should:

1. Confirm `/Volumes/VM-Lab` is mounted and the expected bundle exists.
2. Refuse to continue if the VM is suspended or another lab run holds the lock.
3. Revert to the recorded `00-os-clean` snapshot with `prlctl snapshot-switch`.
4. Start the VM headlessly and wait with a bounded timeout for SSH.
5. Copy only the selected guest script, wheelhouse, and MCP smoke client.
6. Execute the scenario with a clean environment and capture stdout, stderr,
   exit code, timing, OS version, architecture, and installed package versions.
7. Copy results back to the host.
8. Shut the guest down cleanly, with a bounded forced-stop fallback.
9. Leave the base snapshot unchanged and release the host lock.

Use Parallels snapshot IDs rather than snapshot names in automation. Names are
for people; IDs prevent the runner reverting to an ambiguous snapshot.

### 7.3 Result storage

Store results outside the VMs:

```text
wip/test-results/install-testing/<UTC timestamp>/
├── summary.md
├── results.json
├── macos/
├── windows/
└── linux/
```

The summary should include the commit or published version tested, package
source, VM snapshot ID, commands, durations, pass/fail status, and the first
actionable error. Logs must redact tokens, keys, home-directory usernames, and
MCP environment values.

## 8. Package Sources

Support two distinct modes.

### Published release mode

Test exactly what a user sees:

```bash
curl -LsSf https://onetool.beycom.online/install.sh | sh
```

```powershell
irm https://onetool.beycom.online/install.ps1 | iex
```

This validates the deployed installer, checksum files, PyPI resolution, PATH
changes, initialization, and printed MCP configuration.

### Release-candidate mode

Before publication:

1. Build the complete wheel set on the host.
2. Copy it into the guest's temporary directory.
3. Install from that wheelhouse with network package resolution disabled for
   OneTool packages.
4. Run the same assertions as published-release mode.

The current bootstrap scripts always resolve `onetool-mcp` from the configured
package index. Therefore a pre-publication test of the complete bootstrap path
needs one of these explicit facilities before it can be fully automated:

- a staging package index and staging installer URL; or
- a documented installer input such as `ONETOOL_PACKAGE_SPEC` or an index URL
  override, validated by both shell and PowerShell installers.

Until then, test the candidate wheels and local installer scripts separately,
then run one final published bootstrap test immediately after release.

## 9. Test Scenarios

### 9.1 Clean installation

Run on all three operating systems:

1. Confirm `uv`, `onetool`, and Codex are absent at the start. Record any
   OS-supplied Python, but do not preinstall the Python required by OneTool.
2. Run the platform bootstrap non-interactively with an explicit component/extras
   selection.
3. Start a new login shell; do not rely on the installer's current process PATH.
4. Verify:
   - `uv --version`;
   - `onetool --version`;
   - the expected installed OneTool components/extras;
   - `onetool init validate --config <clean test directory>/onetool.yaml`;
   - generated MCP command paths are absolute and exist; and
   - no unexpected prompt occurs in non-interactive mode.
5. Run the protocol-level MCP smoke test described below.

Also run these narrower cases on at least Linux and Windows:

- downloaded installer checksum verification before execution;
- manual `uv tool install` of every supported component composition;
- invalid `ONETOOL_EXTRAS` rejection;
- installation into a path containing spaces; and
- uninstall followed by a clean reinstall, confirming whether configuration is
  intentionally retained.

When `add-lightweight-mcp-skill-installs` lands, expand the matrix to cover
facade-only, `[mcp]`, `[skill]`, `[mcp,skill]`, `[util]`, `[dev]`, and `[all]`,
including absence checks for components that were not selected.

### 9.2 Upgrade

For every supported OS:

1. Revert to `00-os-clean`.
2. Install the previous supported release from PyPI with a fixed version.
3. Initialize a representative configuration and capture its files and hashes.
4. Optionally snapshot this state as `10-previous-<version>` while that upgrade
   path remains relevant.
5. Upgrade to the candidate wheel set or new published version.
6. Verify:
   - the reported version changed as expected;
   - configuration and intended user state were preserved;
   - removed configuration/API values fail through current validation rather
     than being accepted through compatibility shims;
   - MCP startup and `ot.version()` work after upgrade;
   - the old executable/environment is not left earlier on PATH; and
   - a second upgrade invocation is idempotent.

For a breaking component-layout release, explicitly test each documented
migration command. Do not silently make a formerly bare installation behave as
`[mcp]`; the test should require the new documented component selection.

### 9.3 MCP protocol smoke test

Use a small Python client based on the MCP SDK so this test needs no AI model,
Codex login, or billable inference. It should start OneTool over stdio and assert:

1. MCP initialization succeeds within the timeout.
2. `tools/list` returns exactly the expected root tool surface, including `run`.
3. Calling `run` with `{"command": "ot.version()"}` succeeds.
4. Calling `run` with `{"command": "ot.packs()"}` returns a non-empty result.
5. The server exits cleanly when the client closes.

Run an additional Streamable HTTP smoke test when transport behavior changed:

```bash
onetool serve --transport http --config <config> \
  --host 127.0.0.1 --port 8767 --path /mcp
```

### 9.4 Codex CLI integration

Protocol testing is the release gate; Codex is an additional real-client test.

For a full run:

1. Install the current Codex CLI. Use the official standalone installer on
   macOS/Linux. For a uniform Node-based installation across all three guests,
   first install the current Node.js LTS release and then run
   `npm install --global @openai/codex`.
2. Verify `codex --version`.
3. Register OneTool as a stdio MCP server using the absolute installed executable:

   ```bash
   codex mcp add onetool -- \
     /absolute/path/to/onetool serve \
     --config /absolute/path/to/onetool.yaml
   ```

4. Verify `codex mcp list` shows `onetool` enabled.
5. Run one authenticated manual or opt-in `codex exec` prompt that instructs
   Codex to call OneTool's `run` tool for `ot.version()` and report the result.
6. Record only the pass/fail result and CLI versions, not the conversation,
   credential, or token data.

Do not store Codex authentication in `00-os-clean`. For automated real-client
tests, inject a short-lived API credential at run time and remove it before the
VM is shut down. Keep the Codex model call opt-in because it may consume quota or
incur cost.

## 10. Containers and Cloud

### Containers

Use an ARM64 Ubuntu container for a sub-minute POSIX installer pre-check before a
VM run, especially while editing shell logic. This catches missing commands,
shell errors, and basic package resolution, but it is not release evidence for:

- macOS behavior;
- native Windows PowerShell behavior;
- `systemd`, login-shell PATH, keychain, desktop, or OS installer behavior; or
- a genuinely clean full operating system.

Choose whichever of OrbStack, Docker, or Podman is already installed. Do not buy
or configure another container product solely for this plan.

### Cloud fallback

Use cloud only for architecture coverage or when the Mac lab is unavailable:

- **Linux x86-64:** a small temporary AWS EC2 or Azure VM initialized with
  cloud-init, then destroyed after result collection.
- **Windows x86-64:** a temporary provider Windows Server image managed through
  AWS Systems Manager or Azure Run Command, avoiding public RDP when possible.
- **macOS:** keep this local. AWS EC2 Mac requires bare-metal Dedicated Hosts and
  a minimum 24-hour host allocation, making it poor value for occasional short
  tests.

If cloud use becomes regular, add a small OpenTofu/Terraform module with automatic
expiry tags, budget alerts, no inbound public ports, and a destroy command. Do not
introduce it for the first local implementation.

## 11. Pass Criteria

A platform/scenario passes only when:

- the run began from the recorded clean snapshot;
- the documented install or upgrade command returned zero;
- a fresh shell resolved the expected `uv`, `onetool`, and optional `codex`
  executables;
- OneTool version, component selection, init, and validation matched expectations;
- the MCP SDK initialized the server, listed `run`, and executed `ot.version()`;
- no credentials or host-personal paths appeared in collected logs;
- the guest shut down cleanly; and
- `results.json` and the human summary were copied to the host.

Codex model invocation may be marked `skipped` when credentials or quota are not
provided. The non-billable MCP protocol smoke test may not be skipped.

## 12. Fastest Implementation Order

### Phase 1: useful manual lab

- [ ] Format the EX400U as APFS and create the storage layout.
- [ ] Install the Parallels Pro trial.
- [ ] Build the three VMs and create `00-os-clean` snapshots.
- [ ] Manually run one published install and MCP smoke test on each OS.
- [ ] Buy Parallels Pro after confirming the workflow.
- [ ] Decide whether the Windows evaluation is sufficient before buying Windows.

### Phase 2: one-command reset and execution

- [ ] Add the host runner, VM inventory, lock, bounded waits, and log collection.
- [ ] Add POSIX and PowerShell guest scripts.
- [ ] Add the non-billable MCP SDK smoke client.
- [ ] Add local `just install-test` recipes.
- [ ] Record the first complete three-OS result under `wip/test-results/`.

### Phase 3: release and upgrade coverage

- [ ] Add candidate wheelhouse installation.
- [ ] Add previous-release-to-candidate upgrade scenarios.
- [ ] Add component/extras matrix coverage for the lightweight installation change.
- [ ] Add the opt-in Codex real-client scenario.
- [ ] Add x86-64 cloud tests only when a release contains architecture-sensitive
  dependencies or installer behavior.

## 13. Maintenance

- Refresh each `00-os-clean` template with OS updates before a release test, then
  replace the old snapshot instead of layering updates indefinitely.
- Rebuild the Windows evaluation template before its expiry date.
- Back up clean bundles before upgrading Parallels Desktop or making VM hardware
  changes.
- Verify the Parallels CLI command surface after major Parallels upgrades.
- Review all licence and product links at least annually; prices and product terms
  are intentionally not hard-coded here.
- Delete obsolete previous-version upgrade snapshots when that upgrade path is no
  longer supported.

## 14. References

- [Parallels Desktop Pro developer features and CLI](https://www.parallels.com/products/desktop/pro/)
- [Parallels edition comparison](https://www.parallels.com/products/desktop/buy/)
- [Parallels: create a VM from the CLI](https://docs.parallels.com/landing/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/general-virtual-machine-management/create-a-virtual-machine)
- [Parallels: revert to a snapshot](https://docs.parallels.com/landing/parallels-desktop-developers-guide/command-line-interface-utility/manage-virtual-machines-from-cli/snapshot-management/reverting-to-a-snapshot)
- [Parallels: Apple-silicon macOS VM limitations](https://kb.parallels.com/en/128867)
- [Parallels: run VM bundles from an external SSD](https://kb.parallels.com/en/114118)
- [Parallels: Windows is not included](https://kb.parallels.com/en/113879)
- [Microsoft Windows 11 Enterprise evaluation](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise)
- [Apple macOS 26 software licence agreement](https://www.apple.com/legal/sla/docs/macOSTahoe.pdf)
- [Ubuntu 26.04 LTS downloads](https://ubuntu.com/download/desktop)
- [OpenAI Codex CLI](https://developers.openai.com/codex/cli/)
- [OpenAI Codex MCP configuration](https://developers.openai.com/codex/mcp/)
- [AWS EC2 Mac instance constraints](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)
- [Docker Desktop's Linux VM architecture on macOS](https://docs.docker.com/desktop/features/vmm/)
