# Deferred work

- source_plan: `_bmad-output/initiative-janbot/epic-ingestion/story-config-contract-corpus-root-hardening-plan.md`
  summary: Define the symlink policy for the fail-closed scope filter before entry 2.4 builds it, since `config` canonicalizes paths with `.resolve()` while the public corpus folder holds symlinked files.
  evidence: `src/janbot/config.py` `_resolve_path` returns `Path(value).expanduser()...resolve()` (follows symlinks); the epic's public-scope decision makes `~/org/h1_horizon/public_profile_org/` contain symlinks to real files in `~/org` (which also holds private notes); a naive `is_relative_to(config.corpus_path)` check on a symlink-resolved file can reject legitimate public files or mis-point the whitelist. Entry 2.4 must decide (link path vs resolved target) and may read the configured literal rather than the resolved root.
