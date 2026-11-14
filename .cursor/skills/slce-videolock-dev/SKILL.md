---
name: slce-videolock-dev
description: >-
  Desenvolve a integração Home Assistant slce_videolock (unlock + câmera +
  sensores da Fechadura SL-CE). Use ao implementar, depurar ou estender o
  custom_component; sempre cruzar com xtend_tuya, tuya-smart-lock e
  ha-tuya-lock-monitor.
---

# SL-CE Videolock — desenvolvimento

## Antes de mudar código

1. Ler `AGENTS.md` e `docs/device-sl-ce.md`  
2. Ler `docs/references.md` e abrir os 3 repos referência  
3. Manter **um device** no `device_registry` por fechadura  

## Repos referência (clone se necessário)

```bash
# opcional, pasta /tmp ou sibling
git clone --depth 1 https://github.com/nicolasglg/tuya-smart-lock.git
git clone --depth 1 https://github.com/azerty9971/xtend_tuya.git
git clone --depth 1 https://github.com/crestall/ha-tuya-lock-monitor.git
```

Mapear:

| Feature | Onde olhar primeiro |
|---------|---------------------|
| Ticket unlock | `tuya-smart-lock` → API lock / ticket |
| Camera entity | `xtend_tuya` → camera platform / videolock |
| Battery, doorbell, last_* | `ha-tuya-lock-monitor` → sensors |

## Estrutura alvo

```
custom_components/slce_videolock/
  __init__.py
  manifest.json
  const.py
  config_flow.py          # valida token + device info
  tuya_api.py             # ticket unlock + status (MIT refs)
  coordinator.py          # cloud poll ~60s
  entity.py               # DeviceInfo (DOMAIN, device_id)
  lock.py                 # ticket unlock/lock
  camera.py               # stub — ver docs/camera-todo.md (GPL xtend)
  sensor.py
  binary_sensor.py
  strings.json
  translations/en.json
```

Unlock real = Cloud ticket (`TICKET_ENDPOINT` → `DOOR_OPERATE_ENDPOINT`), nunca LAN.
Câmera: não copiar código GPL do xtend_tuya; implementar allocate OpenAPI depois.

## Device ID de teste (RuGiu)

`eba0b0f3d9b38977ed8b0a` — não commitar Access Secret.

## Checklist PR

- [ ] Unlock path documentado (cloud ticket)  
- [ ] Entidades no mesmo device  
- [ ] Sem secrets no git  
- [ ] Versão em `manifest.json` bump  
- [ ] README atualizado
