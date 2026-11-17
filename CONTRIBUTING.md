# Contributing

Thanks for helping **Tuya SL-CE Videolock**.

## Development

1. Clone the repo and work under `custom_components/slce_videolock/`.
2. Run checks:

```bash
python scripts/check_manifest.py
python -m unittest discover -s tests -v
```

3. Keep identifiers and code comments in English; user-facing strings may be PT-BR in `translations/`.

## Pull requests

- One concern per PR when possible
- Do not commit secrets, Access ID/Secret, or live device credentials
- Match existing style; prefer small, focused diffs
- Update `README.md` when user-visible behavior changes (it is also the Marketplace description via `render_readme`)

## Releases

Only maintainers cut releases. Flow: skill `.cursor/skills/ha-release/SKILL.md` (bump → README → zip → tag → `gh release`).

## Catalog (Marketplace / HACS default)

See [`docs/marketplace-catalog.md`](docs/marketplace-catalog.md). Submissions to [`hacs/default`](https://github.com/hacs/default) must come from the repository owner and only after CI is green.
