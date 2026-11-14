# Câmera SL-CE — stream Cloud

## Estado (v0.3.0+)

A entidade `camera` chama:

`POST /v1.0/devices/{device_id}/stream/actions/allocate` com `type` preferido (default **hls**) e fallback `rtsp` → `hls` → `flv` → `rtmp`.

É o **mesmo endpoint OpenAPI** documentado pela Tuya e usado no caminho IoT do [Xtend Tuya](https://github.com/azerty9971/xtend_tuya) (`get_device_stream_allocate`). Código desta integração é **MIT próprio** (sem copiar GPL do Xtend).

- `Camera.stream_source()` → URL assinada fresca (expira; re-allocate a cada abertura)
- Snapshot → `homeassistant.components.ffmpeg.async_get_image`
- Manifest declara `dependencies: ["ffmpeg"]`

Docs Tuya: [IoT Video Live Stream](https://developer.tuya.com/en/docs/cloud/iot-video-live-stream?id=Kaiuybxmi136f)

## Pré-requisito no platform.tuya.com (igual Xtend)

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

### Por que o Xtend / Tuya oficial “não pedem assinatura”

Eles **não** usam Access ID/Secret para o stream. Usam a sessão **Smart Life / Sharing** (QR / User Code), a mesma do app — aí a Tuya libera allocate sem o clique em Cloud Services.

O trial **IoT Video Live Stream** é **grátis** (Free Trial); não é plano pago. Só que **não dá** para o addon ativar isso sozinho com Access ID/Secret: a Tuya só autoriza Cloud Services no portal (UI humana). Não existe API pública estável com essas credenciais para “clicar Free Trial” no setup.

**Nesta integração (v0.4.3+):** a câmera tenta primeiro reaproveitar o manager Sharing da integração oficial `tuya` (ou `xtend_tuya`) se o mesmo `device_id` estiver carregado — mesmo caminho do outro addon, sem trial. OpenAPI do projeto fica só como fallback.

### Spinner eterno / `Invalid data` / 404 no stream worker

Sintoma: more-info da câmera fica no loading (às vezes nem anima), log:

```
Error opening stream (Invalid data found when processing input, https://…m3u8…)
Not Found error opening stream (… rtsps://wework-…stream.iot-11.com…)
```

Causa: Sharing **conseguiu** URL, mas (1) HLS da Tuya costuma quebrar o demuxer do HA e (2) URLs assinadas **expiram** e o HA reutiliza a sessão antiga.

Mitigação em **0.4.5**: preferir **RTSP** no Sharing + `async_create_stream` descarta o `Stream` anterior a cada abertura (padrão Xtend #1067).

### Outros

- Sem URL → `stream_error` nos atributos da câmera + log  
- Com URL mas tela preta → conferir log `stream_worker`; reiniciar abertura da câmera (re-allocate)  
 
 
