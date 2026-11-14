# Câmera SL-CE — stream Cloud

## Estado (v0.3.0+)

A entidade `camera` chama:

`POST /v1.0/devices/{device_id}/stream/actions/allocate` com `type` preferido (default **hls**) e fallback `rtsp` → `hls` → `flv` → `rtmp`.

É o **mesmo endpoint OpenAPI** documentado pela Tuya e usado no caminho IoT do [Xtend Tuya](https://github.com/azerty9971/xtend_tuya) (`get_device_stream_allocate`). Código desta integração é **MIT próprio** (sem copiar GPL do Xtend).

- `Camera.stream_source()` → URL assinada fresca (expira; re-allocate a cada abertura)
- Snapshot → `homeassistant.components.ffmpeg.async_get_image`
- Manifest declara `dependencies: ["ffmpeg"]`

Docs Tuya: [IoT Video Live Stream](https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f)

## Pré-requisito no iot.tuya.com (igual Xtend)

1. Cloud → Cloud Services  
2. Ativar trial **IoT Video Live Stream**  
3. Confirmar que o serviço aparece ativo  

Guia espelhado: https://github.com/azerty9971/xtend_tuya/blob/main/docs/configure_cameras.md

Também precisa de **IoT Core** + **Smart Lock Open Service** (unlock).

## Como testar no HAOS

1. Copiar `custom_components/slce_videolock` para `/config/custom_components/` (ou atualizar via HACS).
2. Reiniciar o Home Assistant.
3. Settings → Devices & Services → **SL-CE Videolock** (Access ID/Secret, Device ID `eba0b0f3d9b38977ed8b0a`, região do projeto).
4. No **mesmo** device, conferir lock + sensores + câmera.
5. Abrir a entidade câmera (More info) e verificar preview/stream.
6. Se falhar: Settings → System → Logs (`custom_components.slce_videolock`); confirmar serviço Live Stream; testar preferência HLS vs RTSP (options / recriar entry se necessário).

## WebRTC (opcional, futuro)

Xtend prioriza WebRTC (`/v1.0/devices/{id}/webrtc-configs` + SDP). Melhor latência, mais complexo. RTSP/HLS cobre o caso RuGiu da SL-CE se o allocate funcionar.

## Ainda opcional

- [ ] Cache curto da URL allocate
- [ ] go2rtc como proxy se ffmpeg falhar com RTSPs Tuya
- [ ] WebRTC nativo

## Debug

- Sem URL → log warning + serviço Live Stream não ativado / device offline  
- Com URL mas tela preta → testar `ffmpeg` no HA; forçar `hls` se RTSP falhar no host  
