---
name: ha-integration-package
description: >-
  Empacota e valida a integração slce_videolock para HACS/instalação manual
  (manifest, hacs.json, zip). Use ao preparar release ou checar estrutura.
  Para publicar no GitHub, use também a skill ha-release.
---

# Empacotar integração HA

Para **publicar release** (tag + GitHub + Marketplace), use a skill
[`ha-release`](../ha-release/SKILL.md) — este arquivo só cobre validação/zip.

## Validar

```bash
python scripts/check_manifest.py
python scripts/build_release_zip.py
```

## Estrutura HACS

- Domain: `custom_components/slce_videolock/`
- `manifest.json` com `domain`, `version` (sem prefixo `v`), `config_flow`, …
- `hacs.json` na raiz com **`zip_release: true`** e `filename: "slce_videolock.zip"`

## Zip de release

Gerar só com:

```bash
python scripts/build_release_zip.py
```

Arquivos na **raiz** do zip. Sem pasta `slce_videolock/` aninhada.
