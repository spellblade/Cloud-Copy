# Roadmap (from user gist)

Source: [Cloud-copy issues gist](https://gist.github.com/spellblade/59af9aceb0a78b7f69bd8bc06ad110f3) (2026-08-26). Also [#16](https://github.com/spellblade/Cloud-Copy/issues/16) (retry skip).

Priority buckets (P0–P3) describe **importance**. **Implementation order** (below) is ease × risk × priority — not “P0 first.”

## P0 — Unblocks real use

| Issue | Problem |
|-------|---------|
| [#6](https://github.com/spellblade/Cloud-Copy/issues/6) | After a failed/cancelled job, the next transfer stays **queued** until cancel + retry. Worker/queue must always pick up the next job. |
| [#4](https://github.com/spellblade/Cloud-Copy/issues/4) | Progress bar jumps only when a file **finishes**. Status shows end totals (`47.6 KB/47.6 KB`), not live bytes. Need per-file download/upload progress and a clear current stage. |
| [#5](https://github.com/spellblade/Cloud-Copy/issues/5) | Selecting a **folder** does not transfer as expected. |

## P1 — Reliability and failed-state clarity

| Issue | Problem |
|-------|---------|
| [#7](https://github.com/spellblade/Cloud-Copy/issues/7) | `HTTPConnectionPool(host='gfs….userstorage.mega.co.nz', port=80): Read timed out` — retries, longer timeout, prefer HTTPS (not port 80) where possible. |
| [#8](https://github.com/spellblade/Cloud-Copy/issues/8) | `SSL validation failed … EOF occurred in violation of protocol (_ssl.c:2406)` on PikPak upload hosts — retry/backoff; don’t treat first EOF as final. |
| [#13](https://github.com/spellblade/Cloud-Copy/issues/13) | Failed jobs must show **which stage** failed (download vs upload vs queue). |
| [#16](https://github.com/spellblade/Cloud-Copy/issues/16) | Retry re-uploads files already complete on the destination; should skip uncorrupted dest files and resume the failed step. |

## P2 — UX polish

| Issue | Problem |
|-------|---------|
| [#9](https://github.com/spellblade/Cloud-Copy/issues/9) | Sticky **NAME** header: folder/file **icons scroll over the heading** while checkboxes and names go underneath. **Loading** appears at the **bottom** of the table (must scroll). |
| [#10](https://github.com/spellblade/Cloud-Copy/issues/10) | Warn that a 6-digit TOTP should be used only when **fresh** and still has time left. |

## P3 — Extra features

| Issue | Problem |
|-------|---------|
| [#11](https://github.com/spellblade/Cloud-Copy/issues/11) | No **New folder** or **Delete folder** in the panes. |
| [#12](https://github.com/spellblade/Cloud-Copy/issues/12) | All transfers are serial. Want parallel downloads and the ability to abort **individual** files in a multi-select job. |

## Implementation order

Work sequence (ease × risk × priority). **Branch** is a plain name (no link); use `—` until work starts. Names stay even if the branch is deleted later.

| Order | Issue | Resolved | Branch |
|-------|--------|----------|--------|
| 1 | [#10](https://github.com/spellblade/Cloud-Copy/issues/10) TOTP hint | Yes | `feat/gist-backlog` |
| 2 | [#13](https://github.com/spellblade/Cloud-Copy/issues/13) Failed stage | Yes | `feat/gist-backlog` |
| 3 | [#9](https://github.com/spellblade/Cloud-Copy/issues/9) File-list UI | Yes | `feat/file-list-ui` |
| 4 | [#5](https://github.com/spellblade/Cloud-Copy/issues/5) Folder select | Yes | `feat/folder-select` |
| 5 | [#4](https://github.com/spellblade/Cloud-Copy/issues/4) Live progress | No | `feat/live-progress` |
| 6 | [#6](https://github.com/spellblade/Cloud-Copy/issues/6) Queue stuck | No | — |
| 7 | [#16](https://github.com/spellblade/Cloud-Copy/issues/16) Retry skip completed dest | No | — |
| 8 | [#7](https://github.com/spellblade/Cloud-Copy/issues/7) MEGA timeout | No | — |
| 9 | [#8](https://github.com/spellblade/Cloud-Copy/issues/8) PikPak SSL | No | — |
| 10 | [#11](https://github.com/spellblade/Cloud-Copy/issues/11) New/Delete folder | No | — |
| 11 | [#12](https://github.com/spellblade/Cloud-Copy/issues/12) Parallel + abort | No | — |

## Notes

- MEGA/PikPak errors need **retries**, not only better error text.
- Parallelism is last: serial + a working queue + live progress is more valuable first.
- #16 sits after #6 so retry/queue is trustworthy before skip-on-dest logic.
