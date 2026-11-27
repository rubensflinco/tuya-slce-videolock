# Tuya SL-CE Videolock for Home Assistant

<p align="center">
  <img src="icon.png" alt="Tuya SL-CE Videolock — Home Assistant smart lock camera integration" width="128" height="128">
</p>

<p align="center">
  <strong>Home Assistant custom integration</strong> for the <strong>Novadigital / Tuya Fechadura SL-CE (Wi-Fi) videolock</strong> —
  cloud unlock, live camera, doorbell photos, battery and sensors in <strong>one device</strong>.
</p>

<p align="center">
  <a href="https://github.com/rubensflinco/tuya-slce-videolock/releases/latest"><img src="https://img.shields.io/github/v/release/rubensflinco/tuya-slce-videolock?style=flat-square&label=release" alt="Latest release"></a>
  <a href="https://github.com/rubensflinco/tuya-slce-videolock/blob/main/LICENSE"><img src="https://img.shields.io/github/license/rubensflinco/tuya-slce-videolock?style=flat-square" alt="MIT license"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5?style=flat-square" alt="Home Assistant 2024.8+"></a>
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-orange?style=flat-square" alt="HACS custom"></a>
  <a href="https://github.com/rubensflinco/tuya-slce-videolock/actions/workflows/validate.yaml"><img src="https://img.shields.io/github/actions/workflow/status/rubensflinco/tuya-slce-videolock/validate.yaml?branch=main&style=flat-square&label=validate" alt="Validate"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=rubensflinco&repository=tuya-slce-videolock&category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open repository in Home Assistant Marketplace / HACS"></a>
  &nbsp;
  <a href="https://my.home-assistant.io/redirect/config_flow_start/?domain=slce_videolock"><img src="https://my.home-assistant.io/badges/config_flow_start.svg" alt="Add Tuya SL-CE Videolock integration"></a>
</p>

**Keywords / busca:** Home Assistant · Tuya smart lock · videolock · Fechadura SL-CE · Novadigital · câmera na fechadura · doorbell · Remote Unlock · HACS · Marketplace

Versão atual: **0.9.2**. Domain: `slce_videolock`. Licença: **MIT**.

**0.9.2:** usa exclusivamente as credenciais Tuya Cloud OpenAPI para alocar streams, executa leituras de mtime de snapshots no executor e remove o ID pessoal de dispositivo das strings de configuração.

**0.9.1:** corrige fotos vazias (corredor) no acesso liberado — resolve `bucket`+`path` via API (`movement-configs`), retries mais longos no álbum Cloud, reconsulta records/`initiative_message` antes do fallback de stream.

**0.9.0:** fotos de acesso/alarme/campainha preferem a **capa do evento na Cloud** (álbum / reconhecimento facial) em vez do stream ao vivo.

**0.8.2:** catalog submission release after green HACS+hassfest CI; prior 0.8.1 fixed http dependency.

Agents and LLMs: see [`llms.txt`](llms.txt) for a machine-oriented summary.

## What this solves

The **official Tuya** Home Assistant integration does **not** expose a usable `lock` entity for this videolock. Other community projects cover only pieces (unlock *or* sensors *or* camera), and Home Assistant **cannot** merge entities from different integrations into one device in the UI.

**Tuya SL-CE Videolock** is the all-in-one Cloud integration for the SL-CE Wi-Fi smart lock with camera:

