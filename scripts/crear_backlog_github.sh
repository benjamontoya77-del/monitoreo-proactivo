#!/usr/bin/env bash
# Crea en GitHub los sprints (milestones) y el Product Backlog PB01-PB06 del Hito 2.
# Requisitos: GitHub CLI (https://cli.github.com) autenticado con `gh auth login`, ejecutar dentro del repo.
set -euo pipefail
for s in "Sprint 1 - Administración" "Sprint 2 - Motor de monitoreo" "Sprint 3 - Alertas y visualización" "Sprint 4 - Reportabilidad y validación"; do
  gh api repos/{owner}/{repo}/milestones -f title="$s" >/dev/null && echo "milestone: $s"
done
gh label create historia --color 0E8A16 2>/dev/null || true
gh label create critica --color B60205 2>/dev/null || true
crear() { gh issue create --title "$1" --body "$2" --label historia${3:+,$3} --milestone "$4"; }
crear "PB01 - RBAC (usuarios y roles)"                "Implementación de RBAC. Prioridad: alta"           ""        "Sprint 1 - Administración"
crear "PB02 - Motor de escaneo ICMP"                  "Disponibilidad básica. Prioridad: crítica"          critica   "Sprint 2 - Motor de monitoreo"
crear "PB03 - Métricas SNMP (CPU, RAM, interfaces)"   "Prioridad: alta"                                     ""        "Sprint 2 - Motor de monitoreo"
crear "PB04 - Alertas por Telegram"                   "Notificaciones proactivas. Prioridad: crítica"      critica   "Sprint 3 - Alertas y visualización"
crear "PB05 - Dashboard en tiempo real (Status Board)" "Prioridad: alta"                                    ""        "Sprint 3 - Alertas y visualización"
crear "PB06 - Informes históricos y SLA"              "Prioridad: media"                                   ""        "Sprint 4 - Reportabilidad y validación"
