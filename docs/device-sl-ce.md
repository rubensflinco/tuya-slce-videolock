# Fechadura Inteligente SL-CE (Wi-Fi) — ficha técnica (RuGiu)

Aparelho real em uso no Apto Bom Retiro (São Paulo). Use estes IDs ao depurar Cloud API / DPs / câmera.

## Identidade

| Campo | Valor |
|-------|--------|
| Nome Smart Life | Fechadura Inteligente SL-CE (Wi-Fi) |
| Marca / linha | Novadigital / Tuya · modelo comercial **SL-CE Elegance** (videolock) |
| Device ID (Tuya) | `eba0b0f3d9b38977ed8b0a` |
| Categoria Tuya | `videolock` (também aparece em docs de video lock / intercom door lock) |
| Product name (HA) | Fechadura Inteligente SL-CE (Wi-Fi) |
| Área HA | Corredor 1 |
| IP LAN (reserva Omada) | `10.0.1.143` |
| MAC | `BC-35-1E-CB-BD-33` (`wlan0`) |

## O que funciona / não funciona

| Caminho | Resultado observado |
|---------|---------------------|
| **Tuya Local (LAN)** | Falha típica — videolock não fecha bem protocolo/local_key |
| **Tuya oficial (HA)** | Sem plataforma `lock`; câmera/status limitados |
| **Xtend Tuya** | Câmera stream + muitos `event.*` (unlock_*, campainha, alarm) + bateria; `operate_lock` **não** destranca de verdade |
| **Tuya Smart Lock** | `lock.unlock` / `lock.lock` via Cloud ticket API — **funciona** |
| **Tuya Lock Monitor** | Mais sensores (online, doorbell binary, last fingerprint/card/password, pending unlock…) — **não** destranca nem tem stream |

## Entidades observadas no HA (antes da unificação)

### Xtend Tuya (`xtend_tuya`)

- `camera.fechadura_inteligente_sl_ce_wi_fi` — stream (idle / proxy)
- `lock.fechadura_inteligente_sl_ce_wi_fi_operate_lock` — **não** destranca
- `sensor.fechadura_inteligente_sl_ce_wi_fi_bateria` — DP tipicamente `residual_electricity`
- `binary_sensor.fechadura_inteligente_sl_ce_wi_fi_lock_status`
- Events: `campainha`, `lock_alarm`, `lock_record`, `lockout_alarm`, `opened_from_inside`, `unlock_user_*` (card, dynamic, face, finger_vein, fingerprint, hand, key, offline_password, password, phone, temporary, voice), `device_notifications`

### Tuya Smart Lock (`tuya_smart_lock`)

- `lock.corredor_1_fechadura_inteligente_sl_ce_wi_fi` — **destranca de verdade** (Cloud ticket)

### Tuya Lock Monitor (`tuya_lock_monitor`) — entry `Tuya Lock (eba0b0f3d9b38977ed8b0a)`

- `lock.*_door_lock` — **não** destranca (desabilitar se unificar)
- Binary: `deadbolt_reverse_lock`, `doorbell`, `duress_hijack_alert`, `normally_open_mode`, `online`
- Sensors: `battery`, `app_unlocks`, `last_alarm`, `last_card_unlock`, `last_contact`, `last_fingerprint_unlock`, `last_password_unlock`, `pending_unlock_requests`, `temporary_code_unlocks`

## DPs / códigos Cloud típicos (videolock / ms)

Baseado em logs Tuya + entidades Xtend/Monitor. Confirmar no IoT Platform → Debug Device / diagnostics HA.

| Código / DP (nome) | Uso |
|--------------------|-----|
| `residual_electricity` | Bateria % |
| `doorbell` | Campainha |
| `hijack` / duress | Alerta coação |
| `alarm_lock` | Alarme |
| `unlock_fingerprint`, `unlock_password`, `unlock_card`, `unlock_app`, `unlock_temporary`, `unlock_dynamic`, `unlock_face`, `unlock_key`, `unlock_phone_remote`, … | Eventos de abertura |
| `unlock_request` | Pedido remoto pendente |
| `lock_motor_state` / `lock_status` | Estado (nem sempre atualiza bem em Wi‑Fi auto-lock) |
| Remote unlock | **Smart Lock Open Service** (ticket) — não é DP simples de switch |

Docs oficiais Tuya (video lock DPs):  
https://developer.tuya.com/en/docs/iot/intercom-door-lock?id=Kaxg4x1dt7a6j

## Credenciais necessárias (Cloud)

Mesmo padrão do Tuya Smart Lock:

1. Projeto em [iot.tuya.com](https://iot.tuya.com)  
2. APIs: **IoT Core** + **Smart Lock Open Service** (renovar trial ~6 meses)  
3. Access ID / Access Secret  
4. Device ID `eba0b0f3d9b38977ed8b0a` vinculado à conta Smart Life  

LAN: IP `.143` só para discovery/diagnóstico — **controle de tranca é cloud-only**.

## Produto comercial (contexto)

Busca: “Novadigital SL-CE Elegance” — Wi‑Fi, câmera, Face ID, biometria, bateria recarregável, Smart Life/Tuya.
