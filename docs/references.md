# Repositórios de referência

Clone/leia estes três projetos **antes** de inventar protocolo. Preferir reutilizar padrões e adaptar ao SL-CE.

## 1. Xtend Tuya — câmera + DPs estendidos

- Repo: https://github.com/azerty9971/xtend_tuya  
- Domain HA: `xtend_tuya`  
- O que pegar:
  - Descoberta / sharing SDK Tuya (mesmo login User Code que Tuya oficial)
  - Entidade `camera` para videolock
  - Mapeamento de events (`unlock_*`, doorbell, alarm)
  - Tratamento de product unsupported + status DPs  

No RuGiu: stream da SL-CE **funciona** aqui; `operate_lock` **não** destranca.

## 2. Tuya Smart Lock — unlock real

- Repo: https://github.com/nicolasglg/tuya-smart-lock  
- Domain HA: `tuya_smart_lock`  
- O que pegar:
  - Fluxo **ticket** da Smart Lock Cloud API (`lock.unlock` / `lock.lock`)
  - Config: Access ID/Secret + device_id
  - Categorias: `videolock`, `ms`, `mk`, `jtmspro`, …  
  - Optimistic state + auto-lock window  

No RuGiu: é a **única** das três que abre a tranca da SL-CE.

## 3. Tuya Lock Monitor — sensores ricos

- Repo: https://github.com/crestall/ha-tuya-lock-monitor  
- Domain HA: `tuya_lock_monitor`  
- Requirements: `tinytuya`  
- O que pegar:
  - Polling OpenAPI / tinytuya para bateria, online, doorbell, last_* unlock  
  - Naming / device_class dos sensores  
  - Entry por device_id  

No RuGiu: melhores status; sem stream e sem unlock útil.

## Docs Tuya externas

- Video lock / intercom DPs: https://developer.tuya.com/en/docs/iot/intercom-door-lock?id=Kaxg4x1dt7a6j  
- HA Tuya oficial (sem lock): https://www.home-assistant.io/integrations/tuya/  
- Community locks: https://community.home-assistant.io/t/tuya-smart-life-door-locks/411396  

## Regra de arquitetura deste repo

```
slce_videolock = SmartLockTicketAPI (unlock)
               + Camera/stream path (inspirado Xtend)
               + Status sensors (inspirado Lock Monitor)
               → um config entry, um device_registry device
```

Não criar três devices. Não depender de mover entidades entre integrações no HA.
