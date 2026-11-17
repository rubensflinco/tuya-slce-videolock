# Entrar no catálogo oficial (Marketplace / HACS)

O **Marketplace** do Home Assistant (desde 2026.11) e o **HACS** usam o **mesmo catálogo**: [`hacs/default`](https://github.com/hacs/default).

Qualquer um pode instalar este repo por **link custom**. Para aparecer **na lista padrão** (busca sem adicionar URL), é preciso um PR nesse catálogo. A revisão costuma levar **meses**.

Docs oficiais:

- [Get into the catalog](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [Publish a custom integration](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Include default repositories (HACS)](https://hacs.xyz/docs/publish/include/)

## Checklist antes do PR

- [x] Repo público no GitHub
- [x] `hacs.json` + `custom_components/slce_videolock/` + `brand/icon.png`
- [x] `manifest.json` com `version`, `issue_tracker`, `documentation`, `codeowners`, `categories`
- [x] Description, topics e Issues habilitados no GitHub
- [x] GitHub Actions: HACS validate + hassfest (sem `ignore`)
- [x] Pelo menos um **GitHub Release** completo (não só tag)
- [ ] Actions verdes no branch `main` após o push desta preparação
- [ ] Novo release **depois** das Actions passarem (exigência do catálogo)
- [ ] PR em `hacs/default` → arquivo `integration`, entrada `rubensflinco/tuya-slce-videolock` em ordem alfabética
- [ ] Template do PR preenchido (links da release + runs verdes das Actions)
- [ ] PR aberto da conta pessoal do **owner** (não organização), editável pela equipe HACS

## Como abrir o PR

```bash
# Fork hacs/default no GitHub, depois:
git clone https://github.com/<seu-user>/default.git
cd default
git checkout -b add-tuya-slce-videolock
# Editar integration: inserir "rubensflinco/tuya-slce-videolock" em ordem alfabética
git commit -am "Add rubensflinco/tuya-slce-videolock"
git push -u origin add-tuya-slce-videolock
gh pr create --repo hacs/default --title "Add rubensflinco/tuya-slce-videolock" --body-file ...
```

Enquanto o PR não mergeia, use os badges **My** no README para instalação por link.

## O que não é “oficial”

| Caminho | Significado |
|---------|-------------|
| Catálogo Marketplace / HACS default | Comunidade; aparece na busca padrão |
| Custom repository link | Instalável, fora do catálogo |
| Home Assistant Core | Integração built-in (outro processo, bem mais tarde) |
| Supervisor Add-on | Container separado — **este projeto não é add-on** |

## Divulgação (descoberta Google + IA)

1. Post no [Community Home Assistant](https://community.home-assistant.io/) (Share your Projects)
2. `r/homeassistant` e grupos BR (Telegram/Discord) com o My link
3. Manter `README.md` + `llms.txt` atualizados (citáveis por agentes)
4. Releases frequentes com notas claras (o update entity mostra o body)
