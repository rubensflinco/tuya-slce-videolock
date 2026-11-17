---
name: ha-release
description: >-
  Publica release GitHub/HACS/Marketplace da integração slce_videolock
  (bump, README, commit, push, tag, gh release). Use when the user asks to
  subir versão, publicar release, tag, HACS update, Marketplace, ou
  empacotar zip de release. Nunca só preparar no localhost.
---

# Release SL-CE Videolock (HACS / Marketplace)

## Regra de ouro

Pedido para **subir versão** = publicar de ponta a ponta no GitHub:

`bump → README → testes → zip → commit → tag → push → gh release`

**Não** entregar só artefatos locais. Sempre `git push` + release criada + URL no final.

## README (repo + HA)

- Arquivo único: **`README.md` na raiz**
- `hacs.json` tem `"render_readme": true` → o Marketplace/HA **mostra esse README**
- Em toda release: atualizar versão **e** documentar as mudanças relevantes (PIN, polling, etc.)
- Não existe segundo README separado; manter o da raiz completo e atual

## Por que release GitHub

Instalação só por **commit** aparece como hash (`22225c7`) e atualiza mal.
Marketplace usa **GitHub Release** + ZIP. Catálogo ~4–6 h; repo custom até ~48 h.

## Checklist (obrigatório — executar tudo)

```
- [ ] Bump version em custom_components/slce_videolock/manifest.json
- [ ] Atualizar README.md (versão + mudanças) — feed do Marketplace/HA
- [ ] hacs.json: zip_release true + filename slce_videolock.zip
- [ ] python scripts/check_manifest.py
- [ ] python -m unittest discover -s tests -v
- [ ] python scripts/build_release_zip.py
- [ ] git commit (HEREDOC) na main
- [ ] Tag anotada = version do manifest (ex. 0.7.2) SEM prefixo v
- [ ] git push origin main && git push origin <tag>
- [ ] gh release create <tag> dist/slce_videolock.zip --title ... --notes ...
- [ ] Confirmar asset + devolver URL da release ao usuário
```

## hacs.json (não remover)

```json
{
  "name": "Tuya SL-CE Videolock",
  "zip_release": true,
  "filename": "slce_videolock.zip",
  "render_readme": true,
  "homeassistant": "2024.8.0"
}
```

Sem `country`: o catálogo mostra o repo no mundo todo (melhor descoberta). Só use `country` se quiser filtrar por país.

## Zip — formato crítico

Extraído **dentro** de `custom_components/slce_videolock/`.

| Correto | Errado |
|---------|--------|
| `manifest.json` na raiz do zip | `slce_videolock/manifest.json` |

Sempre: `python scripts/build_release_zip.py`

## Tag = manifest

- Manifest `"version": "0.7.2"` → tag `0.7.2` (mesma string, sem `v`)
- Tags antigas `v0.x` existem; releases novas **sem** `v`

## Comandos (fluxo completo)

```bash
VERSION=$(python -c "import json; print(json.load(open('custom_components/slce_videolock/manifest.json'))['version'])")
python scripts/check_manifest.py
python -m unittest discover -s tests -v
python scripts/build_release_zip.py

git add -A
git commit -m "$(cat <<EOF
release: ${VERSION}

EOF
)"
git tag -a "${VERSION}" -m "${VERSION}"
git push origin main
git push origin "${VERSION}"

gh release create "${VERSION}" dist/slce_videolock.zip \
  --title "${VERSION} — <resumo>" \
  --notes "$(cat <<'EOF'
## Mudanças
- ...

## Atualização
Marketplace/HACS → atualizar (ou ⋮ → baixar esta versão) → reiniciar HA.
EOF
)"
```

## Resposta ao usuário

1. URL: `https://github.com/rubensflinco/tuya-slce-videolock/releases/tag/<VERSION>`
2. Se a instalação mostrar **hash de commit**: ⋮ → baixar outra versão → escolher a tag
3. Update automático pode demorar; também em **Configurações → Atualizações**

## Anti-padrões

- Parar no localhost / “preparei o zip, publique quando quiser”
- Push sem `gh release create`
- Release sem asset `slce_videolock.zip`
- Esquecer de atualizar `README.md` (é o texto do HA)
- Zip com pasta `slce_videolock/` aninhada
- `filename` sem `zip_release: true`
