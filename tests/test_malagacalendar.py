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

    # Normalización canónica Futsal (RFAF Heredia 21)
    assert mc.normalizar_nombre_equipo("CLUB DEPORTIVO HEREDIA 21 FS", "futsal") == "Heredia 21 FS"
    assert mc.normalizar_nombre_equipo("C.D. U.D. PLAYAS DE MÁLAGA F.S.", "futsal") == "UD Playas de Málaga FS"
    assert mc.normalizar_nombre_equipo("CLUB DEPORTIVO CAMPILLOS FUTBOL SALA FEMENINO", "futsal") == "CD Campillos FS Femenino"


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


def test_resolver_pabellon_futsal():
    # Local de Heredia 21 por defecto es Pabellón Cubierto Rubén Ruzafa (Rincón de la Victoria)
    assert mc.resolver_pabellon_futsal("Heredia 21 FS") == mc.PABELLON_HEREDIA21_LOCAL
    assert "Rubén Ruzafa" in mc.PABELLON_HEREDIA21_LOCAL
    assert mc.resolver_pabellon_futsal("CLUB DEPORTIVO HEREDIA 21 FS", "Pabellón por confirmar") == mc.PABELLON_HEREDIA21_LOCAL
    assert mc.resolver_pabellon_futsal(
        "CLUB DEPORTIVO HEREDIA 21 FS",
        "Rincón de la Victoria - Rubén Ruzafa Pabellón Municipal (Pabellón) (PQ)",
    ) == mc.PABELLON_HEREDIA21_LOCAL
    # Si RFAF aún muestra Carranque como placeholder de ficha en jornadas futuras sin confirmar
    assert mc.resolver_pabellon_futsal(
        "CLUB DEPORTIVO HEREDIA 21 FS",
        "Málaga - Carranque Ciudad Deportiva (Pabellón) (PQ)",
    ) == mc.PABELLON_HEREDIA21_LOCAL

    # Si RFAF designa otro campo específico en la jornada (ej. J4 en Algarrobo o J3 en Malvaloca)
    assert "La Vega" in mc.resolver_pabellon_futsal(
        "CLUB DEPORTIVO HEREDIA 21 FS",
        "Algarrobo - La Vega Pabellón Municipal (Pabellón) (P)",
    )
    assert "Malvaloca" in mc.resolver_pabellon_futsal(
        "CLUB DEPORTIVO CAMPILLOS FUTBOL SALA FEMENINO",
        "Pista PISTA EXTERIOR - COMPLEJO DEPORTIVO DE MALVALOCA (MÁLAGA) (XC)",
    )

    # Visitantes de la liga malagueña
    assert "La Princesa" in mc.resolver_pabellon_futsal("C.D. U.D. PLAYAS DE MÁLAGA F.S.")
    assert "Casabermeja" in mc.resolver_pabellon_futsal("C.D. TORRE DE CASABERMEJA")
    assert "San Miguel" in mc.resolver_pabellon_futsal("CLUB TORREMOLINOS F.S.")
    assert "Elena Benítez" in mc.resolver_pabellon_futsal("C.D. SAMPEDREÑO FUTSAL")


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