| Capability | Status | Pattern inspired by |
|------------|--------|---------------------|
| Unlock / lock | ✅ Cloud ticket (`password-ticket` → `door-operate`) | [tuya-smart-lock](https://github.com/nicolasglg/tuya-smart-lock) (MIT) |
| Remote unlock PIN (4 digits) | ✅ Setup; PBKDF2 hash; native HA keypad | `LockEntity.code_format` |
| Battery, online, doorbell, last_* | ✅ Configurable Cloud polling (default **60 s**) | [ha-tuya-lock-monitor](https://github.com/crestall/ha-tuya-lock-monitor) (MIT) |
| Camera stream | ✅ Tuya Cloud OpenAPI `stream/actions/allocate` (RTSP/HLS) + ffmpeg | [Tuya IoT Video Live Stream](https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f) |
| Photos + gallery | ✅ Snapshot on **doorbell**, **access granted**, **alarm**; prefers **Cloud album/face cover**; Media folders; retention **30 days** | `image` + `media_source` |

**LAN / `tuya_local`:** out of scope — local unlock on this videolock is not reliable.

Camera stream URLs are allocated using this integration's own Tuya Cloud OpenAPI credentials. The Tuya Cloud project must have **IoT Video Live Stream** enabled (a free trial is available in the Tuya portal). Details: [`docs/camera-todo.md`](docs/camera-todo.md).

## Install

### Marketplace / HACS (recommended)

1. Open the badge above, or add custom repository `rubensflinco/tuya-slce-videolock` as **Integration**
2. Download / install, restart if Home Assistant asks
3. **Settings → Devices & Services → Add Integration → Tuya SL-CE Videolock**
4. Enter Access ID / Secret / region, pick the lock, set the **4-digit PIN**, polling interval, and photo retention

My links also work on HA **before** 2026.11 (HACS) and **after** (built-in Marketplace).

Catalog listing (default search without custom URL) requires a PR to [`hacs/default`](https://github.com/hacs/default) — see [`docs/marketplace-catalog.md`](docs/marketplace-catalog.md). Until merged, use the My link above.

### Manual

1. Copy `custom_components/slce_videolock` into `/config/custom_components/`
2. Ensure **ffmpeg** is available (declared dependency)
3. Restart Home Assistant and add the integration from the UI

## Tuya IoT prerequisites

1. Account on [platform.tuya.com](https://platform.tuya.com/) → **Cloud** project (Smart Home method)
2. Link the **Smart Life / Tuya** app account (QR) so the device appears
3. Authorize:
   - **IoT Core**
   - **Smart Lock Open Service** (trial ~6 months — renew when it expires)
   - **IoT Video Live Stream** (camera)
4. In Smart Life: enable **Remote Unlock / Unlock without password**
5. Note **Access ID**, **Access Secret**, **Device ID**, and data-center **region** (`us` / `eu` / `cn` / `in`)

Reference device sheet: [`docs/device-sl-ce.md`](docs/device-sl-ce.md).

## Entities (same device)

Registry id: `(slce_videolock, <device_id>)`.

| Platform | Entities |
|----------|----------|
| `lock` | Lock (ticket unlock/lock + PIN) |
| `sensor` | Battery, last fingerprint/password/card, app unlocks, temporary codes, last alarm, contact requests |
| `binary_sensor` | Online, Doorbell, Duress alert |
| `camera` | Live stream + ffmpeg snapshot |
| `image` | Last photo — Doorbell / Access granted / Alarm |
| Media Browser | Folders for each photo event type |

### Polling

- Default **60 s** · range **1–600 s** (setup / Configure)
- Very low intervals make doorbell/`last_*` snappier but may hit Tuya rate limits

### Photos

| Event | Media folder | Image entity |
|-------|--------------|--------------|
| Doorbell | Campainha | Last doorbell photo |
| Access granted (fingerprint, PIN, face, app, key…) | Acesso liberado | Last access photo |
| Security alarm (incl. duress) | Alarme de segurança | Last alarm photo |

Photos prefer the **Tuya Cloud event cover** (album / face recognition / `initiative_message`). The integration resolves storage URLs (`bucket`+`file_path`) and retries Cloud upload for several seconds before any live-stream fallback (often an empty hallway). Retention default **30 days** (1–365). Activity entries include source (`cloud_album` / `cloud_initiative` / `live_stream`…).

No Tuya IoT: authorize **Smart Lock Open Service**, enable **Beta API** if needed for `movement-configs`, and a door-lock cloud storage plan when albums-media is empty.

### Remote unlock PIN

- Required 4-digit numeric code before unlock (native HA lock keypad)
- Stored as salt + PBKDF2-SHA256 only — **not** reversible
- To change PIN: remove the integration and add it again

## FAQ

### Does this work with any Tuya lock?

It targets **videolock / smart lock** devices exposed by Tuya Cloud (tested on **Novadigital SL-CE Wi-Fi**). Other Tuya locks may work if they support the same ticket unlock + optional stream APIs — open an issue with your category and DPs.

### Why not the official Tuya integration?

Official Tuya does not provide a proper `lock` platform for this device class. This project fills that gap and keeps camera + sensors on the **same** HA device.

### Is it local / LAN?

No. Primary path is **Tuya Cloud** (`cloud_polling`). Local unlock via `tuya_local` is unreliable on this model and out of scope.

### Is it a Supervisor add-on?

No. It is a **custom integration** (`custom_components`), installable via Marketplace / HACS.

### Will it appear in the default Marketplace list?

After CI is green and a release is published, the owner submits `rubensflinco/tuya-slce-videolock` to [`hacs/default`](https://github.com/hacs/default). Review often takes months. Until then, install via the My / custom repository link.

### How do I update?

Marketplace/HACS → update (or ⋮ → download a release tag). Prefer GitHub **Releases** (semver), not a raw commit hash.

## Development

```bash
python scripts/check_manifest.py
python scripts/build_release_zip.py
python -m unittest discover -s tests -v
```

See [`AGENTS.md`](AGENTS.md), [`.cursor/skills/`](.cursor/skills/), [`docs/references.md`](docs/references.md), [`CONTRIBUTING.md`](CONTRIBUTING.md), [`SECURITY.md`](SECURITY.md).

## Attribution

- This integration: **MIT** — Rubens Flinco / RuGiu
- Unlock ticket patterns: [nicolasglg/tuya-smart-lock](https://github.com/nicolasglg/tuya-smart-lock) (MIT)
- Sensor / polling patterns: [crestall/ha-tuya-lock-monitor](https://github.com/crestall/ha-tuya-lock-monitor) (MIT)
- Camera behavior study: [azerty9971/xtend_tuya](https://github.com/azerty9971/xtend_tuya) (GPL-3 — **no code copied**) + public Tuya API

## License

MIT — Rubens Flinco / RuGiu
