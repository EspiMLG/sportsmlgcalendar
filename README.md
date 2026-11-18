# ⚽ Málaga CF · 🏀 Unicaja Baloncesto · 🥅 Heredia 21 FS — Calendario Automático Modular (`.ics`)

Generador automático y portal web interactivo de calendarios deportivos sincronizados para **Málaga CF** (LaLiga / Copa del Rey), **Unicaja Baloncesto** (Liga Endesa ACB / Basketball Champions League) y **Club Deportivo Heredia 21 FS** (2ª Andaluza Femenina Sénior F.S. — RFAF).

---

## 📅 Portal Web y Suscripción a la Carta (Calendarios Modulares)

- **🌐 Panel Web Interactivo (Selector a la carta):** [https://espimlg.github.io/sportsmlgcalendar/](https://espimlg.github.io/sportsmlgcalendar/)

En la web puedes marcar con casillas exactamente a qué equipos quieres suscribirte, o usar directamente cualquiera de los **7 feeds `.ics` auto-actualizables**:

| Combinación de Equipos | Archivo `.ics` | Enlace de Suscripción (`https://` / `webcal://`) |
| :--- | :--- | :--- |
| **⚽ Málaga CF + 🏀 Unicaja + 🥅 Heredia 21 FS** *(Completo)* | `completo.ics` | `https://espimlg.github.io/sportsmlgcalendar/completo.ics` |
| **⚽ Málaga CF + 🏀 Unicaja** *(General clásico)* | `partidos.ics` | `https://espimlg.github.io/sportsmlgcalendar/partidos.ics` |
| **⚽ Solo Málaga CF** | `malaga.ics` | `https://espimlg.github.io/sportsmlgcalendar/malaga.ics` |
| **🏀 Solo Unicaja Baloncesto** | `unicaja.ics` | `https://espimlg.github.io/sportsmlgcalendar/unicaja.ics` |
| **🥅 Solo Heredia 21 Femenino FS** | `heredia21.ics` | `https://espimlg.github.io/sportsmlgcalendar/heredia21.ics` |
| **⚽ Málaga CF + 🥅 Heredia 21 FS** | `malaga_heredia21.ics` | `https://espimlg.github.io/sportsmlgcalendar/malaga_heredia21.ics` |
| **🏀 Unicaja + 🥅 Heredia 21 FS** | `unicaja_heredia21.ics` | `https://espimlg.github.io/sportsmlgcalendar/unicaja_heredia21.ics` |

---

## 🚀 Arquitectura y Características Principales

1. **Extracción Multicapa (A prueba de fallos):**
   - **Málaga CF:** Consume directamente la API oficial paginada de `malagacf.com` (`/api/football_list/football_match`) para obtener horarios exactos en UTC, estadios oficiales, competición y jornada, con *fallback* automático mediante **Selenium** al DOM de la web oficial y enriquecimiento en tiempo real desde **Flashscore**.
   - **Unicaja Baloncesto:** Unifica en una sola pasada la tabla oficial de `unicajabaloncesto.com/calendario`, el feed `/calendario/ics` y las fichas individuales `/partido/ver/id/<id>` en paralelo (`ThreadPoolExecutor`) para obtener el pabellón oficial exacto de cada encuentro, competición y fechas provisionales (`POR CONFIRMAR`).
   - **CD Heredia 21 Femenino FS (RFAF):** Conecta con el sistema oficial `pnfg` de la **Real Federación Andaluza de Fútbol (`rfaf.es`)**, gestionando automáticamente la sesión (`JSESSIONID`) y extrayendo todas las jornadas, horarios confirmados, resultados y pabellones de *2ª Andaluza Femenina Sénior F.S. (Málaga)*.

2. **Resolución Inteligente de Estadios y Pabellones:**
   - Asigna automáticamente el **Estadio La Rosaleda**, el **Palacio de Deportes José María Martín Carpena** y la **Ciudad Deportiva de Carranque (Pabellón)** cuando cada equipo juega en casa.
   - Dispone de diccionarios completos de todos los estadios de **LaLiga (1ª y 2ª División)**, pabellones de **Liga Endesa (ACB) y BCL** y pabellones municipales de **Fútbol Sala en Málaga (RFAF)** para que ningún partido visitante quede sin recinto.

3. **Motor de Reconciliación y Anti-Duplicados:**
   - Normaliza todos los alias de equipos rivales (`Racing Santander` $\leftrightarrow$ `R. Racing Club`, `Betis` $\leftrightarrow$ `Real Betis`, `C.D. U.D. PLAYAS DE MÁLAGA F.S.` $\leftrightarrow$ `UD Playas de Málaga FS`, etc.).
   - Cuando se confirma el horario de un partido y cambia del día provisional al día definitivo ($\pm 12$ días), el motor reemplaza automáticamente el evento provisional sin dejar eventos fantasma duplicados.
   - **Protección anti-borrado e idempotencia (`DTSTAMP`):** Conserva los eventos previos si alguna fuente falla puntualmente y mantiene el `DTSTAMP` intacto si los datos del partido no han variado, evitando commits innecesarios.

4. **Actualización Automática Post-Partido (GitHub Actions):**
   - El workflow [`.github/workflows/main.yml`](.github/workflows/main.yml) se ejecuta diariamente tras cada franja horaria de partidos (mediodía, tarde, competiciones europeas y noche) y tras los anuncios de horarios, pasando primero toda la batería de tests (`pytest`) antes de publicar todos los calendarios `.ics` y actualizar GitHub Pages.

---

## 🧪 Ejecución Local y Plan de Pruebas

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Actualizar todos los calendarios (.ics) y el portal web (index.html)
python malagacalendar.py

# 3. Ejecutar la suite de tests unitarios y de integración
PYTHONPATH=. pytest -v
```

