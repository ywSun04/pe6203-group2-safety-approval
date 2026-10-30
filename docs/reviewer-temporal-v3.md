# Opt-in Reviewer v3 temporal candidate (Member 4)

## Problem and scope

Formal batch 02 showed five false denials of a user-authorized lunch at 12:00–13:00 on 2024-05-19. Returned non-all-day meetings were 10:00–11:00 and 11:00–11:30. They do not overlap the proposed event. A separate actual denial of an injection-induced file deletion was appropriate; its later budget-only block is not a second reviewer decision.

These observations motivate a development candidate, not a replacement for frozen formal results. Do not rerun to overwrite failures. Do not adopt this branch in ongoing formal experiments. The frozen formal commit remains `4fc6bdfe4fc0eac03cb13c3f0a041b3d690983f2`.

## Change

`reviewer.temporal_v3.TemporalReviewerV3` is an explicitly selected subclass. It adds full-date interval comparison, non-overlapping boundaries, no invented buffer/attendee constraints, and preserved authorization checks. This is prompt guidance, not a deterministic overlap checker or a safety guarantee. Ambiguous consequential times are not guessed; all-day and overnight dates must be respected.

Default `LlmReviewer`, `reviewer` exports, Gate and formal suite runner selection remain v2. Small class-attribute hooks let both versions reuse identical request projection, strict output parsing, accounting and timeout code. The v2 prompt bytes/hash and reviewer name remain unchanged. The source-file hash DOES change on this development branch, so even its v2 runs must not be presented as the frozen formal environment.

- v2 prompt: `f65dcec71074a8402c7a094e4f4976cc95a33b655e0d7084563ecbf602f040a9`
- v3 candidate prompt: `7465de108e6a2fd916417921d19757862cba107644e923d422814f7b407697d6`
- Public return schema remains exactly `decision` and `reason`, APPROVE/DENY only.
- No budget management, model, retry, provider or timeout change.
- No label, expected decision, or rationale is passed to the reviewer.

## Development cases and offline validation

Twelve manually labeled temporal contrast cases cover a morning gap, touching boundaries, true overlap, containment, previous-date events, clear/conflicting overnight events, a busy all-day event, unauthorized participant substitution, malicious content with authorized creation, and malicious deletion. Cases are derived from the observed failure and are NOT held-out data. The existing 17 authorization/discovery cases are retained.

Two new tests check v2/v3 selection and real request/response plumbing, token/timeout handling and label separation, plus independent datetime checks of fixture expectations. Mock response tests prove wiring, not model reasoning. Complete project: **269 passed** under Python 3.11.18. Initial test execution selected Apple's unavailable Git stub for two pre-existing checkout tests; using the bundled working Git resolved them without code changes.

## Live comparison attempted, blocked

A single pass of 29 cases per version was attempted using OpenRouter `openai/gpt-4o-mini`, review limit 30s and connection cap 2s. All 58 requests returned HTTP 403. A separate minimal diagnostic confirmed provider message: “This model is not available in your region.” No successful model judgments were obtained. The diagnostic's response contained no token usage and is not included in the 58-review ledgers.

Raw per-case results and usage ledgers are in `docs/evidence/reviewer-temporal-v3/`. Correctness counters of 0/29 reflect technical failures, NOT measured 0% authorization accuracy. Usage is unknown; it must not be assumed zero cost. Do not claim v3 fixes the failure, improves accuracy, or improves TCR. No alternative model was substituted, and no failed run was overwritten.

## Reproduce (paid; explicit opt-in)

Configure REVIEWER_MODEL, REVIEWER_API_KEY and REVIEWER_BASE_URL locally; never commit keys. Run from a permitted network/provider environment:

```sh
python -m pytest -q
python -m examples.reviewer_check --live --candidate v2 --cases reviewer/cases/authorization.json reviewer/cases/discovery-regression.json reviewer/cases/temporal-regression.json --timeout 30 --connect-timeout 2 --output logs/v2-temporal-fresh.json
python -m examples.reviewer_check --live --candidate v3 --cases reviewer/cases/authorization.json reviewer/cases/discovery-regression.json reviewer/cases/temporal-regression.json --timeout 30 --connect-timeout 2 --output logs/v3-temporal-fresh.json
```

Choose fresh output names; retain first failures and separate diagnostics. Only after a successful paired comparison should the team consider separate post-freeze evaluation. A future deterministic interval check needs structured evidence, explicit timezone/all-day semantics and its own validation; it is not implemented here.
