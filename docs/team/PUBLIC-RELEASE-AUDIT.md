# Public release audit — Job 8

**Human release decision required.** GitHub's repository metadata reports `Tecncentral/typecast` is already **public** (checked 2026-11-14 UTC). This is therefore a review of already reachable history and proposed new history, not a promise that visibility can be changed later. No visibility change, history rewrite, branch deletion or credential rotation was performed.

## Findings

| Priority | Commit / path | Finding and risk | Decision required |
| --- | --- | --- | --- |
| High, before publishing the pending branch | `9131594`, retained/expanded in `e93ad59`; `docs/team/status-worlds.md` | Real CoStar property identifiers are embedded in example shot identifiers and local browser URLs. Exact matches were checked locally against the private join; values, complete shot identifiers and URLs are deliberately omitted here. At inspection these commits were reachable only from the local `dressed-set` branch, not a fetched remote branch or `origin/dev`. A future push would expose them in history even if a later commit removes them. | The World Labs owner and human must decide how to remove licensed identifiers from the unpublished commits before pushing/merging, or document applicable redistribution permission. This job does not edit that branch or its history. |
| Release gate | `dbceec2`; `web/viewfinder.js` | The current in-app dressing badge is visible, but saved JPEG grabs do not burn that badge into pixels. A shared image could lose the distinction between a real room and generated dressing. PR #31 proposes the export-label fix; its merged browser result is not established by this audit. | Verify the saved image after the human merges the fix before approving publication. Private recordings and images remain private unless a human approves them. |
| Informational, cleared pattern hit | `9131594`; `web/vendor/spark/spark.module.min.js` | Four credential-shaped substrings occur inside an embedded binary/base64 payload. Context is compiled vendor content, not credential assignments. No exact current local credential value matched. This is a pattern false positive, not evidence of a leaked access key. | Retain the vendor's license/attribution; no key revocation is justified by these pattern hits alone. |
| Informational, cleared assignment hit | `5a38d63`; `index/tests/test_production.py` | The long secret-shaped literal is a synthetic sentinel in `test_provider_failure_is_sanitized_and_never_fabricates_property_evidence`; the test asserts it cannot enter the response. The value is omitted. | Retain the sanitization regression. |
| Informational, fixture data | `4bc66d9`, `d3ab730`, `e3ee0e1`, `ec0d183`; `mocks/*.json`, `mocks/events.jsonl`, `agent/eval/{scenes,labels.template}.jsonl` | JSONL/data-shaped files are authored scenes, synthetic output fixtures and label templates. Mock addresses/IDs are declared invented in `mocks/README.md`; no exact private demo or join address match was found. They are not the private labeled evaluation export. | Keep their fixture provenance; do not replace them with real rows. |
| Informational, fixture images | `e3ee0e1`; `mocks/img/*.jpg` | All fifteen historical fixture image blobs were visually inspected in a private contact sheet. Every one is a text card marked synthetic and “Not a real building photograph.” The generator is `scripts/make_mock_images.py`. | No licensed building imagery was identified in these images. |
| Informational, vendor images/contact attribution | `de84d15`, `d871894`; `web/vendor/leaflet/` | Remaining image candidates are Leaflet map-control/marker assets. Email matches are vendor-author attribution, not property-owner contact records. Preserve the packaged license. | No removal requested by this audit. |
| Informational, synthetic contact test | `7143d3a`, `9c0f7a5`, `1a8a90b`; `data/tests/test_costar_live.py` | Phone/contact candidates belong to deliberate privacy-sentinel fixtures that test withholding contact fields. Values are omitted here. No actual owner contact was identified. | Retain the regression coverage. |

## Method and coverage

The scan reads Git object history, not only the working tree. It inventories every local and fetched remote branch with `git for-each-ref`, all reachable commits/blobs with `git rev-list --objects --all` and `git cat-file`, and every historical path with recursive `git ls-tree`. Blob aliases are checked so renamed paths cannot evade the path inventory. It includes pending local World Labs history read-only, plus the active Job 8 branches, existing lane branches and independent audit branches.

