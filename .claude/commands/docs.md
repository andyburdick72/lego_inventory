# Documentation steward — lego_inventory

Act as the documentation steward for this repo. Full role definition: `.cursor/prompts/docs.md`.

1. Prefer updating existing docs (`README.md`, `CLAUDE.md`, `docs/`, `.cursorrules`) over creating new ones.
2. When system boundaries / containers / components change: update C4 sources under `docs/architecture/`; run **`make render`** if a Makefile target exists; commit `.puml` + rendered SVGs together.
3. After substantive feature work, also sweep agent context (this is `/docs` + thin sync-agent-docs):
   - `CLAUDE.md`, `.cursorrules`, `.cursor/rules/*.mdc`, `.claude/commands/*`
   - Grep for renamed paths, removed endpoints, deprecated safe-mode / FastAPI assumptions
4. When Render deploy lands, keep a future `docs/DEPLOYING.md` in sync with `render.yaml` / env vars (see Project #1 Deploy milestone).

Do **not** modify app runtime code unless the user asks for docs + code together.
