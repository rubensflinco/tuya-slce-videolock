---
name: ha-integration-package
description: >-
  Empacota e valida a integração slce_videolock para HACS/instalação manual
  (manifest, hacs.json, zip). Use ao preparar release ou checar estrutura.
---

# Empacotar integração HA

## Validar

```bash
python scripts/check_manifest.py
```

## Estrutura HACS

- Domain folder: `custom_components/slce_videolock/`  
- `manifest.json` com `domain`, `version`, `config_flow`, `documentation`, `issue_tracker`  
- `hacs.json` na raiz  

## Zip de release (HACS / Marketplace)

Com `zip_release: true` no `hacs.json`, o asset `slce_videolock.zip` é extraído **direto** em
`/config/custom_components/slce_videolock/`. Os arquivos devem ficar na **raiz do zip**
(`manifest.json`, `__init__.py`, …) — **sem** pasta `slce_videolock/` dentro do arquivo.

```bash
# Python (Windows/Linux)
python - <<'PY'
import zipfile
from pathlib import Path
root = Path("custom_components/slce_videolock")
out = Path("dist/slce_videolock.zip")
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            zf.write(path, path.relative_to(root).as_posix())
print(out)
PY
```

Tag da release = `version` do `manifest.json` (ex.: `0.7.1`, sem divergir).

Instalar manual: extrair o zip em `/config/custom_components/slce_videolock/` e reiniciar HA.
