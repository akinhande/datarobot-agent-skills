# Artifact lifecycle — rules the spec doesn't state

The SKILL.md section 4 has the operational summary and example code. This reference holds **only the behavioral rules** that aren't visible from the spec alone (`POST /artifacts/`, `PATCH /artifacts/{id}/`, etc. shapes are in the spec).

## Lifecycle states and transitions

```
create  →  iterate (PATCH while draft)  →  lock  →  rolling replacement
              ↳ status=draft                ↳ status=locked, immutable
                                              clones create new drafts
```

- Artifacts start in `draft` when created.
- While `draft`: PATCH applies in place.
- When `locked`: artifact becomes immutable. Any edit requires `POST /artifacts/{id}/clone/` (produces a new draft in the same artifact repository), then PATCH on the clone.
- Once locked, to deploy changes you trigger a **rolling replacement** on the workload (`POST /workloads/{wid}/replacement/`). Promote is the alternative for the in-place draft→locked case.

## Replacement status-match rule

The API rejects `POST /workloads/{id}/replacement/` with **HTTP 400** unless the new artifact's status matches the currently-running artifact's:

| Workload currently runs | New artifact must be | Use |
|---|---|---|
| draft | draft | `POST /workloads/{id}/replacement/` |
| draft | want to lock the same artifact | `POST /workloads/{id}/promote/` (no restart) |
| locked | locked | `POST /workloads/{id}/replacement/` |
| locked | want new content | clone → patch the draft → lock the new draft → `POST /workloads/{id}/replacement/` |

This rule is enforced server-side but isn't called out in the spec's path documentation — agents have to know it from the error response or from this reference.

## Promote — in-place lock without restart

`POST /workloads/{wid}/promote/` is the only way to transition a workload from "running a draft" to "running a locked production version" **without** a rolling restart:

- Artifact `status` flips draft → locked (becomes immutable).
- Workload's `artifactId` keeps pointing at the same artifact (now locked).
- Running pods are NOT restarted. Traffic uninterrupted.

If you also need a rolling restart in addition to the lock (e.g. to pick up new env vars from a recent PATCH), follow with `POST /workloads/{wid}/replacement/` using the same artifact ID. The intent split: promote = "the running version IS production"; replacement = "deploy a different version".

## PATCH on multi-container artifacts replaces the whole `containerGroups` array

If your artifact has multiple containers and you only want to change one, **fetch the full `spec` first, modify only the target container in place, and send the entire array back**. Sending one container will silently drop the others. The spec describes the schema shape but doesn't warn about this replacement-semantics gotcha.

Also: don't include `spec.type` in PATCH bodies — it's a read-only discriminator that the `UpdateArtifactRequest` write model rejects.

## Server-side image builds

If the artifact was created with `imageBuildConfig` referencing source code in DataRobot Files, the platform can build the image. Triggered with `POST /artifacts/{id}/builds/`; poll via `scripts/wait_for_build.py`. Two non-spec behaviors:

- On success, the platform **populates the artifact's `imageUri` automatically**. Re-`GET` the artifact to see it; don't PATCH it manually. If both `imageBuildConfig` and `imageUri` are supplied at create time, the build overwrites `imageUri` on completion.
- Success status can be either `BUILT` or `COMPLETED` depending on platform version — treat both as terminal-success.
- Only drafts can build. Builds for locked artifacts can't be triggered or deleted.

## Rolling replacement — non-idempotent, 404-after-completion

- **Not idempotent.** Calling `POST /workloads/{id}/replacement/` while one is in progress queues a second swap. Always check via `GET /workloads/{id}/replacement/` (or `scripts/wait_for_replacement.py`) before retrying.
- **`GET /workloads/{id}/replacement/` returns 404** when no active replacement exists — body: `{"detail": "There is no active replacement for this workload."}`. Treat as "no replacement in progress", not as an error. The polling script handles this case explicitly.
- On `failed`, the workload reverts to the old artifact. Diagnose the candidate's pods via `diagnose_workload.py` before retrying.

## Replacement history

`GET /workloads/{id}/history/` returns the chronological list of past replacements — who, when, which strategy. Useful for audit ("which artifact version was running on 2026-04-15?") and rollback ("the previous artifact ID was X — replace back to that").
