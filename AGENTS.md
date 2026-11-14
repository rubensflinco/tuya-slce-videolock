# Briefing para agentes (Cursor / cloud / Devin)

Você está no repositório **`slce-videolock`**: integração Home Assistant custom que unifica a **Fechadura SL-CE (Wi-Fi) videolock** num **único device**.

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

- [ ] Scaffold HA válido (já parcialmente criado)  
- [ ] Config flow: Access ID, Access Secret, Device ID, (opcional) region  
- [ ] Entity `lock` funcional (dry-run / mock se sem credenciais)  
- [ ] Entity `camera` ou stub documentado se stream exigir ffmpeg/SDK extra  
- [ ] Sensors: battery, online, doorbell (+ best-effort last unlock)  
- [ ] `hacs.json` + README instalação  
- [ ] Skill `.cursor/skills/slce-videolock-dev/SKILL.md` atualizada se o fluxo mudar  

## Skills do repo

| Skill | Quando usar |
|-------|-------------|
| `slce-videolock-dev` | Desenvolver / estender a integração |
| `tuya-slce-device` | Consultar ficha do aparelho e DPs |
| `ha-integration-package` | Empacotar zip / HACS / validar manifest |

## Fora de escopo (MVP)

- Controle 100% local (LAN) da tranca  
- Substituir Tuya oficial para *todos* os devices da conta  
- UI Lovelace custom
