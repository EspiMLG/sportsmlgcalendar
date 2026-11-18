import os
import tempfile
import datetime as dt
import pytest
from icalendar import Calendar

import malagacalendar as mc


# --- 1. TESTS DE FECHAS Y NORMALIZACIÓN ---
def test_traducir_fecha_malaga_a_numeros():
    assert mc.traducir_fecha_malaga_a_numeros("sáb 7 de nov") == "07.11"
    assert mc.traducir_fecha_malaga_a_numeros("mié, 21 de abr") == "21.04"
    assert mc.traducir_fecha_malaga_a_numeros("dom 3 de ene") == "03.01"
    assert mc.traducir_fecha_malaga_a_numeros("Sat, Nov 7") == "07.11"
    assert mc.traducir_fecha_malaga_a_numeros("8 nov") == "08.11"
    assert mc.traducir_fecha_malaga_a_numeros("") is None
    assert mc.traducir_fecha_malaga_a_numeros("Fecha sin sentido") is None


def test_limpiar_y_normalizar_nombres_equipos():
    # Limpieza de textos basura de Flashscore (SVGs y códigos de país)
    assert mc.limpiar_nombre_equipo_raw("Malaga Advancing to next round: Malaga") == "Malaga"
    assert mc.limpiar_nombre_equipo_raw("Malaga (Esp)") == "Malaga"
    assert mc.limpiar_nombre_equipo_raw("Fulham (Eng)") == "Fulham"

    # Normalización canónica Fútbol
    assert mc.normalizar_nombre_equipo("Malaga Advancing to next round: Malaga", "futbol") == "Málaga CF"
    assert mc.normalizar_nombre_equipo("Malaga (Esp)", "futbol") == "Málaga CF"
    assert mc.normalizar_nombre_equipo("Racing Santander", "futbol") == "R. Racing Club"
    assert mc.normalizar_nombre_equipo("Betis", "futbol") == "Real Betis"
    assert mc.normalizar_nombre_equipo("Alaves", "futbol") == "Deportivo Alavés"
    assert mc.normalizar_nombre_equipo("Alcazar", "futbol") == "Alcázar"
    assert mc.normalizar_nombre_equipo("Espanyol", "futbol") == "RCD Espanyol de Barcelona"

    # Normalización canónica Basket
    assert mc.normalizar_nombre_equipo("Unicaja Baloncesto", "basket") == "Unicaja"
    assert mc.normalizar_nombre_equipo("Surne Bilbao Basket", "basket") == "Surne Bilbao"
    assert mc.normalizar_nombre_equipo("Baskonia", "basket") == "Kosner Baskonia"


# --- 2. TESTS DE ESTADIOS Y PABELLONES (LOCAL Y VISITANTE) ---
def test_resolver_estadio_futbol():
    # Local siempre La Rosaleda
    assert mc.resolver_estadio_futbol("Málaga CF") == mc.ESTADIO_MALAGA_LOCAL
    assert mc.resolver_estadio_futbol("Malaga", "Estadio Visitante") == mc.ESTADIO_MALAGA_LOCAL

    # Visitante ignora placeholders genéricos y resuelve el estadio real
    assert "Sadar" in mc.resolver_estadio_futbol("CA Osasuna", "Estadio Visitante")
    assert "Sardinero" in mc.resolver_estadio_futbol("Racing Santander", "Estadio Visitante (Flashscore)")
    assert "Mendizorroza" in mc.resolver_estadio_futbol("Alaves", None)

    # Respeta nombre oficial si viene de la API del club
    assert mc.resolver_estadio_futbol("Real Betis", "Estadio La Cartuja de Sevilla") == "Estadio La Cartuja de Sevilla"


def test_resolver_pabellon_basket():
    # Local siempre Martín Carpena
    assert mc.resolver_pabellon_basket("Unicaja") == mc.PABELLON_UNICAJA_LOCAL
    assert mc.resolver_pabellon_basket("Unicaja", "Pabellón por confirmar") == mc.PABELLON_UNICAJA_LOCAL
    assert mc.resolver_pabellon_basket("Unicaja", "Pabellón (Resultado)") == mc.PABELLON_UNICAJA_LOCAL

    # Visitante ignora placeholders y resuelve el pabellón real del equipo local
    assert "Movistar Arena" in mc.resolver_pabellon_basket("Real Madrid", "Pabellón (Resultado)")
    assert "Palau Blaugrana" in mc.resolver_pabellon_basket("Barça", "Pabellón por confirmar")
    assert "Príncipe Felipe" in mc.resolver_pabellon_basket("Casademont Zaragoza", None)
    assert "Enteria Arena" in mc.resolver_pabellon_basket("BK Kvis Pardubice", None)


