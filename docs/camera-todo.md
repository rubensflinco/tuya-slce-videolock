# Câmera SL-CE — próximos passos (MVP stub)

## Estado atual

A entidade `camera.*` é registrada no **mesmo** device da fechadura, mas **não** entrega snapshot/stream ainda.

## Por que não copiar o Xtend Tuya

[azerty9971/xtend_tuya](https://github.com/azerty9971/xtend_tuya) prova que o stream da SL-CE funciona (WebRTC / IPC via Sharing + IoT SDK). Porém o projeto é **GPL-3.0** — incompatível com cópia direta para esta integração MIT.

## Caminho recomendado (OpenAPI, código próprio)

1. **HLS / RTSP allocate** (mais simples para o HA `stream`/`ffmpeg`):
   - Endpoint típico: `POST /v1.0/devices/{device_id}/stream/actions/allocate` (ou variante Sharing)
   - Tipos: `hls`, `rtsp`, `rtmp`, `flv`
   - Retornar URL em `Camera.stream_source()`

2. **WebRTC** (melhor latência, mais complexo):
   - `GET /v1.0/devices/{device_id}/webrtc-configs`
   - Troca SDP / ICE (mesmo fluxo que o app Smart Life)
   - Requer handlers HA WebRTC (`async_handle_async_webrtc_offer`, etc.)

3. **Dependências**:
   - Serviço de câmera / IPC autorizado no projeto IoT
   - Possivelmente `ffmpeg` no HA para RTSP/HLS
   - Token Cloud já obtido pelo `TuyaCloudApi` desta integração

4. **Teste no RuGiu**:
   - Device `eba0b0f3d9b38977ed8b0a`
   - Comparar com a entidade Xtend existente até a paridade

## Enquanto isso

Manter Xtend Tuya **só** para a câmera, se necessário, e usar `slce_videolock` para unlock + sensores — ou desativar a câmera stub até o allocate estar pronto.
