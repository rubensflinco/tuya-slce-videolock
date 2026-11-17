# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest GitHub release | Yes |
| Older tags | Best effort |

## Reporting a vulnerability

Please **do not** open a public issue for security problems that could unlock doors or leak credentials.

Email the maintainer via the GitHub profile of [@rubensflinco](https://github.com/rubensflinco), or open a **private** security advisory on GitHub if available.

Include:

- Integration version and Home Assistant version
- Impact (e.g. unlock without PIN, credential leak)
- Steps to reproduce without sharing real Access Secret / PIN

## Hardening notes for users

- Treat Tuya **Access Secret** like a password
- Always set the **4-digit remote unlock PIN** in the config flow
- Prefer a dedicated Tuya Cloud project with least privilege
- Keep **Smart Lock Open Service** and camera trials renewed only as needed