# --- 3. TESTS DE EXTRACCIÓN HTML UNICAJA (VISITANTE SIN TEXTO Y 'POR CONFIRMAR') ---
def test_parsear_calendario_unicaja_visitante_sin_texto_y_por_confirmar():
    html_mock = """
    <section class="contenedora_calendario">
      <h1 class="titulo_principal">Noviembre</h1>
      <!-- Partido 1: Unicaja local vs visitante cuyo nombre solo está en img[alt] -->
      <div class="fila fila_interior">
        <div class="celda prioridad-1 fecha">Miércoles 18<br/><span>20:30</span></div>
        <div class="celda prioridad-1 competicion">
          <div class="contenedor_logo_competicion">
            <img src="/Documentos/Logos_competiciones/logo-9.jpg"/>
            <span class="jornada">1ª Fase</span>
          </div>
        </div>
        <div class="celda prioridad-1 enfrentamiento">
          <div class="contenedor_logo_equipo floatl">
            <div class="logo_equipo"><a href="/equipo/ver/3-unicaja.html" title="Unicaja"><img alt="Unicaja"/></a></div>
            <div class="nombre_equipo"></div>
          </div>
          <div class="marcador venta_entradas"></div>
          <div class="contenedor_logo_equipo floatr">
            <div class="logo_equipo"><a href="/rival/ver/31384.html"><img alt="BK Kvis Pardubice"/></a></div>
            <div class="nombre_equipo"></div>
          </div>
        </div>
      </div>
      <!-- Partido 2: Resultado pasado con visitante en a[title] -->
      <div class="fila fila_interior">
        <div class="celda prioridad-1 fecha">Domingo 8<br/><span>17:00</span></div>
        <div class="celda prioridad-1 enfrentamiento">
          <div class="contenedor_logo_equipo floatl">
            <div class="logo_equipo"><a href="/rival/ver/10.html" title="Casademont Zaragoza"></a></div>
            <div class="nombre_equipo"></div>
          </div>
          <div class="marcador resultado"><a href="/partido/ver/id/202627013">96 | 91</a></div>
          <div class="contenedor_logo_equipo floatr">
            <div class="logo_equipo"><a href="/equipo/ver/3-unicaja.html" title="Unicaja"></a></div>
            <div class="nombre_equipo"></div>
          </div>
        </div>
      </div>
    </section>
    <section class="contenedora_calendario">
      <h1 class="titulo_principal">Mayo</h1>
      <!-- Partido 3: Fecha POR CONFIRMAR rescatada por metadatos ICS -->
      <div class="fila fila_interior">
        <div class="celda prioridad-1 fecha"><span>POR<br/>CONFIRMAR</span></div>
        <div class="celda prioridad-1 competicion"><span class="jornada">J. 34</span></div>
        <div class="celda prioridad-1 enfrentamiento">
          <div class="contenedor_logo_equipo floatl">
            <div class="logo_equipo"><img alt="Unicaja"/></div>
            <div class="nombre_equipo"></div>
          </div>
          <div class="marcador"></div>
          <div class="contenedor_logo_equipo floatr">
            <div class="logo_equipo"><img alt="Leyma Coruña"/></div>
            <div class="nombre_equipo"></div>
          </div>
        </div>
      </div>
    </section>
    """
    info_equipos = {
        "Unicaja vs Leyma Coruña": {
            "match_id": "202627040",
            "competicion": "Liga Endesa (Jornada 34)",
            "dtstart": dt.date(mc.ANO_INICIO_TEMPORADA + 1, 5, 21),
            "pabellon": "Palacio Municipal de los Deportes José María Martín Carpena",
        }
    }
    proximos, resultados = mc.parsear_calendario_unicaja_html(html_mock, info_equipos, {})

    assert len(proximos) == 2
    assert len(resultados) == 1

    # Verificar que el visitante nunca se perdió ni quedó como 'Unicaja vs Unicaja'
    assert proximos[0]["name"] == "Unicaja vs BK Kvis Pardubice"
    assert "Martín Carpena" in proximos[0]["estadio"]

    # Verificar partido 'POR CONFIRMAR' rescatado
    assert proximos[1]["name"] == "Unicaja vs Leyma Coruña"
    assert proximos[1]["hora_confirmada"] is False
    assert "Hora por confirmar" in proximos[1]["descripcion"]

    # Verificar resultado y pabellón visitante
    assert resultados[0]["name"] == "Casademont Zaragoza vs Unicaja"
    assert resultados[0]["resultado"] == "96 - 91"
    assert "Príncipe Felipe" in resultados[0]["estadio"]