Checks include credential provider patterns, private-key delimiters, literal long key/token/password assignments, exact current local credential values (compared in memory; never printed or copied into findings), `.env` and key-file paths, `cache/`, data and archive formats, JSONL, image files, email/phone/address patterns, and exact licensed identifier/address cross-checks. The private demo file supplies nine property identifiers; their nine street addresses are resolved locally from the join. The broader check covers all 3,288 join property identifiers and 3,261 distinct address strings. No source rows, contact values or credential values are emitted by this report.

No tracked `.env`, private `cache/` path, parquet/CSV/XLSX/array/splat/archive/key file was found in the historical path inventory. No exact current local credential value or private demo identifier/address matched. No broader exact join street-address match was found. The known-property-ID matches are the pending-branch finding above. Numeric coincidences, synthetic addresses and vendor attribution were separated from actual private-source matches.

The audit is bounded: it covers locally available/fetched reachable Git history at the recorded refs. It does not inspect deleted/unfetched remote refs, GitHub issues/attachments/actions artifacts, secrets no longer known locally, arbitrary encodings, or OCR hidden in every binary. It cannot establish sponsor redistribution rights. Git author identities are ordinary repository metadata, not evidence of property-owner contact leakage. A clean pattern scan is not a guarantee of no secrets.

Private scan evidence is under `cache/demo-checks/job8-audit/` (ignored). It includes object/path inventories, redacted candidate findings, exact-credential match counts and the fixture contact sheet. None belongs in the public repository. Repeat the scan after new World Labs or other branch commits and before publishing any private media. The current branch snapshots are listed below.

## Masthead verification

The main app now has semantic “Location scouting | Director's Room” navigation with `aria-current="page"` and the existing `--accent` underline. Chromium checks at 1440×900, 1280×720 and 390×844 found no horizontal overflow or JavaScript errors; both links retain a 44-pixel target height. All three private screenshots were visually checked. Evidence: `cache/demo-checks/masthead/20261114T224033Z/report.json` and adjacent PNGs. This check used explicit mocks and made no live model requests.

## History snapshot

Closing content pass: 1439 reachable objects, 685 unique blobs. Complete historical path pass: 185 commits, 279 distinct paths, no private/data-output path hits. No additional sensitive-value category appeared in the closing content pass. Credential assignments also cleared one synthetic sanitization-test sentinel listed above.

| Ref | Commit |
| --- | --- |
| `dev` | `5a449bc` |
| `director-restyle` | `6ba671b` |
| `dressed-set` | `e93ad59` |
| `job8-judge-path` | `dbceec2` |
| `job8-public-audit` | `43d380e` |
| `job8-stage` | `dbceec2` |
| `job8-submission-story` | `b89293b` |
| `lane-b` | `9bcc444` |
| `lane-c` | `e1fbcea` |
| `lane-d` | `acfaefb` |
| `main` | `6928661` |
| `review/lane-a-3` | `dcba573` |
| `viewfinder` | `6660265` |
| `origin` | `360b646` |
| `origin/ai/claude-release-audit` | `6001063` |
| `origin/claude/messaging-bridge` | `be1c907` |
| `origin/cursor/audit-index-tests-24cf` | `25a6654` |
| `origin/cursor/demo-review-005d` | `2c2b57f` |
| `origin/cursor/director-audit-tests-e463` | `7d11dc0` |
| `origin/cursor/grok-production-audit-2876` | `c20680e` |
| `origin/cursor/grok-release-audit-a9d3` | `b89d4f2` |
| `origin/dev` | `dbceec2` |
| `origin/director-restyle` | `6ba671b` |
| `origin/dressed-set` | `2a997c9` |
| `origin/fix/windows-verification` | `bece229` |
| `origin/job8-submission-story` | `b89293b` |
| `origin/lane-a` | `0bdc5e2` |
| `origin/lane-b` | `d5c6581` |
| `origin/lane-b-fixes` | `2215d57` |
| `origin/lane-c` | `e1fbcea` |
| `origin/lane-d` | `4d6ae8a` |
| `origin/main` | `360b646` |
| `origin/viewfinder` | `6660265` |
