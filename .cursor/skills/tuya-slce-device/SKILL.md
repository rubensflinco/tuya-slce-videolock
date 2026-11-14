---
name: tuya-slce-device
description: >-
  Ficha técnica da Fechadura Inteligente SL-CE (Wi-Fi) videolock do apto RuGiu
  (IDs Tuya, IP, MAC, o que cada addon faz). Use ao mapear DPs, depurar unlock
  ou câmera deste modelo.
---

# Device SL-CE

Fonte canônica: `docs/device-sl-ce.md`.

## Resumo rápido

- **Device ID:** `eba0b0f3d9b38977ed8b0a`  
- **Categoria:** `videolock`  
- **IP/MAC:** `10.0.1.143` / `BC-35-1E-CB-BD-33`  
- **Unlock real:** só via Smart Lock Cloud API (ticket)  
- **Stream:** Xtend Tuya já prova que a cloud entrega câmera  
- **LAN tuya_local:** não confiar para tranca  

## Ao buscar na web / IoT

Priorizar:

1. Tuya Developer — intercom / video door lock DPs  
2. Issues em `tuya-smart-lock` com `videolock`  
3. Diagnostics JSON do device no HA (`product_id`, `status`, `function`)  

Se o usuário fornecer novo diagnostics, atualizar `docs/device-sl-ce.md` nesta mesma tarefa.
