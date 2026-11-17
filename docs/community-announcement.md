# Rascunho de anúncio (Community / Reddit)

Copie, ajuste e publique. Inclua sempre o My link.

---

**Title:** Tuya / Novadigital SL-CE Wi-Fi videolock — unlock + camera + doorbell in one Home Assistant device

Hi everyone,

I built a custom integration for the **Novadigital / Tuya Fechadura SL-CE (Wi-Fi)** smart lock with camera (`videolock`).

**Problem:** the official Tuya integration does not expose a proper `lock` entity for this device, and you cannot merge entities from different integrations into one device in the UI. Existing add-ons only cover pieces (unlock *or* sensors *or* camera).

**This integration** (`slce_videolock`) puts everything on **one device**:

- Cloud unlock/lock (ticket API) with optional 4-digit PIN
- Live camera stream (RTSP/HLS + ffmpeg)
- Doorbell / access / alarm photo gallery in Media Browser
- Battery, online, last unlock methods, alarms

**Install (Marketplace / HACS):**

[Open repository in Home Assistant](https://my.home-assistant.io/redirect/hacs_repository/?owner=rubensflinco&repository=tuya-slce-videolock&category=integration)

Repo: https://github.com/rubensflinco/tuya-slce-videolock

Requires a Tuya IoT Cloud project (IoT Core + Smart Lock Open Service + IoT Video Live Stream) and Remote Unlock enabled in Smart Life.

Feedback and issues welcome. Thanks!

---

Versão PT-BR curta:

Integração HA para a **Fechadura SL-CE (Wi-Fi) videolock** (Novadigital/Tuya): destrave Cloud + câmera + fotos da campainha/acesso/alarme + sensores **no mesmo device**. A Tuya oficial não expõe `lock`. Instalação: [My link](https://my.home-assistant.io/redirect/hacs_repository/?owner=rubensflinco&repository=tuya-slce-videolock&category=integration) — repo https://github.com/rubensflinco/tuya-slce-videolock
