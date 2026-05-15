# Repository Hygiene Checklist

This repository is currently treated as a paper-first research artifact. Before
publishing, sharing, or submitting it, apply this checklist.

## Required Before Publication

- Remove private keys and cloud credentials from the repository history.
- Rotate any AWS key pair or credential that was ever committed locally.
- Use a clean Git root at `CC_research`. This workspace now has a nested Git
  repository initialized at `CC_research`; the older parent-root history at
  `C:/Users/Admin` should not be used for publication.
- Run the local secret scanner:

```powershell
python -m raasa.scripts.secret_scan --root .
```

- Run the test suite:

```powershell
python -m pytest tests -q
```

## Clean-Repo Migration

Do this manually for any final publication copy, because moving `.git` from a
user home directory can destroy unrelated history.

1. Start from the clean `CC_research` Git root or create a fresh external clone.
2. Copy only the curated `CC_research` project files into it.
3. Exclude local result bulk, caches, keys, virtual environments, and generated
   archives.
4. Run the secret scanner and tests before the first publication commit.

## Current Policy

No PEM files, private keys, `.env` files, AWS credential files, large result
archives, or local runtime logs should be committed. Evidence bundles can be
kept locally and summarized in `docs/evidence_index.md`; only curated summaries
should be committed unless a reviewer explicitly needs a raw artifact.