# --- 4. TESTS DE FLASHSCORE (FILTRO AMISTOSOS Y LIMPIEZA SVG) ---
def test_parsear_resultados_flashscore_html():
    html_fs = """
    <div class="sportName soccer">
      <div class="headerLeague__wrapper">WORLD: Club Friendly</div>
      <div class="event__match">
        <span data-testid="wcl-stageTime">12.08. 19:00</span>
        <div class="event__homeParticipant"><span data-testid="wcl-simple-text-01">Malaga (Esp)</span></div>
        <div class="event__awayParticipant"><span data-testid="wcl-simple-text-01">Fulham (Eng)</span></div>
        <span class="event__score--home">2</span>
        <span class="event__score--away">2</span>
      </div>

      <div class="headerLeague__wrapper">SPAIN: Copa del Rey</div>
      <div class="event__match">
        <span data-testid="wcl-stageTime">27.10. 20:00</span>
        <div class="event__homeParticipant"><span data-testid="wcl-simple-text-01">Alcazar</span></div>
        <div class="event__awayParticipant">
          <span data-testid="wcl-simple-text-01">Malaga</span>
          <svg><title>Advancing to next round: Malaga</title></svg>
        </div>
        <span class="event__score--home">0</span>
        <span class="event__score--away">3</span>
      </div>
    </div>
    """
    eventos = mc.parsear_resultados_flashscore_html(html_fs)
    # El amistoso 'WORLD: Club Friendly' debe ser ignorado y el de Copa debe tener el nombre limpio
    assert len(eventos) == 1
    assert eventos[0]["name"] == "Alcázar vs Málaga CF"
    assert eventos[0]["resultado"] == "0 - 3"
    assert "Manuel Delgado Meco" in eventos[0]["estadio"]


# --- 5. TESTS DE RECONCILIACIÓN ICS (ADIÓS DUPLICADOS Y PROTECCIÓN ANTI-BORRADO) ---
def test_reconciliacion_ics_cambio_fecha_y_resultado():
    with tempfile.TemporaryDirectory() as tmpdir:
        ruta_ics = os.path.join(tmpdir, "test_partidos.ics")

        # Paso 1: Generar ICS inicial con un partido el domingo 29/11 sin hora confirmada
        # y otro contra Racing Santander con nombre sin normalizar
        eventos_iniciales = [
            {
                "fecha_hora_inicio": "2026-11-29T02:00:00+00:00",
                "fecha_hora_fin": "2026-11-29T04:00:00+00:00",
                "estadio": "Estadio La Rosaleda",
                "name": "Málaga CF vs Athletic Club",
                "descripcion": "Próximo partido Málaga CF (Hora por confirmar)",
                "hora_confirmada": False,
            },
            {
                "fecha_hora_inicio": "2026-11-07T13:00:00+00:00",
                "fecha_hora_fin": "2026-11-07T15:00:00+00:00",
                "estadio": "Estadio La Rosaleda",
                "name": "Málaga CF vs R. Racing Club",
                "descripcion": "Próximo partido Málaga CF",
                "hora_confirmada": True,
            },
            {
                "fecha_hora_inicio": "2026-12-06T18:00:00+00:00",
                "fecha_hora_fin": "2026-12-06T20:00:00+00:00",
                "estadio": "Pabellón por confirmar",
                "name": "Unicaja vs Valencia Basket",
                "descripcion": "Próximo partido Unicaja",
                "hora_confirmada": True,
            }
        ]
        mc.generar_archivo_ics(eventos_iniciales, ruta_ics)

        # Paso 2: En la siguiente ejecución:
        # - El partido del Athletic se confirma para el sábado 28/11 a las 15:15Z
        # - El partido del Racing ya tiene resultado (incluso si entrara como 'Racing Santander')
        # - Unicaja no devuelve eventos (simulando caída temporal de la web de Unicaja)
        eventos_actualizados = [
            {
                "fecha_hora_inicio": "2026-11-28T15:15:00+00:00",
                "fecha_hora_fin": "2026-11-28T17:15:00+00:00",
                "estadio": "Estadio La Rosaleda, Málaga",
                "name": "Málaga CF vs Athletic Club",
                "descripcion": "Próximo partido Málaga CF (LALIGA EA SPORTS - J14)",
                "hora_confirmada": True,
            },
            {
                "fecha_hora_inicio": "2026-11-07T13:00:00+00:00",
                "fecha_hora_fin": "2026-11-07T15:00:00+00:00",
                "estadio": "Estadio La Rosaleda, Málaga",
                "name": "Málaga CF vs Racing Santander",
                "descripcion": "Resultado Málaga CF: 1 - 2",
                "resultado": "1 - 2",
                "hora_confirmada": True,
            }
        ]
        mc.generar_archivo_ics(eventos_actualizados, ruta_ics)

        with open(ruta_ics, "rb") as f:
            cal = Calendar.from_ical(f.read())
        vevents = [c for c in cal.walk() if c.name == "VEVENT"]

        # Deben quedar exactamente 3 eventos (sin duplicar Athletic ni Racing, y conservando Unicaja)
        assert len(vevents) == 3

        summaries = [str(v.get("summary")) for v in vevents]
        uids = [str(v.get("uid")) for v in vevents]
        locations = {str(v.get("uid")): str(v.get("location")) for v in vevents}

        assert "Málaga CF vs R. Racing Club (1 - 2)" in summaries
        assert "20261128-MálagaCFvsAthleticClub@sportsmlg.com" in uids
        assert "20261129-MálagaCFvsAthleticClub@sportsmlg.com" not in uids
        # Además, el evento preservado de Unicaja debe haber reparado su ubicación a Martín Carpena
        assert "Martín Carpena" in locations["20261206-UnicajavsValenciaBasket@sportsmlg.com"]


