# Câmera SL-CE — stream Cloud

## Estado (v0.3.0+)

A entidade `camera` chama:

`POST /v1.0/devices/{device_id}/stream/actions/allocate` com `type` em `rtsp` → `hls` → `flv` → `rtmp`

É o **mesmo endpoint OpenAPI** documentado pela Tuya e usado no caminho IoT do [Xtend Tuya](https://github.com/azerty9971/xtend_tuya) (`get_device_stream_allocate`). Código desta integração é **MIT próprio** (sem copiar GPL do Xtend).

`Camera.stream_source()` devolve a URL; o HA usa **ffmpeg** para o player.

## Pré-requisito no iot.tuya.com (igual Xtend)

1. Cloud → Cloud Services  
2. Ativar trial **IoT Video Live Stream**  
3. Confirmar que o serviço aparece ativo  

Guia espelhado: https://github.com/azerty9971/xtend_tuya/blob/main/docs/configure_cameras.md

Também precisa de **IoT Core** + **Smart Lock Open Service** (unlock).

## WebRTC (opcional, futuro)

Xtend prioriza WebRTC (`/v1.0/devices/{id}/webrtc-configs` + SDP). Melhor latência, mais complexo. RTSP/HLS cobre o caso RuGiu da SL-CE se o allocate funcionar.

## Debug

- Sem URL → log warning + serviço Live Stream não ativado / device offline  
- Com URL mas tela preta → testar `ffmpeg` no HA; tentar HLS forçando só `hls` no código se RTSP falhar no host  
