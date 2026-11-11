# Bug backlog

Confirmed bugs that need fixing, one file per bug.

- File name: `YYYY-MM-DD-short-slug.md` (date the bug was reported, slug is a few words describing it).
- Start every new entry from `TEMPLATE.md`.
- Update `Status` in place as the bug moves through `Open` -> `In progress` -> `Fixed` (link the fix) or `Won't fix` (say why). Don't delete resolved entries - they're a record.
- Entries are written only by `backlog-keeper`, so they stay deduplicated.
- An entry needs real repro steps and evidence: the request and its filtered log lines, the failing command and its output, or the UI steps the user observed. A bug reported by the user is recorded with the steps as they observed them (`Evidence: reported by the user`); the bug fix flow reproduces it end to end before fixing. A bug report with no way to reproduce it isn't actionable.
- Keep the index below in sync whenever an entry is created or its status changes.

## Index

| Entry | Severity | Status |
| --- | --- | --- |