# --- 6. TEST DE INTEGRACIÓN SOBRE EL ARCHIVO REAL GENERADO ---
def test_integracion_partidos_ics_real():
    assert os.path.exists("partidos.ics"), "Debe existir partidos.ics tras la ejecución"
    with open("partidos.ics", "rb") as f:
        cal = Calendar.from_ical(f.read())

    vevents = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(vevents) >= 60, f"Se esperaban al menos 60 partidos en la temporada, encontrados: {len(vevents)}"

    ubicaciones_prohibidas = {
        "pabellón por confirmar",
        "pabellon por confirmar",
        "pabellón (resultado)",
        "pabellon (resultado)",
        "estadio visitante",
        "estadio visitante (flashscore)",
        "lugar no especificado",
    }

    partidos_unicaja = 0
    partidos_malaga = 0
    ventana_enfrentamientos = {}

    for ev in vevents:
        uid = str(ev.get("uid", ""))
        summary = str(ev.get("summary", ""))
        location = str(ev.get("location", "")).strip()
        dt_inicio = ev.get("dtstart").dt

        # 1. Ningún partido debe tener ubicación genérica vacía o rota
        assert location.lower() not in ubicaciones_prohibidas, f"Ubicación genérica no resuelta en {uid}: {location}"
        assert len(location) >= 4, f"Ubicación vacía en {uid}"

        # 2. Ningún partido debe tener textos basura de Flashscore ni 'Unicaja vs Unicaja' ni 'Desconocido'
        assert "Advancing to next round" not in summary, f"Texto basura en summary: {summary}"
        assert "(Esp)" not in summary and "(Eng)" not in summary, f"Sufijo de país sin limpiar: {summary}"
        assert "Unicaja vs Unicaja" not in summary, f"Fallo de visitante en Unicaja: {summary}"
        assert "Desconocido" not in summary, f"Equipo desconocido en: {summary}"

        if "Unicaja" in summary:
            partidos_unicaja += 1
            if summary.startswith("Unicaja vs "):
                assert "Martín Carpena" in location, f"Unicaja local sin Martín Carpena: {summary} -> {location}"
        if "Málaga CF" in summary:
            partidos_malaga += 1
            if summary.startswith("Málaga CF vs "):
                assert "Rosaleda" in location, f"Málaga CF local sin La Rosaleda: {summary} -> {location}"

        # 3. Verificar que no existen partidos duplicados en una ventana de ±12 días
        titulo_base = summary.split(" (")[0].strip()
        fecha_d = dt_inicio.date() if isinstance(dt_inicio, dt.datetime) else dt_inicio
        if titulo_base in ventana_enfrentamientos:
            for fecha_prev in ventana_enfrentamientos[titulo_base]:
                dias_dif = abs((fecha_d - fecha_prev).days)
                assert dias_dif > 12, f"Partido duplicado en ventana cercana ({dias_dif} días): {titulo_base} ({fecha_prev} y {fecha_d})"
            ventana_enfrentamientos[titulo_base].append(fecha_d)
        else:
            ventana_enfrentamientos[titulo_base] = [fecha_d]

    assert partidos_unicaja >= 30, f"Se esperaban >=30 partidos de Unicaja, hay {partidos_unicaja}"
    assert partidos_malaga >= 30, f"Se esperaban >=30 partidos del Málaga CF, hay {partidos_malaga}"

