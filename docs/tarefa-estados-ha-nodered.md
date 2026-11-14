# Tarefa: maximizar estados da SL-CE no HA (para Node-RED)

**Prioridade:** alta  
**Origem:** casa RuGiu / `ia-agents-rugiu` — workflows Node-RED (tab Porta + facial → corredor)  
**Device:** `eba0b0f3d9b38977ed8b0a` · IP `10.0.1.143` · ver `docs/device-sl-ce.md`

## Contexto

No Home Assistant (ha-server) usamos esta integração (`slce_videolock`) como fonte da fechadura. Automações no Node-RED dependem de **mudanças de estado confiáveis e momentâneas**. Hoje vários sinais **não disparam** ou ficam **stuck**, então o workflow não funciona.

Problemas observados em produção (2026-11-14):

| Sinal HA | Problema | Impacto Node-RED |
|----------|----------|------------------|
| `binary_sensor.*_campainha` | Cloud deixa `doorbell=true` sem limpar; com poll antigo (~60s) fica stuck `on` | Rising edge off→on quase nunca dispara |
| `sensor.*_ultimo_alarme` | Valor sticky (ex. `wrong_finger`); repetir o mesmo alarme **não** gera `state_changed` | Alarme na porta não re-dispara |
| Unlock facial / digital | Depende de `lock` → `unlocked` (ok às vezes), mas DPs de evento (`unlock_face`, etc.) não viram `event.*` úteis como no Xtend | Facial→lâmpada corredor frágil |
| Polling | Só Cloud status poll; eventos curtos podem ser perdidos entre polls | Campainha/alarme perdidos |

Houve um patch paliativo de pulse-reset na campainha (2s) + poll 15s no HAOS — isso é **workaround**, não a solução correta. A correção canônica deve ficar **neste repo** e ser publicada/instalada no HA.

## Objetivo

Ir até o fundo (docs Tuya, OpenAPI, debug device, engenharia reversa de pacotes Smart Life / referências MIT se necessário) e fazer a integração expor **o máximo possível de estados/eventos** da fechadura no HA, de forma **acionável por automação** (Node-RED / HA automations).

### Estados / eventos que precisamos (mínimo)

1. ✅ **Campainha** — `event.*_campainha` (tipo `ring`) + `binary_sensor` auto-reset 2s
2. ✅ **Alarme / tentativa** — `event.*_alarme` + `sensor.*_total_de_alarmes` (contador)
3. ✅ **Coação / hijack** — `event.*_alarme` (tipo `duress`) + `binary_sensor` auto-reset 2s
4. ✅ **Método de abertura** — `event.*_desbloqueio` (tipos: `face`, `fingerprint`, `password`, `card`, `key`...)
5. ✅ **Lock motor / unlocked / locked** — `binary_sensor.*_porta_destrancada` + `lock.*`
6. ✅ **Pedido de abertura remota** — `sensor.*_pedidos_de_abertura_pendentes`
7. ✅ **Extras** — timestamps (`sensor.*_ultima_*_hora`), contadores totais, logs Tuya API

### Qualidade exigida

- Eventos **momentâneos** não podem depender só de “último valor sticky”  
- Preferir plataforma `event` do HA + sensores com `last_*` **e** timestamp/`event_count`  
- Polling Cloud: reduzir latência **ou** (melhor) canal push/MQTT/message do Tuya se existir para videolock  
- Auto-reset / pulse onde o cloud for sticky (padrão `ha-tuya-lock-monitor`)  
- Documentar DPs mapeados em `docs/device-sl-ce.md`  
- ✅ Bump de versão: `manifest.json` → v0.5.3

**Status:** ✅ Implementado em v0.5.0 · hotfixes **v0.5.1** / **v0.5.2** / **v0.5.3**

### Hotfix v0.5.1 (2026-11-14)

Cloud deixa `doorbell=true` sticky. Em 0.5.0 o coordinator re-disparava `event.*_campainha` a cada poll (~15s) por um cooldown de 5s.  
**Correção:** armar só quando cloud volta a `false`; um único `ring` por sessão sticky; no bootstrap pós-reload não dispara se já estiver `true`.

### Hotfix v0.5.2 (2026-11-14)

Status sticky impede detectar novo toque / mesmo facial (`unlock_face=2`).  
`door-lock/records` falhava com `sign invalid` (query params fora de ordem alfabética).  
**Correção:** assinatura com query ordenada; campainha/unlock/alarme via records; entidades `event` registradas antes do poll.

### Hotfix v0.5.3 (2026-11-14)

Alarme por tentativas erradas **não** aparece em `door-lock/records` (`alarm_lock` sticky / vazio).  
Em videolocks o lockout costuma vir em `initiative_message` (ext.type) / logs DP type=7 (ver Xtend #1079).  
**Correção:** ler device logs + `initiative_message` / `alarm_reminder` / `alarm_lock` re-reports; não disparar alarme sticky no bootstrap.

## Referências (já no repo / conhecidas)

- `docs/device-sl-ce.md`, `docs/references.md`, `docs/camera-todo.md`  
- [tuya-smart-lock](https://github.com/nicolasglg/tuya-smart-lock) (MIT) — ticket unlock  
- [ha-tuya-lock-monitor](https://github.com/crestall/ha-tuya-lock-monitor) (MIT) — sensores + doorbell auto-reset 1s  
- [xtend_tuya](https://github.com/azerty9971/xtend_tuya) (GPL — estudar comportamento, **não copiar código**) — muitos `event.*`  
- Docs Tuya video lock DPs: https://developer.tuya.com/en/docs/iot/intercom-door-lock?id=Kaxg4x1dt7a6j  
- OpenAPI status: `/v1.0/iot-03/devices/{id}/status` (já usado em `tuya_api.py`)

## Consumidor (Node-RED / RuGiu)

Workflows em `ia-agents-rugiu`:

- Facial → liga interruptor corredor 1 (~2 min) — trigger desejado: unlock facial / `lock` unlocked  
- Campainha → liga TV + cast câmera fechadura ~60s + notify urgente  
- Alarme fechadura → mesma sequência TV + notify  

Se os eventos no HA forem bons, o Node-RED só escuta; não precisa de hack.

## Pedido ao agente

1. Auditar `coordinator.py`, `binary_sensor.py`, `sensor.py`, `lock.py`, `const.py`, `tuya_api.py`  
2. Comparar com Xtend/Monitor o que **falta** expor  
3. Descobrir na prática (API dump / debug) todos os DPs do device `eba0b0f3d9b38977ed8b0a`  
4. Implementar eventos + pulse/reset + melhor refresh  
5. Atualizar docs e versão  
6. Indicar como atualizar no HAOS (HACS / copy custom_components)

Trabalhar neste repositório `tuya-slce-videolock`. Responder em português.
