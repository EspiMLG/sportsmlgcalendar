# ⚽ Málaga CF & 🏀 Unicaja Baloncesto — Calendario Automático (`.ics`)

Generador automático y portal web del calendario oficial de partidos y resultados del **Málaga CF** (LaLiga / Copa del Rey) y del **Unicaja Baloncesto** (Liga Endesa ACB / Basketball Champions League).

---

## 📅 Enlaces de Suscripción y Portal Web

- **🌐 Panel Web Interactivo:** [https://espimlg.github.io/sportsmlgcalendar/](https://espimlg.github.io/sportsmlgcalendar/)
- **📎 URL directa del archivo `.ics`:** `https://espimlg.github.io/sportsmlgcalendar/partidos.ics`
- **📲 Suscripción rápida (iOS / macOS / Outlook):** `webcal://espimlg.github.io/sportsmlgcalendar/partidos.ics`

---

## 🚀 Arquitectura y Características Principales

1. **Extracción Multicapa (A prueba de fallos):**
   - **Málaga CF:** Consume directamente la API oficial paginada de `malagacf.com` (`/api/football_list/football_match`) para obtener horarios exactos en UTC, estadios oficiales, competición y jornada, con *fallback* automático mediante **Selenium** al DOM de la web oficial y enriquecimiento en tiempo real desde **Flashscore**.
   - **Unicaja Baloncesto:** Unifica en una sola pasada la tabla oficial de `unicajabaloncesto.com/calendario`, el feed `/calendario/ics` y las fichas individuales `/partido/ver/id/<id>` en paralelo (`ThreadPoolExecutor`) para obtener el pabellón oficial exacto de cada encuentro, competición y fechas provisionales (`POR CONFIRMAR`).
   - **Extracción blindada de equipos (Local y Visitante):** Verifica secuencialmente `div.nombre_equipo`, `<img alt>`, `<a title>` y enlaces de equipo en Unicaja, y limpia títulos de `<svg>` (`Advancing to next round...`) y sufijos de país (`(Esp)`) en Flashscore.

2. **Resolución Inteligente de Estadios y Pabellones:**
   - Asigna automáticamente el **Estadio La Rosaleda, Málaga** y el **Palacio de Deportes José María Martín Carpena, Málaga** cuando juegan en casa.
   - Obtiene el recinto oficial de las fichas de cada club y dispone de un diccionario completo de respaldo con todos los estadios de **LaLiga (1ª y 2ª División)** y pabellones de **Liga Endesa (ACB) y BCL** para que ningún partido visitante quede como `"Pabellón por confirmar"` ni `"Estadio Visitante"`.

3. **Motor de Reconciliación y Anti-Duplicados:**
   - Normaliza todos los alias de equipos rivales (`Racing Santander` $\leftrightarrow$ `R. Racing Club`, `Betis` $\leftrightarrow$ `Real Betis`, `Alaves` $\leftrightarrow$ `Deportivo Alavés`, etc.).
   - Cuando se confirma el horario de un partido y cambia del domingo provisional al viernes, sábado o lunes ($\pm 12$ días), el motor reemplaza automáticamente el evento provisional sin dejar eventos fantasma duplicados.
   - **Protección anti-borrado e idempotencia (`DTSTAMP`):** Conserva los eventos previos si alguna fuente falla puntualmente y mantiene el `DTSTAMP` intacto si los datos del partido no han variado, evitando commits innecesarios.

4. **Actualización Automática Post-Partido (GitHub Actions):**
   - El workflow [`.github/workflows/main.yml`](.github/workflows/main.yml) se ejecuta diariamente tras cada franja horaria de partidos (mediodía, tarde, competiciones europeas y noche) y tras los anuncios de horarios, pasando primero toda la batería de tests (`pytest`) antes de publicar cambios.

---

## 🧪 Ejecución Local y Plan de Pruebas

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Actualizar el calendario (partidos.ics) y el portal web (index.html)
python malagacalendar.py

# 3. Ejecutar la suite de tests unitarios y de integración
PYTHONPATH=. pytest -v
```
