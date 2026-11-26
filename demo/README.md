# Scripts de la demo

Scripts listos para ejecutar, uno por acción, para el uso diario del prototipo
(levantar o resetear el cluster, prueba de carga, etc.).

## Cómo ejecutarlos

> ⚠️ **Se corren en Git Bash** (el que ya venís usando), **NO en CMD ni PowerShell**, y
> **NO hace falta abrirlo como administrador.**

Abrí **Git Bash** en la raíz del repositorio y corré,
por ejemplo:

```bash
bash demo/k3s-levantar.sh
```

(Requisito en todos los casos: **Docker Desktop abierto**.) Para cortar un script que
queda corriendo —como `pico-carga.sh` o `pico-observar.sh`— se usa **Ctrl+C**.

---

## ▶️ Recorrido de la demo (orden sugerido)

1. **Levantar / resetear** la demo:
   - `bash demo/k3s-resetear.sh` → deja el sistema **en cero** (ideal: el panel de
     vendedor arranca vacío y se llena en vivo). *(O `k3s-levantar.sh` si no querés
     borrar datos.)*
2. `bash demo/k3s-estado.sh` → confirmá que todo esté **Running** y la app responda.
3. En **una terminal aparte**: `bash demo/pico-observar.sh` → para ver el HPA escalar.
4. En **otra terminal**: `bash demo/pico-carga.sh` → abrí `http://localhost:8089`,
   poné Users=300 / Ramp=30 / Start = arranca el **pico**.
5. En el navegador (`http://localhost:8088`) seguí estos pasos: activar
   CyberMonday → esperar que escale → **comprar durante el pico** → panel de vendedor →
   campana (notificación por IA, aparece a los ~5-15 s).
6. Al terminar: **Stop** en Locust; opcional `bash demo/k3s-detener.sh` para pausar.

---

## Los scripts

### k3s — entorno de la DEMO (autoescala de verdad; `http://localhost:8088`)

| Script | Qué hace |
|---|---|
| `k3s-levantar.sh` | Crea el cluster si no existe, o **reanuda** el existente (conserva datos). Deja la app lista. |
| `k3s-resetear.sh` | **Borra y recrea** el cluster limpio → **0 pedidos**, 16 productos, stock lleno. *(Antes de empezar.)* |
| `k3s-estado.sh`   | Muestra pods, HPA y un chequeo rápido de la app. Solo lectura. |
| `k3s-detener.sh`  | **Pausa** el cluster (libera CPU/RAM, conserva datos). |
| `k3s-eliminar.sh` | **Borra** el cluster por completo. |

### Pico de carga (la parte central de la demo)

| Script | Qué hace |
|---|---|
| `pico-carga.sh`    | Lanza **Locust** (UI en `:8089`) contra el cluster = el pico. Ctrl+C corta la carga. |
| `pico-observar.sh` | Muestra el **autoescalado en vivo** (réplicas 1→5). Abrir antes de lanzar la carga. |

### docker compose — entorno de DESARROLLO (`http://localhost`, **sin** autoescalado)

| Script | Qué hace |
|---|---|
| `compose-levantar.sh` | Levanta el stack con compose (rápido, para probar sin Kubernetes). |
| `compose-detener.sh`  | Detiene el stack (conserva datos). |
| `compose-resetear.sh` | Resetea el stack a cero (borra datos) y lo vuelve a levantar. |

---

## Notas

- **¿k3s o compose para la demo?** → **k3s.** El corazón de la demo (compra durante un
  pico con **autoescalado real**) solo funciona en k3s; compose no autoescala. compose
  es solo para desarrollo/pruebas rápidas.
- **No corras k3s y compose a la vez** si andás justo de RAM: k3s usa `:8088`, compose
  `:80` (no chocan de puerto, pero sí consumen recursos juntos).
- Los scripts ya resuelven el **gotcha de kubectl en Windows** (re-fijan el acceso al
  cluster solos). Si igual `kubectl` diera timeout, corré `k3s-levantar.sh`.
- **Si cambiás código** y querés verlo en k3s: primero `cd infra && docker compose
  build` (reconstruye las imágenes) y después `k3s-resetear.sh` (que las reimporta).
- Usuario de la demo: `juan@shopia.demo` / `demo` (el front loguea solo).
