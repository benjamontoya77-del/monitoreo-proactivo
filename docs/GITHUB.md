# Puesta en marcha en GitHub

```bash
cd monitoreo-proactivo
git init -b main
git add . && git commit -m "feat: versión inicial del sistema de monitoreo proactivo"
# Crea un repo VACÍO en github.com (privado al inicio) y luego:
git remote add origin https://github.com/TU_USUARIO/monitoreo-proactivo.git
git push -u origin main
git checkout -b develop && git push -u origin develop
```
**Flujo de ramas:** `main` = versión estable/entregable · `develop` = integración · `feature/pbXX-nombre` = una rama por historia del backlog.
Cada sprint termina con un Pull Request `develop → main` y una etiqueta (`git tag v1.1.0`). El CI (`.github/workflows/ci.yml`) ejecuta `pytest` y compila el frontend en cada push.

**Backlog y sprints:** con `gh auth login` hecho, ejecuta `./scripts/crear_backlog_github.sh` para crear los 4 sprints y las historias PB01–PB06 de tu Hito 2. Usa GitHub Projects (tablero Kanban) para el Scrumban con límite WIP que describes.
**Seguridad:** `.env` está en `.gitignore`; nunca subas tokens de Telegram ni contraseñas.
