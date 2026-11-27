# Câmera SL-CE — stream Cloud

## Estado (v0.9.2+)

A entidade `camera` chama:

`POST /v1.0/devices/{device_id}/stream/actions/allocate` com `type` preferido (default **rtsp**) e fallback para os demais formatos suportados.

O stream usa somente as credenciais próprias desta integração e o endpoint OpenAPI documentado pela Tuya. Não acessa sessões ou dados de outras integrações.

- `Camera.stream_source()` → URL assinada fresca (expira; re-allocate a cada abertura)
- Snapshot → `homeassistant.components.ffmpeg.async_get_image`
- Manifest declara `dependencies: ["ffmpeg"]`

Docs Tuya: [IoT Video Live Stream](https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f)

## Pré-requisito no platform.tuya.com

1. Cloud → Cloud Services  
2. Ativar trial **IoT Video Live Stream**  
3. Confirmar que o serviço aparece ativo  

Guia espelhado: https://github.com/azerty9971/xtend_tuya/blob/main/docs/configure_cameras.md

Também precisa de **IoT Core** + **Smart Lock Open Service** (unlock).

## Como testar no HAOS

1. Copiar `custom_components/slce_videolock` para `/config/custom_components/` (ou atualizar via HACS).
2. Reiniciar o Home Assistant.
3. Settings → Devices & Services → **Tuya SL-CE Videolock** (Access ID/Secret, Device ID da sua conta, região do projeto).
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

### Erro real no RuGiu (HA logs)

```
Stream allocate (hls|rtsp|flv|rtmp) failed: No permissions. This API is not subscribed.
Error requesting stream: Camera … does not support streaming
```

Causa: o projeto Cloud das credenciais **não tem** o serviço **IoT Video Live Stream** autorizado (trial). O unlock/sensores usam outras APIs e continuam OK; só o allocate da câmera exige esse serviço.

Correção (igual [Xtend configure_cameras](https://github.com/azerty9971/xtend_tuya/blob/main/docs/configure_cameras.md)):

1. [platform.tuya.com](https://platform.tuya.com/) → **Cloud → Cloud Services** (ou Service API no projeto)
2. Linha **IoT Video Live Stream** → **Free Trial** / Authorize
3. Confirmar status ativo
4. No HA: reabrir a entidade câmera (ou recarregar a integração)

### Spinner eterno / `Invalid data` / 404 no stream worker

Sintoma: more-info da câmera fica no loading (às vezes nem anima), log:

```
Error opening stream (Invalid data found when processing input, https://…m3u8…)
Not Found error opening stream (… rtsps://wework-…stream.iot-11.com…)
```

Causa: a alocação do stream funcionou, mas (1) HLS da Tuya costuma quebrar o demuxer do HA e (2) URLs assinadas **expiram** e o HA reutiliza a sessão antiga.

Mitigação: preferir **RTSP** e `async_create_stream` descarta o `Stream` anterior a cada abertura.

### Outros

- Sem URL → `stream_error` nos atributos da câmera + log  
- Com URL mas tela preta → conferir log `stream_worker`; reiniciar abertura da câmera (re-allocate)  
 
 
