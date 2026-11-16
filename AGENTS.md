# Briefing para agentes (Cursor / cloud / Devin)

Você está no repositório **`tuya-slce-videolock`**: integração Home Assistant custom que unifica a **Fechadura SL-CE (Wi-Fi) videolock** num **único device**.

## Missão

Implementar `custom_components/slce_videolock` com:

1. **`lock`** — unlock/lock via Tuya Smart Lock Cloud API (ticket), como [tuya-smart-lock](https://github.com/nicolasglg/tuya-smart-lock)  
2. **`camera`** — stream da videolock, como [xtend_tuya](https://github.com/azerty9971/xtend_tuya)  
3. **Sensores / binary_sensors / events** — bateria, online, doorbell, last unlock methods, alarms, como [ha-tuya-lock-monitor](https://github.com/crestall/ha-tuya-lock-monitor)  

Tudo no **mesmo** `device_id` do registry.

## Device alvo (produção RuGiu)

Ler obrigatoriamente: [`docs/device-sl-ce.md`](docs/device-sl-ce.md)

- Device ID: `eba0b0f3d9b38977ed8b0a`  
- IP: `10.0.1.143` · MAC `BC-35-1E-CB-BD-33`  
- Categoria: `videolock`  
- LAN/`tuya_local`: **não** usar como caminho principal de unlock  

## Referências de código

Ver [`docs/references.md`](docs/references.md). Antes de codificar unlock/câmera/sensores, **buscar e ler** os trechos equivalentes nos 3 repos (clone shallow se precisar).

## Constraints

- Python async Home Assistant (`config_flow`, `DataUpdateCoordinator` ou MQTT/push se o SDK permitir)  
- `manifest.json` com `config_flow: true`, `iot_class` adequado (`cloud_polling` ou `cloud_push`)  
- Uma entry = um device SL-CE (ou hub multi-device depois; MVP = um device_id)  
- Não copiar código GPL/licença incompatível sem respeitar licença; MIT/Apache preferível; se copiar, atribuir  
- PT-BR ok em README; código/idents em inglês  
- Testes unitários dos parsers de DP / ticket se possível sem rede  

## Entregáveis MVP

- [x] Scaffold HA válido  
- [x] Config flow: Access ID, Access Secret, Device ID, region, stream_type  
- [x] Entity `lock` via Cloud ticket  
- [x] Entity `camera` via stream allocate (HLS/RTSP) + ffmpeg  
- [x] Sensors: battery, online, doorbell (+ last unlock / alarms)  
- [x] `hacs.json` + README instalação  
- [ ] Skill `.cursor/skills/slce-videolock-dev/SKILL.md` atualizada se o fluxo mudar  

## Skills do repo

| Skill | Quando usar |
|-------|-------------|
| `slce-videolock-dev` | Desenvolver / estender a integração |
| `tuya-slce-device` | Consultar ficha do aparelho e DPs |
| `ha-integration-package` | Validar manifest / estrutura HACS |
| `ha-release` | **Subir versão** (tag + zip_release + `gh release`) |

Release: rule `.cursor/rules/ha-release.mdc` + skill `ha-release`.
Ao pedir **subir versão**: commit + push + GitHub Release (nunca só localhost).
Sempre atualizar `README.md` (é o README do Marketplace/HA via `render_readme`).

## Fora de escopo (MVP)

- Controle 100% local (LAN) da tranca  
- Substituir Tuya oficial para *todos* os devices da conta  
- UI Lovelace custom
