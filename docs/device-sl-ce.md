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

## Entidades slce_videolock (v0.5.0+) — integração unificada

Todas as entidades num único device. **Recomendado**: remover Xtend/SmartLock/LockMonitor após configurar esta integração.

### Lock
- `lock.fechadura_inteligente_sl_ce_wi_fi` — **destranca de verdade** (Cloud ticket)

### Camera
- `camera.fechadura_inteligente_sl_ce_wi_fi` — stream RTSP/HLS via Tuya Cloud

### Binary Sensors (com auto-reset para valores sticky)
- `binary_sensor.*_online` — conectividade
- `binary_sensor.*_campainha` — ON por 2s depois auto-reset
- `binary_sensor.*_alerta_de_coacao` — hijack/duress, auto-reset
- `binary_sensor.*_porta_destrancada` — estado do motor

### Sensors
- `sensor.*_bateria` — % bateria
- `sensor.*_ultima_digital` — último unlock_fingerprint
- `sensor.*_ultima_senha` — último unlock_password
- `sensor.*_ultimo_cartao` — último unlock_card
- `sensor.*_ultimo_reconhecimento_facial` — último unlock_face
- `sensor.*_ultima_chave_mecanica` — último unlock_key
- `sensor.*_ultimo_desbloqueio_remoto` — último unlock_phone_remote
- `sensor.*_ultima_senha_dinamica` — último unlock_dynamic
- `sensor.*_aberturas_pelo_app` — contador unlock_app
- `sensor.*_codigos_temporarios_usados` — contador unlock_temporary
- `sensor.*_pedidos_de_abertura_pendentes` — unlock_request
- `sensor.*_ultimo_alarme` — último alarm_lock
- `sensor.*_total_de_toques_campainha` — contador (incrementa em cada toque)
- `sensor.*_total_de_alarmes` — contador
- `sensor.*_total_de_desbloqueios` — contador
- `sensor.*_ultima_campainha` — timestamp do último toque
- `sensor.*_ultimo_alarme_hora` — timestamp do último alarme
- `sensor.*_ultimo_desbloqueio_hora` — timestamp do último unlock

### Events (plataforma event do HA — ideal para automações)
- `event.*_campainha` — dispara `ring` a cada toque (não fica stuck)
- `event.*_desbloqueio` — dispara tipo do método: `fingerprint`, `face`, `password`, `card`, `key`, etc.
- `event.*_alarme` — dispara tipo do alarme: `wrong_finger`, `wrong_password`, `pry`, `duress`, etc.

## DPs / códigos Cloud típicos (videolock / ms)

Baseado em logs Tuya + entidades Xtend/Monitor. Confirmar no IoT Platform → Debug Device / diagnostics HA.

| Código / DP (nome) | Uso | Entidade HA (v0.5.0+) |
|--------------------|-----|----------------------|
| `residual_electricity` | Bateria % | `sensor.*_bateria` |
| `doorbell` | Campainha (sticky, auto-reset 2s) | `binary_sensor.*_campainha` + `event.*_campainha` |
| `hijack` | Alerta coação (sticky, auto-reset 2s) | `binary_sensor.*_alerta_de_coacao` + `event.*_alarme` |
| `alarm_lock` | Alarme (wrong_finger, pry, etc.) | `sensor.*_ultimo_alarme` + `event.*_alarme` |
| `unlock_fingerprint` | Desbloqueio por digital | `sensor.*_ultima_digital` + `event.*_desbloqueio` |
| `unlock_password` | Desbloqueio por senha | `sensor.*_ultima_senha` + `event.*_desbloqueio` |
| `unlock_card` | Desbloqueio por cartão | `sensor.*_ultimo_cartao` + `event.*_desbloqueio` |
| `unlock_face` | Desbloqueio facial | `sensor.*_ultimo_reconhecimento_facial` + `event.*_desbloqueio` |
| `unlock_key` | Chave mecânica | `sensor.*_ultima_chave_mecanica` + `event.*_desbloqueio` |
| `unlock_app` | Desbloqueio pelo app (contador) | `sensor.*_aberturas_pelo_app` |
| `unlock_temporary` | Senha temporária (contador) | `sensor.*_codigos_temporarios_usados` |
| `unlock_dynamic` | Senha dinâmica | `sensor.*_ultima_senha_dinamica` + `event.*_desbloqueio` |
| `unlock_phone_remote` | Desbloqueio remoto celular | `sensor.*_ultimo_desbloqueio_remoto` + `event.*_desbloqueio` |
| `unlock_request` | Pedido remoto pendente | `sensor.*_pedidos_de_abertura_pendentes` |
| `lock_motor_state` | Estado motor (True=destravado) | `binary_sensor.*_porta_destrancada` |
| Remote unlock | **Smart Lock Open Service** (ticket) | `lock.*` (unlock/lock) |

### Endpoints de logs usados (v0.5.0+)

| Endpoint | Uso |
|----------|-----|
| `/v1.0/devices/{id}/door-lock/open-logs` | Histórico de desbloqueios com timestamp |
| `/v1.0/devices/{id}/door-lock/alarm-logs` | Histórico de alarmes com timestamp |
| `/v1.0/devices/{id}/door-lock/records` | Registros combinados (unlock + alarm) — preferido para videolock |

Docs oficiais Tuya (video lock DPs):  
https://developer.tuya.com/en/docs/iot/intercom-door-lock?id=Kaxg4x1dt7a6j

### Comportamento de polling (v0.5.0+)

- **Intervalo**: 15 segundos (antes era 60s)
- **Auto-reset**: `doorbell` e `hijack` resetam para OFF após 2s (evita stuck)
- **Detecção de eventos**: Compara status anterior + busca logs para disparar `event.*`
- **Contadores**: Incrementam mesmo se o valor do DP não mudar (útil para wrong_finger repetido)

## Credenciais necessárias (Cloud)

Mesmo padrão do Tuya Smart Lock:

1. Projeto em [platform.tuya.com](https://platform.tuya.com/)  
2. APIs: **IoT Core** + **Smart Lock Open Service** (renovar trial ~6 meses)  
3. Access ID / Access Secret  
4. Device ID `eba0b0f3d9b38977ed8b0a` vinculado à conta Smart Life  

LAN: IP `.143` só para discovery/diagnóstico — **controle de tranca é cloud-only**.

## Produto comercial (contexto)

Busca: “Novadigital SL-CE Elegance” — Wi‑Fi, câmera, Face ID, biometria, bateria recarregável, Smart Life/Tuya.
