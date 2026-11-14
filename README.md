# SL-CE Videolock

Integração custom do **Home Assistant** para a **Fechadura Inteligente SL-CE (Wi-Fi)** (Novadigital / Tuya Smart Life — categoria `videolock`).

Objetivo: **um único device** no HA com:

| Capacidade | Hoje (3 integrações) | Neste repo |
|------------|----------------------|------------|
| Stream da câmera | Xtend Tuya | ✅ |
| Destrancar / trancar | Tuya Smart Lock | ✅ |
| Status ricos (bateria, campainha, online, last unlock…) | Tuya Lock Monitor | ✅ |

## Por que existe

A integração oficial Tuya **não** expõe `lock`. Três addons cobrem pedaços diferentes e o HA **não** permite juntar entidades de integrações distintas no mesmo device via UI. Esta integração unifica o fluxo Cloud (ticket unlock + DPs + câmera).

## Referências obrigatórias (código)

1. [azerty9971/xtend_tuya](https://github.com/azerty9971/xtend_tuya) — câmera / eventos / DPs estendidos  
2. [nicolasglg/tuya-smart-lock](https://github.com/nicolasglg/tuya-smart-lock) — unlock via Smart Lock Cloud API (ticket)  
3. [crestall/ha-tuya-lock-monitor](https://github.com/crestall/ha-tuya-lock-monitor) — sensores de status / histórico  

Docs do aparelho: [`docs/device-sl-ce.md`](docs/device-sl-ce.md) · briefing IA: [`AGENTS.md`](AGENTS.md)

## Instalação (HACS / manual)

1. Copiar `custom_components/slce_videolock` para `/config/custom_components/`  
2. Reiniciar o HA  
3. Adicionar integração **SL-CE Videolock**  
4. Credenciais: Tuya IoT Access ID/Secret + Device ID (mesmo projeto que Smart Lock)

## Desenvolvimento

Ver skills em `.cursor/skills/` e `AGENTS.md`.

```bash
# validação rápida de estrutura
python scripts/check_manifest.py
```

## Licença

MIT — Rubens Flinco / RuGiu
