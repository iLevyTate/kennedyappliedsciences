Website for Kennedy Applied Sciences Research Group, the public-facing brand of Kennedy Applied Sciences, Inc.

## Two sites, one codebase

This repo and its partner (named in `.github/site-sync.json`) serve the two
Kennedy Applied Sciences websites from the same files.
Every push to `main` in either repo is mirrored into the other by
`.github/workflows/sync.yml`, so edit whichever site you like and both update.

- The domain is swapped automatically everywhere it appears (links, emails, text).
- Content for one site only goes between `<!-- per-site:NAME -->` and
  `<!-- /per-site:NAME -->`. Keep the markers on both sites (empty where unused);
  each site keeps its own text between them.
- Whole files or folders for one site only go in that site's `local_only` list in
  `.github/site-sync.json`. `CNAME` is never synced.

Setup: both repos need a `SITE_SYNC_TOKEN` Actions secret holding a fine-grained
personal access token with access to both repos and the **Contents** and
**Workflows** permissions set to read and write.