# --- 3B. TESTS DE EXTRACCIÓN HTML RFAF (HEREDIA 21 FEMENINO FS) ---
def test_parsear_partidos_heredia21_html():
    ano_temp = mc.ANO_INICIO_TEMPORADA
    html_rfaf = f"""
    <table class="table">
      <tr>
        <td><h5>1</h5></td>
        <td>
          <h5>C.D. U.D. PLAYAS DE MÁLAGA F.S.</h5>
          <h5>CLUB DEPORTIVO HEREDIA 21 FS</h5>
          <h5>16-10-{ano_temp} &nbsp;21:30</h5>
        </td>
        <td><b>1</b> - <b> 2</b>&nbsp;<span class="badge">G</span></td>
      </tr>
      <tr>
        <td><h5>5</h5></td>
        <td>
          <h5>C.D. TORRE DE CASABERMEJA</h5>
          <h5>CLUB DEPORTIVO HEREDIA 21 FS</h5>
          <h5>20-11-{ano_temp} &nbsp;21:30</h5>
        </td>
        <td>-</td>
      </tr>
      <tr>
        <td><h5>6</h5></td>
        <td>
          <h5>CLUB DEPORTIVO HEREDIA 21 FS</h5>
          <h5>C.V. AV EL TORCAL</h5>
          <h5>29-11-{ano_temp}</h5>
        </td>
        <td>-</td>
      </tr>
      <tr>
        <td><h5>Final</h5></td>
        <td>
          <h5>C.D. SAMPEDREÑO FUTSAL</h5>
          <h5>CLUB DEPORTIVO HEREDIA 21 FS</h5>
          <h5>24-05-{ano_temp - 1} &nbsp;13:00</h5>
        </td>
        <td><b>2</b> - <b> 1</b></td>
      </tr>
    </table>
    """
    proximos, resultados = mc.parsear_partidos_heredia21_html(html_rfaf, "2ª Andaluza Femenina Sénior F.S.")

    # El partido de la temporada pasada (24-05-{ano_temp - 1}) debe filtrarse
    assert len(resultados) == 1
    assert len(proximos) == 2

    # Resultado Jornada 1
    assert resultados[0]["name"] == "UD Playas de Málaga FS vs Heredia 21 FS"
    assert resultados[0]["resultado"] == "1 - 2"
    assert "La Princesa" in resultados[0]["estadio"]
    assert resultados[0]["deporte"] == "futsal"

    # Próximo con hora confirmada (J5)
    assert proximos[0]["name"] == "CD Torre de Casabermeja vs Heredia 21 FS"
    assert proximos[0]["hora_confirmada"] is True
    assert "Casabermeja" in proximos[0]["estadio"]

    # Próximo en casa sin hora confirmada (J6)
    assert proximos[1]["name"] == "Heredia 21 FS vs CV AV El Torcal"
    assert proximos[1]["hora_confirmada"] is False
    assert "Hora por confirmar" in proximos[1]["descripcion"]
    assert "Rubén Ruzafa" in proximos[1]["estadio"]

    # Test de lectura de campos designados en NFG_VisCalendario_Vis (CDetalle=1) y NFG_CmpJornada
    html_cal_det = f"""
    <div class="row">
      <div class="col-sm-7 col-xs-12">
        <table width="100%">
          <tr>
            <td width="45%"><strong><span>CLUB DEPORTIVO HEREDIA 21 FS</span></strong></td>
            <td>-</td>
            <td width="45%"><strong><span>C.V. AV EL TORCAL</span></strong></td>
          </tr>
        </table>
      </div>
      <div class="col-sm-5 col-xs-12 right font_responsive">
        <i class="fa fa-map-marker"></i> Rincón de la Victoria - Rubén Ruzafa Pabellón Municipal (Pabellón)&nbsp;(PQ)
        <br/><i class="fa fa-clock"></i> 29-11-{ano_temp} - 21:00
      </div>
    </div>
    """
    html_cmp_jornada = f"""
    <table width="100%">
      <tr>
        <td class="td_widget"><a href="NFG_VisEquipos?Codigo_Equipo=1">C.D. TORRE DE CASABERMEJA</a></td>
        <td><span class="horario">20-11-{ano_temp}</span><span class="horario">21:30</span></td>
        <td class="td_widget"><a href="NFG_VisEquipos?Codigo_Equipo=2">CLUB DEPORTIVO HEREDIA 21 FS</a></td>
      </tr>
      <tr>
        <td colspan="9">
          <a href="/pnfg/NPcd/NFG_VisCampos?Codigo_Campo=999">Pista PISTA EXTERIOR - COMPLEJO DEPORTIVO DE MALVALOCA (MÁLAGA)</a>
        </td>
      </tr>
    </table>
    """
    campos_map = mc.parsear_campos_rfaf_html(html_cal_det)
    campos_map.update(mc.parsear_campos_rfaf_html(html_cmp_jornada))

    prox_con_campos, _ = mc.parsear_partidos_heredia21_html(
        html_rfaf,
        "2ª Andaluza Femenina Sénior F.S.",
        campos_rfaf=campos_map,
    )
    assert "Malvaloca" in prox_con_campos[0]["estadio"]
    assert "Rubén Ruzafa" in prox_con_campos[1]["estadio"]
    assert prox_con_campos[1]["hora_confirmada"] is True


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


