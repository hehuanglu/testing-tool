# Resource preflight and storage/memory diagnosis

Read before heavy workloads or resource failures. Identify bottlenecks and grounded remedies rather than stopping at a free-space number. Do not lower admission thresholds; repair measurement/allocation/orchestration bugs under [remediation](local-remediation-and-continuation.md), verify, and remeasure. Lightweight modes have their own prerequisites. Use [retention/recovery](retention-stop-and-recovery.md) for complicated attempts without automatic fault campaigns/indexes.

## Measure the correct resources

Record time, actual output filesystem, Docker context, and planned workload. Use `df -k OUTPUT_PARENT` and separately measure Docker-image volumes where different. Host and Linux-VM free space are distinct.

Read current reserve/growth/calibration from actual plan/source/sidecars. Historical W4 used preflight `2×estimatedGrowth + 2GiB reserve`, runtime reserve 2GiB, plus memory/sampling/stop conditions; the fixed 8GiB floor was removed on 2026-10-19. This snapshot does not override current source. Disk sufficiency alone is not admission; HTTP calibration does not qualify HTTPS/browser workloads. Missing calibration means exact headroom is unknown.

Use `docker system df`, with `-v` only for attribution. Distinguish shared image layers/writable containers/volumes/build cache without summing every tag's full size. Reclaimable is not deletable authority: unused images may be pinned; zero-link volumes may hold backups/user data.

On Docker Desktop/macOS locate the actual disk image. `du -k Docker.raw` or allocated-block stat measures physical usage; `ls -lh` may show sparse logical maximum. Do not equate a 228GiB maximum with allocated usage or add internal Docker objects again to host totals.

Separate RAM from disk: `memory_pressure -Q`, `sysctl vm.swapusage`, and optionally `ps -axo pid,rss,comm | sort -k2,2nr`. RSS is a snapshot rather than additive physical-memory accounting. Omit full argv/environments. Disk shortage is not RAM shortage.

Routine preflight does not require recursive home scans, full suites, helper containers, or personal-data reading. Status-only stays read-only; use existing owned VM measurement paths where needed and state unavailable measurements rather than deriving VM free from system df.

## Diagnose low storage read-only

Move from aggregate to large branches with bounded depth/time/results. macOS `du -x -k -d 1` can inspect relevant home/Applications/Library/project/.codex branches. Expand only large contributors. Stop duplicate diagnosis traversals owned by this task, rather than user work. Read size/path metadata, not message databases/history/credentials/private evidence contents.

Classify installation bundles (quitting does not remove them), app data (profiles/attachments/simulators/downloads/staging, not all cache), developer data (dependencies/builds/worktrees/corpora/sessions/reports/backups), verified regenerable caches/logs/temp, and system/VM data (swap/sleepimage/APFS/purgeable). Names such as cache/in_progress are hints rather than deletion proof. Unknown UUID owners stay unknown; permission errors are not zero sizes or permission to bypass privacy controls. Large df/du gaps may justify read-only snapshot/open-deleted-file metadata, never deletion of swap/sleepimages/snapshots.

Avoid double counting aliases/parent-child paths/Docker.raw internals. State units (`GiB=bytes/2^30`, du -k=KiB), measurement coverage/errors/time and sparse/shared/cloned limitations. One snapshot cannot establish continual growth or disk/memory leaks.

## Choose grounded actions

Memory pressure: identify measured apps/tabs, suggest saving work and normal Quit where appropriate. Expect reduced working sets/swap growth without promising immediate full swap reclamation or exact disk gains. Stop stacks only with ownership/use established; quitting Docker stops product/scanner containers and may prevent the assessment itself.

Disk: prefer app-managed removal of confirmed unused downloads/resources/emulators after retention review, or moving retained data. App removal may leave data. Verified unused cache/staging can be narrow cleanup candidates with measured upper-bound bytes and rebuild/download effects, without promised equal df gains. Authorized archival needs destination capacity and verified integrity/restore before originals are removed; compression on full disks itself needs headroom.

For Docker, consider exact object IDs with labels/mount/reference checks, rather than system/volume prune, down -v, disk-image resizing, or deleting/moving Docker.raw. Location changes use Docker's supported UI; reclaim requires scoped authorization and data preservation, not privileged audit commands.

A diagnosis request alone does not authorize quitting/stopping/deleting/moving. Prepare concrete paths/IDs/sizes/ownership/effects/retained data before any necessary new approval; reuse still-valid explicit cleanup authority without asking again. Do not install cleanup apps or change autostart/configuration unsolicited.

After authorized actions remeasure the same host filesystem, allocated image/VM usage, and memory as applicable; verify product/scanner/history preservation. If provisioning breaches reserve after initial admission, inspect actual growth/concurrency, serialize heavy steps, avoid duplicate builds/copies, and reuse correctly pinned artifacts where supported. Evaluate legitimate owned-temp cleanup before declaring blocked, without lowering reserves/deleting evidence. Revalidated sufficient prerequisites permit retry despite old missing snapshots. Retry only blocked modes after **all** prerequisites pass; do not replay unknown POST/start or completed branches because disk improved.

## Report

State bottleneck, free/required/shortfall where computable, largest measured contributors/limits, and prioritized actions/effects. Distinguish RAM relief from disk cleanup and reclaim candidates from authorized changes. Preserve each mode's execution/security/cleanup/gate state and continue eligible independent work. New diagnostics do not rewrite old manifests.

Version-dependent product guidance should be checked against [Apple storage support](https://support.apple.com/en-au/102624) and [Docker Mac disk-usage documentation](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/macfaqs/).

[Anonymous FE](fe-anonymous-research.md) has a separate transport/journey lane; do not force it through backend-only binding/prerequisites.
