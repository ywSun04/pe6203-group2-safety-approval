# Fix for fixture hashes after Git checkout

Member 2 found that the frozen main commit
`ccf3051c96505f655de169e7613ab6722fec6a4c` fails two tests in an LF checkout.
I reproduced **263 passed, 2 failed** under Python 3.11.18. All 20 active
fixtures have LF bytes in Git, but their manifest entries match CRLF bytes.
The earlier Windows checks passed because Git converted the files to CRLF.
That left a gap in my original validation.

## Applied fix

The core fix is Member 2's supplied `attack-hash-If-fix.patch`:

```gitattributes
attacks/member5/*.json text eol=lf
configs/member5/*.json text eol=lf
```

The manifest now records SHA-256 of the actual LF file bytes. I checked all 20
values against the patch and all 22 fixture Git blobs against the old main
commit, including the two retired fixtures. Fixture blobs and parsed payloads
are unchanged. The only manifest value changes are its 20 file hashes. The
official evaluators, Gate, policies, Reviewer and cost accounting are unchanged.

The patch supplied by Member 2 has SHA-256
`ad133fa58b2c4ed815fa429592e29b1c105d11880cad7fcd1cd9f50e184e59b7`.
The file check still hashes raw bytes; it does not silently accept alternate
line endings or weaken tamper detection.

## Checks

- The original 265 tests pass after applying the fix. Two added regression
  cases bring the full Python 3.11.18 suite to **267 passed**.
- The new test commits the real fixture/configuration files to a temporary
  repository, then checks them out with Git under both `core.autocrlf=false`
  and `core.autocrlf=true`. It checks LF bytes, all 20 manifest hashes and stable
  manifest bytes. It uses `checkout-index`, with no network or shell calls.
- All 20 pairs again pass offline loading, reference delivery, reference utility
  and the original official success predicates. These are not model attack runs.
- The validation JSON and task/attack matrix have been regenerated. Serialized
  tool-output hashes describe the new replay; they are not fixture identifiers
  or a claim that every replay output is byte-identical across processes.

## Freeze and plan impact

The manifest changed, so the attack-pack hash also changes. The corrected pack
SHA-256 is
`a785947a3155e002580f729c1491f792e13f2a358254301ba44597215a7aa63b`.
Its ID is `member5-fixed20-a785947a3155`. The runner's hash of each parsed
payload map is unchanged, since the JSON values are unchanged.

The saved candidate coverage uses the corrected pack and is explicitly marked
as a preview pending this fix and a new freeze. Its `integration_commit` records
the inspected pre-fix base, not a new runnable freeze. All 2,400 slots remain
unrun. Do not use the old pack, edit historical run manifests to fit the new
pack, or start formal runs from the invalidated `ccf3051` freeze.

After Member 1 merges the fix and announces the new main SHA, Members 2 and 6
should check out that SHA, rerun the tests and regenerate the plan into a new
folder. Record the new commit, pack hash, unchanged Reviewer v2 prompt hash,
timeouts and dependency versions. No model API was called for this repair.