# --- 5. TESTS DE RECONCILIACIÓN ICS Y CALENDARIOS MODULARES ---
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


def test_generar_todos_los_calendarios_ics_modulares():
    with tempfile.TemporaryDirectory() as tmpdir:
        eventos_mix = [
            {
                "fecha_hora_inicio": "2026-11-22T17:30:00+00:00",
                "fecha_hora_fin": "2026-11-22T19:30:00+00:00",
                "estadio": mc.ESTADIO_MALAGA_LOCAL,
                "name": "Málaga CF vs Real Sociedad",
                "descripcion": "Próximo partido Málaga CF",
                "deporte": "futbol",
                "hora_confirmada": True,
            },
            {
                "fecha_hora_inicio": "2026-11-18T19:30:00+00:00",
                "fecha_hora_fin": "2026-11-18T21:30:00+00:00",
                "estadio": mc.PABELLON_UNICAJA_LOCAL,
                "name": "Unicaja vs BK Kvis Pardubice",
                "descripcion": "Próximo partido Unicaja",
                "deporte": "basket",
                "hora_confirmada": True,
            },
            {
                "fecha_hora_inicio": "2026-11-20T20:30:00+00:00",
                "fecha_hora_fin": "2026-11-20T22:30:00+00:00",
                "estadio": "Pabellón Municipal de Casabermeja, Málaga",
                "name": "CD Torre de Casabermeja vs Heredia 21 FS",
                "descripcion": "Próximo partido Heredia 21 FS",
                "deporte": "futsal",
                "hora_confirmada": True,
            },
        ]
        rutas = mc.generar_todos_los_calendarios_ics(eventos_mix, directorio=tmpdir)
        assert len(rutas) == 7

        conteos_esperados = {
            "completo.ics": 3,
            "partidos.ics": 2,
            "malaga.ics": 1,
            "unicaja.ics": 1,
            "heredia21.ics": 1,
            "malaga_heredia21.ics": 2,
            "unicaja_heredia21.ics": 2,
        }
        for archivo, num_esp in conteos_esperados.items():
            ruta = rutas[archivo]
            assert os.path.exists(ruta)
            with open(ruta, "rb") as f:
                cal = Calendar.from_ical(f.read())
            vevents = [c for c in cal.walk() if c.name == "VEVENT"]
            assert len(vevents) == num_esp, f"Fallo en {archivo}: esperados {num_esp}, encontrados {len(vevents)}"


# --- 6. TEST DE INTEGRACIÓN SOBRE LOS ARCHIVOS REALES GENERADOS ---
def test_integracion_partidos_ics_real():
    for archivo in mc.CALENDARIOS_MODULARES:
        assert os.path.exists(archivo), f"Debe existir '{archivo}' tras la ejecución"

    with open("completo.ics", "rb") as f:
        cal = Calendar.from_ical(f.read())

    vevents = [c for c in cal.walk() if c.name == "VEVENT"]
    assert len(vevents) >= 75, f"Se esperaban al menos 75 partidos en completo.ics, encontrados: {len(vevents)}"

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
    partidos_heredia21 = 0
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
        if "Heredia 21 FS" in summary:
            partidos_heredia21 += 1
            if summary.startswith("Heredia 21 FS vs "):
                assert (
                    "Rubén Ruzafa" in location or "La Vega" in location
                ), f"Heredia 21 local sin Rubén Ruzafa ni campo RFAF designado: {summary} -> {location}"

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
    assert partidos_heredia21 >= 15, f"Se esperaban >=15 partidos de Heredia 21 FS, hay {partidos_heredia21}"


