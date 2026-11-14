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

## Zip manual

```bash
cd custom_components
zip -r ../dist/slce_videolock.zip slce_videolock -x "*.pyc" "*__pycache__*"
```

Instalar: extrair `slce_videolock/` em `/config/custom_components/` e reiniciar HA.
