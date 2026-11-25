import os
import re
import json
import time
import random
import unicodedata
import datetime as dt
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from icalendar import Calendar, Event
from selenium_stealth import stealth

# --- ZONA HORARIA Y LÓGICA DE TEMPORADA ---
TZ_MADRID = ZoneInfo("Europe/Madrid")
ANO_ACTUAL = dt.datetime.now(TZ_MADRID).year
MES_ACTUAL = dt.datetime.now(TZ_MADRID).month

MES_INICIO_TEMPORADA = 8
ANO_INICIO_TEMPORADA = ANO_ACTUAL
if MES_ACTUAL < MES_INICIO_TEMPORADA:
    ANO_INICIO_TEMPORADA = ANO_ACTUAL - 1
FECHA_INICIO_TEMPORADA = dt.datetime(ANO_INICIO_TEMPORADA, MES_INICIO_TEMPORADA, 1)
print(f"INFO: Filtrando resultados de ambas webs anteriores al {FECHA_INICIO_TEMPORADA.strftime('%Y-%m-%d')}")
# --- FIN LÓGICA DE TEMPORADA ---

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

ESTADIO_MALAGA_LOCAL = "Estadio La Rosaleda, Málaga"
PABELLON_UNICAJA_LOCAL = "Palacio de Deportes José María Martín Carpena, Málaga"
PABELLON_HEREDIA21_LOCAL = "Pabellón Cubierto Rubén Ruzafa (Rincón de la Victoria)"

RFAF_CODIGO_EQUIPO_HEREDIA21 = "46655793"
RFAF_CODGRUPO_HEREDIA21_DEFAULT = "48466076"
RFAF_CODCOMPETICION_HEREDIA21_DEFAULT = "48466075"
RFAF_CODTEMPORADA_HEREDIA21_DEFAULT = "22"
RFAF_URL_EQUIPO_HEREDIA21 = (
    f"https://www.rfaf.es/pnfg/NPcd/NFG_VisEquipos?cod_primaria=1000119&Codigo_Equipo={RFAF_CODIGO_EQUIPO_HEREDIA21}"
)

CALENDARIOS_MODULARES = {
    "completo.ics": {
        "deportes": {"futbol", "basket", "futsal"},
        "calname": "Calendario Málaga CF, Unicaja y Heredia 21 FS",
        "etiqueta": "Málaga CF + Unicaja + Heredia 21 FS",
    },
    "partidos.ics": {
        "deportes": {"futbol", "basket"},
        "calname": "Calendario Málaga CF y Unicaja",
        "etiqueta": "Málaga CF + Unicaja",
    },
    "malaga.ics": {
        "deportes": {"futbol"},
        "calname": "Calendario Málaga CF",
        "etiqueta": "Solo Málaga CF",
    },
    "unicaja.ics": {
        "deportes": {"basket"},
        "calname": "Calendario Unicaja Baloncesto",
        "etiqueta": "Solo Unicaja Baloncesto",
    },
    "heredia21.ics": {
        "deportes": {"futsal"},
        "calname": "Calendario Heredia 21 Femenino FS",
        "etiqueta": "Solo Heredia 21 FS",
    },
    "malaga_heredia21.ics": {
        "deportes": {"futbol", "futsal"},
        "calname": "Calendario Málaga CF y Heredia 21 FS",
        "etiqueta": "Málaga CF + Heredia 21 FS",
    },
    "unicaja_heredia21.ics": {
        "deportes": {"basket", "futsal"},
        "calname": "Calendario Unicaja y Heredia 21 FS",
        "etiqueta": "Unicaja + Heredia 21 FS",
    },
}

# --- DICCIONARIOS DE NORMALIZACIÓN DE EQUIPOS Y RECINTOS ---
ALIAS_EQUIPOS_FUTBOL = {
    "malaga": "Málaga CF",
    "málaga": "Málaga CF",
    "malaga cf": "Málaga CF",
    "málaga cf": "Málaga CF",
    "malaga club de futbol": "Málaga CF",
    "malaga club de futbol sad": "Málaga CF",
    "racing santander": "R. Racing Club",
    "real racing club": "R. Racing Club",
    "r. racing club": "R. Racing Club",
    "racing": "R. Racing Club",
    "betis": "Real Betis",
    "real betis": "Real Betis",
    "real betis balompie": "Real Betis",
    "alaves": "Deportivo Alavés",
    "deportivo alaves": "Deportivo Alavés",
    "d. alaves": "Deportivo Alavés",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "getafe": "Getafe CF",
    "getafe cf": "Getafe CF",
    "villarreal": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
    "celta vigo": "Celta",
    "rc celta": "Celta",
    "celta": "Celta",
    "levante": "Levante UD",
    "levante ud": "Levante UD",
    "dep. a coruna": "RC Deportivo",
    "deportivo la coruna": "RC Deportivo",
    "rc deportivo": "RC Deportivo",
    "atl. madrid": "Atlético de Madrid",
    "atletico madrid": "Atlético de Madrid",
    "atletico de madrid": "Atlético de Madrid",
    "alcazar": "Alcázar",
    "sporting de alcazar": "Alcázar",
    "alcázar": "Alcázar",
    "osasuna": "CA Osasuna",
    "ca osasuna": "CA Osasuna",
    "athletic": "Athletic Club",
    "athletic bilbao": "Athletic Club",
    "athletic club": "Athletic Club",
    "sevilla": "Sevilla FC",
    "sevilla fc": "Sevilla FC",
    "barcelona": "FC Barcelona",
    "fc barcelona": "FC Barcelona",
    "rayo": "Rayo Vallecano",
    "rayo vallecano": "Rayo Vallecano",
    "elche": "Elche CF",
    "elche cf": "Elche CF",
    "valencia": "Valencia CF",
    "valencia cf": "Valencia CF",
    "real madrid": "Real Madrid",
    "real sociedad": "Real Sociedad",
}

ESTADIOS_FUTBOL = {
    "Málaga CF": ESTADIO_MALAGA_LOCAL,
    "CA Osasuna": "Estadio El Sadar, Pamplona",
    "Athletic Club": "Estadio de San Mamés, Bilbao",
    "Sevilla FC": "Estadio Ramón Sánchez-Pizjuán, Sevilla",
    "FC Barcelona": "Spotify Camp Nou, Barcelona",
    "Rayo Vallecano": "Estadio de Vallecas, Madrid",
    "Elche CF": "Estadio Martínez Valero, Elche",
    "Valencia CF": "Estadio de Mestalla, Valencia",
    "Real Madrid": "Estadio Santiago Bernabéu, Madrid",
    "Real Sociedad": "Reale Arena (Anoeta), San Sebastián",
    "Deportivo Alavés": "Estadio de Mendizorroza, Vitoria",
    "RC Deportivo": "Estadio ABANCA-Riazor, A Coruña",
    "Levante UD": "Estadio Ciutat de València, Valencia",
    "Real Betis": "Estadio Benito Villamarín / La Cartuja, Sevilla",
    "Atlético de Madrid": "Riyadh Air Metropolitano, Madrid",
    "Villarreal CF": "Estadio de la Cerámica, Villarreal",
    "RCD Espanyol de Barcelona": "RCDE Stadium, Cornellà-El Prat",
    "R. Racing Club": "Campos de Sport de El Sardinero, Santander",
    "Getafe CF": "Coliseum, Getafe",
    "Celta": "Estadio ABANCA Balaídos, Vigo",
    "Alcázar": "Estadio Municipal Manuel Delgado Meco, Alcázar de San Juan",
    "Girona FC": "Estadi Montilivi, Girona",
    "RCD Mallorca": "Estadi Mallorca Son Moix, Palma",
    "UD Las Palmas": "Estadio Gran Canaria, Las Palmas",
    "CD Leganés": "Estadio Municipal Butarque, Leganés",
    "Real Valladolid": "Estadio José Zorrilla, Valladolid",
    "Cádiz CF": "Estadio Nuevo Mirandilla, Cádiz",
    "Granada CF": "Estadio Nuevo Los Cármenes, Granada",
    "UD Almería": "UD Almería Stadium, Almería",
    "Sporting de Gijón": "Estadio El Molinón, Gijón",
    "Real Oviedo": "Estadio Carlos Tartiere, Oviedo",
    "Real Zaragoza": "Estadio La Romareda, Zaragoza",
    "SD Eibar": "Estadio Municipal de Ipurua, Eibar",
    "CD Tenerife": "Estadio Heliodoro Rodríguez López, Tenerife",
    "Córdoba CF": "Estadio Bahrain Victorious Nuevo Arcángel, Córdoba",
    "Albacetes Balompié": "Estadio Carlos Belmonte, Albacete",
    "Burgos CF": "Estadio El Plantío, Burgos",
    "CD Castellón": "Estadio SkyFi Castalia, Castellón",
    "SD Huesca": "Estadio El Alcoraz, Huesca",
    "CD Mirandés": "Estadio Municipal de Anduva, Miranda de Ebro",
    "Racing de Ferrol": "Estadio Municipal de A Malata, Ferrol",
}

ALIAS_EQUIPOS_BASKET = {
    "unicaja": "Unicaja",
    "unicaja baloncesto": "Unicaja",
    "unicaja malaga": "Unicaja",
    "surne bilbao": "Surne Bilbao",
    "surne bilbao basket": "Surne Bilbao",
    "bilbao basket": "Surne Bilbao",
    "baskonia": "Kosner Baskonia",
    "kosner baskonia": "Kosner Baskonia",
    "cazoo baskonia": "Kosner Baskonia",
    "barca": "Barça",
    "barça": "Barça",
    "fc barcelona": "Barça",
    "real madrid": "Real Madrid",
    "valencia basket": "Valencia Basket",
    "ucam murcia": "UCAM Murcia",
    "ucam murcia cb": "UCAM Murcia",
    "la laguna tenerife": "La Laguna Tenerife",
    "lenovo tenerife": "La Laguna Tenerife",
    "cb canarias": "La Laguna Tenerife",
    "casademont zaragoza": "Casademont Zaragoza",
    "basket zaragoza": "Casademont Zaragoza",
    "morabanc andorra": "MoraBanc Andorra",
    "bc andorra": "MoraBanc Andorra",
    "asisa joventut": "Asisa Joventut",
    "joventut badalona": "Asisa Joventut",
    "joventut": "Asisa Joventut",
    "fiatc girona": "FIATC Girona",
    "basquet girona": "FIATC Girona",
    "bàsquet girona": "FIATC Girona",
    "ilerna lleida": "iLERNA Lleida",
    "hiopos lleida": "iLERNA Lleida",
    "forca lleida": "iLERNA Lleida",
    "rio breogan": "Río Breogán",
    "río breogán": "Río Breogán",
    "cb breogan": "Río Breogán",
    "leyma coruna": "Leyma Coruña",
    "leyma coruña": "Leyma Coruña",
    "basquet coruna": "Leyma Coruña",
    "monbus obradoiro": "Monbus Obradoiro",
    "obradoiro": "Monbus Obradoiro",
    "kids&us manresa": "Kids&Us Manresa",
    "baxi manresa": "Kids&Us Manresa",
    "basquet manresa": "Kids&Us Manresa",
    "recoletas salud san pablo burgos": "Recoletas Salud San Pablo Burgos",
    "san pablo burgos": "Recoletas Salud San Pablo Burgos",
    "longevida san pablo burgos": "Recoletas Salud San Pablo Burgos",
    "dreamland gran canaria": "Dreamland Gran Canaria",
    "gran canaria": "Dreamland Gran Canaria",
    "coviran granada": "Coviran Granada",
    "fundacion cb granada": "Coviran Granada",
    "bk kvis pardubice": "BK Kvis Pardubice",
    "bk pardubice": "BK Kvis Pardubice",
    "bc juventus utena": "BC Juventus Utena",
    "juventus utena": "BC Juventus Utena",
    "pallacanestro reggiana": "Pallacanestro Reggiana",
    "reggio emilia": "Pallacanestro Reggiana",
}

PABELLONES_BASKET = {
    "Unicaja": PABELLON_UNICAJA_LOCAL,
    "Real Madrid": "Movistar Arena, Madrid",
    "La Laguna Tenerife": "Pabellón Insular Santiago Martín, San Cristóbal de La Laguna",
    "BC Juventus Utena": "Utena Arena / Vilnius Arena, Lituania",
    "MoraBanc Andorra": "Pavelló Toni Martí, Andorra la Vella",
    "Kids&Us Manresa": "Pavelló Nou Congost, Manresa",
    "BK Kvis Pardubice": "Enteria Arena, Pardubice",
    "Río Breogán": "Pazo Provincial dos Deportes, Lugo",
    "Barça": "Palau Blaugrana, Barcelona",
    "Pallacanestro Reggiana": "PalaBigi, Reggio Emilia",
    "Casademont Zaragoza": "Pabellón Príncipe Felipe, Zaragoza",
    "FIATC Girona": "Pavelló Girona-Fontajau, Girona",
    "Recoletas Salud San Pablo Burgos": "Coliseum Burgos, Burgos",
    "Valencia Basket": "Roig Arena / Pabellón Fuente de San Luis, Valencia",
    "UCAM Murcia": "Palacio Municipal de Deportes, Murcia",
    "iLERNA Lleida": "Pavelló Barris Nord, Lleida",
    "Asisa Joventut": "Palau Municipal d'Esports de Badalona, Badalona",
    "Leyma Coruña": "Coliseum da Coruña, A Coruña",
    "Monbus Obradoiro": "Multiusos Fontes do Sar, Santiago de Compostela",
    "Surne Bilbao": "Bilbao Arena (Miribilla), Bilbao",
    "Kosner Baskonia": "Fernando Buesa Arena, Vitoria-Gasteiz",
    "Dreamland Gran Canaria": "Gran Canaria Arena, Las Palmas",
    "Coviran Granada": "Palacio Municipal de Deportes, Granada",
    "Mersin Msk": "Servet Tazegül Spor Salonu, Mersin",
    "Karditsa Iaponiki": "Giannis Bourousis Indoor Hall, Karditsa",
    "BC Oostende": "COREtec Dôme, Ostende",
}

ALIAS_EQUIPOS_FUTSAL = {
    "club deportivo heredia 21 fs": "Heredia 21 FS",
    "cd heredia 21 fs": "Heredia 21 FS",
    "heredia 21 fs": "Heredia 21 FS",
    "heredia 21": "Heredia 21 FS",
    "c.d. u.d. playas de malaga f.s.": "UD Playas de Málaga FS",
    "c.d. u.d. playas de málaga f.s.": "UD Playas de Málaga FS",
    "ud playas de malaga fs": "UD Playas de Málaga FS",
    "ud playas de málaga fs": "UD Playas de Málaga FS",
    "cd cuevas bajas atletico": "CD Cuevas Bajas Atlético",
    "cd cuevas bajas atlético": "CD Cuevas Bajas Atlético",
    "club deportivo campillos futbol sala femenino": "CD Campillos FS Femenino",
    "cd campillos fs femenino": "CD Campillos FS Femenino",
    "c.d. axarquia f.s. ayuntamiento algarrobo": "CD Axarquía FS Algarrobo",
    "cd axarquia fs algarrobo": "CD Axarquía FS Algarrobo",
    "cd axarquía fs algarrobo": "CD Axarquía FS Algarrobo",
    "c.d. torre de casabermeja": "CD Torre de Casabermeja",
    "cd torre de casabermeja": "CD Torre de Casabermeja",
    "c.v. av el torcal": "CV AV El Torcal",
    "cv av el torcal": "CV AV El Torcal",
    "club de futbol arriate": "CF Arriate",
    "cf arriate": "CF Arriate",
    "club torremolinos f.s.": "Club Torremolinos FS",
    "club torremolinos fs": "Club Torremolinos FS",
    "c.d. sampedreno futsal": "CD Sampedreño Futsal",
    "c.d. sampedreño futsal": "CD Sampedreño Futsal",
    "cd sampedreno futsal": "CD Sampedreño Futsal",
    "cd sampedreño futsal": "CD Sampedreño Futsal",
}

PABELLONES_FUTSAL = {
    "Heredia 21 FS": PABELLON_HEREDIA21_LOCAL,
    "UD Playas de Málaga FS": "Polideportivo Municipal La Princesa (Pista Ext.), Málaga",
    "CD Cuevas Bajas Atlético": "Polideportivo Municipal de Cuevas Bajas, Málaga",
    "CD Campillos FS Femenino": "Pabellón Municipal de Campillos, Málaga",
    "CD Axarquía FS Algarrobo": "Pabellón Municipal La Vega, Algarrobo (Málaga)",
    "CD Torre de Casabermeja": "Pabellón Municipal de Casabermeja, Málaga",
    "CV AV El Torcal": "Pista Polideportiva Municipal El Torcal, Málaga",
    "CF Arriate": "Pabellón Municipal de Arriate, Málaga",
    "Club Torremolinos FS": "Pabellón Municipal San Miguel, Torremolinos (Málaga)",
    "CD Sampedreño Futsal": "Pabellón Municipal Elena Benítez, San Pedro Alcántara (Marbella)",
}


def _quitar_acentos(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def limpiar_nombre_equipo_raw(nombre):
    """Limpia textos parásitos de Flashscore o de otras webs (ej. 'Advancing to next round...', '(Esp)')."""
    if not nombre:
        return ""
    limpio = str(nombre).strip()
    # Eliminar textos de clasificación/prórroga pegados por SVGs de Flashscore
    limpio = re.sub(r'\s*Advancing to next round:.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'\s*Qualified for.*$', '', limpio, flags=re.IGNORECASE)
    # Eliminar códigos de país entre paréntesis como (Esp), (Eng), (Qat)
    limpio = re.sub(r'\s*\([A-Za-z]{2,4}\)\s*$', '', limpio)
    limpio = re.sub(r'\s+', ' ', limpio).strip()
    return limpio


def normalizar_nombre_equipo(nombre, deporte="futbol"):
    """Normaliza un nombre de equipo a su nombre canónico oficial."""
    limpio = limpiar_nombre_equipo_raw(nombre)
    if not limpio:
        return "Desconocido"
    clave_exacta = limpio.lower()
    clave_sin_acentos = _quitar_acentos(clave_exacta)

    if deporte == "basket":
        mapa = ALIAS_EQUIPOS_BASKET
    elif deporte == "futsal":
        mapa = ALIAS_EQUIPOS_FUTSAL
    else:
        mapa = ALIAS_EQUIPOS_FUTBOL

    if clave_exacta in mapa:
        return mapa[clave_exacta]
    if clave_sin_acentos in mapa:
        return mapa[clave_sin_acentos]
    return limpio


def resolver_estadio_futbol(equipo_local, estadio_web=None):
    """Devuelve siempre el estadio más preciso para un partido de fútbol."""
    local_norm = normalizar_nombre_equipo(equipo_local, "futbol")
    if "málaga" in local_norm.lower() or "malaga" in local_norm.lower():
        return ESTADIO_MALAGA_LOCAL

    if estadio_web:
        est_limpio = estadio_web.strip()
        genericos = {"estadio visitante", "estadio visitante (flashscore)", "por confirmar", "tbd", "-"}
        if est_limpio and est_limpio.lower() not in genericos:
            if "rosaleda" in est_limpio.lower():
                return ESTADIO_MALAGA_LOCAL
            return est_limpio

    if local_norm in ESTADIOS_FUTBOL:
        return ESTADIOS_FUTBOL[local_norm]

    # Búsqueda flexible por subcadena sin acentos
    local_sin = _quitar_acentos(local_norm.lower())
    for eq, est in ESTADIOS_FUTBOL.items():
        eq_sin = _quitar_acentos(eq.lower())
        if eq_sin in local_sin or local_sin in eq_sin:
            return est

    if local_norm and local_norm != "Desconocido":
        return f"Estadio de {local_norm}"
    return "Estadio por confirmar"


def resolver_pabellon_basket(equipo_local, pabellon_web=None):
    """Devuelve siempre el pabellón más preciso para un partido de baloncesto."""
    local_norm = normalizar_nombre_equipo(equipo_local, "basket")
    if "unicaja" in local_norm.lower():
        return PABELLON_UNICAJA_LOCAL

    if pabellon_web:
        pab_limpio = pabellon_web.strip()
        genericos = {
            "pabellón por confirmar", "pabellon por confirmar",
            "pabellón (resultado)", "pabellon (resultado)",
            "por confirmar", "tbd", "-"
        }
        if pab_limpio and pab_limpio.lower() not in genericos:
            if "carpena" in pab_limpio.lower():
                return PABELLON_UNICAJA_LOCAL
            return pab_limpio

    if local_norm in PABELLONES_BASKET:
        return PABELLONES_BASKET[local_norm]

    local_sin = _quitar_acentos(local_norm.lower())
    for eq, pab in PABELLONES_BASKET.items():
        eq_sin = _quitar_acentos(eq.lower())
        if eq_sin in local_sin or local_sin in eq_sin:
            return pab

    if local_norm and local_norm != "Desconocido":
        return f"Pabellón de {local_norm}"
    return "Pabellón por confirmar"


def limpiar_campo_rfaf(campo_raw):
    """Limpia el nombre de un campo o pabellón extraído de la RFAF (sufijos de superficie como (PQ), (XC), (P), etc.)."""
    if not campo_raw:
        return ""
    limpio = str(campo_raw).replace("\xa0", " ").strip()
    # Eliminar códigos de superficie al final: (PQ), (XC), (P), (C), (H), (T), (A), (S)
    limpio = re.sub(r"\s*\((?:PQ|XC|P|C|H|T|A|S)\)\s*$", "", limpio, flags=re.IGNORECASE)
    # Limpiar prefijos redundantes como "Pista PISTA EXTERIOR"
    limpio = re.sub(r"^Pista\s+(?=PISTA\b)", "", limpio, flags=re.IGNORECASE)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio


def resolver_pabellon_futsal(equipo_local, pabellon_web=None):
    """Devuelve siempre el pabellón o pista oficial para un partido de fútbol sala femenino (RFAF)."""
    local_norm = normalizar_nombre_equipo(equipo_local, "futsal")
    es_heredia_local = "heredia 21" in local_norm.lower()

    if pabellon_web:
        pab_limpio = limpiar_campo_rfaf(pabellon_web)
        genericos = {
            "pabellón por confirmar", "pabellon por confirmar",
            "pabellón (resultado)", "pabellon (resultado)",
            "por confirmar", "tbd", "-"
        }
        if pab_limpio and pab_limpio.lower() not in genericos:
            pab_sin = _quitar_acentos(pab_limpio.lower())
            if "ruben ruzafa" in pab_sin or "rincon de la victoria" in pab_sin:
                return PABELLON_HEREDIA21_LOCAL
            if "carranque" in pab_sin:
                if es_heredia_local:
                    return PABELLON_HEREDIA21_LOCAL
                return "Ciudad Deportiva de Carranque (Pabellón), Málaga"
            if "malvaloca" in pab_sin:
                return "Complejo Deportivo de Malvaloca (Pista Ext.), Málaga"
            if "la princesa" in pab_sin:
                return PABELLONES_FUTSAL["UD Playas de Málaga FS"]
            if "cuevas bajas" in pab_sin:
                return PABELLONES_FUTSAL["CD Cuevas Bajas Atlético"]
            if "la vega" in pab_sin and "algarrobo" in pab_sin:
                return PABELLONES_FUTSAL["CD Axarquía FS Algarrobo"]
            if "casabermeja" in pab_sin or "casabemeja" in pab_sin:
                return PABELLONES_FUTSAL["CD Torre de Casabermeja"]
            if "el torcal" in pab_sin:
                return PABELLONES_FUTSAL["CV AV El Torcal"]
            if "arriate" in pab_sin:
                return PABELLONES_FUTSAL["CF Arriate"]
            if "san miguel" in pab_sin and "torremolinos" in pab_sin:
                return PABELLONES_FUTSAL["Club Torremolinos FS"]
            if "elena benitez" in pab_sin:
                return PABELLONES_FUTSAL["CD Sampedreño Futsal"]
            if "campillos" in pab_sin:
                return PABELLONES_FUTSAL["CD Campillos FS Femenino"]
            return pab_limpio

    if es_heredia_local:
        return PABELLON_HEREDIA21_LOCAL

    if local_norm in PABELLONES_FUTSAL:
        return PABELLONES_FUTSAL[local_norm]

    local_sin = _quitar_acentos(local_norm.lower())
    for eq, pab in PABELLONES_FUTSAL.items():
        eq_sin = _quitar_acentos(eq.lower())
        if eq_sin in local_sin or local_sin in eq_sin:
            return pab

    if local_norm and local_norm != "Desconocido":
        return f"Pabellón de {local_norm}"
    return "Pabellón por confirmar"


# --- FUNCIÓN 1: PRÓXIMOS Y RESULTADOS MÁLAGA CF (API OFICIAL + FALLBACK DOM) ---
def traducir_fecha_malaga_a_numeros(fecha_es):
    """
    Soporta formatos con o sin día de la semana y en ES/EN:
    'sáb 7 de nov', 'mié, 21 de abr', '8 nov', 'Nov 8', 'dom 3 de ene'
    """
    if not fecha_es:
        return None
    traduccion_a_numero = {
        'ene': '01', 'enero': '01', 'feb': '02', 'febrero': '02',
        'mar': '03', 'marzo': '03', 'abr': '04', 'abril': '04',
        'may': '05', 'mayo': '05', 'jun': '06', 'junio': '06',
        'jul': '07', 'julio': '07', 'ago': '08', 'agosto': '08',
        'sep': '09', 'sept': '09', 'septiembre': '09',
        'oct': '10', 'octubre': '10', 'nov': '11', 'noviembre': '11',
        'dic': '12', 'diciembre': '12',
        # Inglés por si el runner de GitHub recibe la web en inglés
        'jan': '01', 'january': '01', 'february': '02', 'march': '03',
        'apr': '04', 'april': '04', 'june': '06', 'july': '07',
        'aug': '08', 'august': '08', 'september': '09', 'october': '10',
        'november': '11', 'dec': '12', 'december': '12'
    }
    texto = str(fecha_es).lower().replace('.', '').replace(',', ' ').strip()

    # Patrón 1: Día (1-2 dígitos) + opcional "de" + Mes (letras) -> ej. "sáb 7 de nov"
    match_es = re.search(r'\b(\d{1,2})\s+(?:de\s+)?([a-záéíóú]{3,10})\b', texto)
    if match_es:
        dia = match_es.group(1).zfill(2)
        mes_str = match_es.group(2)
        mes_num = traduccion_a_numero.get(mes_str) or traduccion_a_numero.get(mes_str[:3])
        if mes_num:
            return f"{dia}.{mes_num}"

    # Patrón 2: Mes (letras) + Día (1-2 dígitos) -> ej. "Sat Nov 7"
    tokens = texto.split()
    for i in range(len(tokens) - 1):
        t1, t2 = tokens[i], tokens[i + 1]
        mes_num = traduccion_a_numero.get(t1) or traduccion_a_numero.get(t1[:3])
        if mes_num and t2.isdigit():
            return f"{t2.zfill(2)}.{mes_num}"

    return None


def _obtener_team_id_malaga(session):
    """Obtiene dinámicamente el teamId de la web oficial del Málaga CF con fallback seguro."""
    default_team_id = "03672ebf-f8a5-4921-8b2e-d21b2586de12"
    try:
        resp = session.get("https://www.malagacf.com/partidos", headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            nd = soup.find('script', id='__NEXT_DATA__')
            if nd and nd.string:
                data = json.loads(nd.string)
                grids = data.get('props', {}).get('pageProps', {}).get('data', {}).get('page', {}).get('grids', [])
                for g in grids:
                    for a in g.get('areas', []):
                        for m in a.get('modules', []):
                            tid = (m.get('data') or {}).get('teamId')
                            if tid:
                                return tid
    except Exception:
        pass
    return default_team_id


def obtener_partidos_malaga_api(active_tab="fixtures", session=None):
    """
    Consulta la API JSON oficial de malagacf.com para obtener todos los partidos
    ('fixtures' o 'results') con fecha/hora ISO exacta, estadio oficial y competición.
    """
    s = session or requests.Session()
    team_id = _obtener_team_id_malaga(s)
    todos_partidos_json = []
    offset = 0
    max_paginas = 10

    for _ in range(max_paginas):
        url = (
            f"https://www.malagacf.com/api/football_list/football_match"
            f"?locale=es&teamId={team_id}&activeTab={active_tab}&offset={offset}"
        )
        resp = s.get(url, headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code != 200:
            break
        payload = resp.json()
        lote = payload.get("data", [])
        if not lote:
            break
        todos_partidos_json.extend(lote)
        total = payload.get("total", 0)
        if len(todos_partidos_json) >= total:
            break
        offset += len(lote)

    eventos = []
    for item in todos_partidos_json:
        try:
            home_obj = item.get("homeTeam") or {}
            away_obj = item.get("awayTeam") or {}
            raw_local = home_obj.get("shortName") or home_obj.get("name") or "Desconocido"
            raw_visitante = away_obj.get("shortName") or away_obj.get("name") or "Desconocido"

            equipo_local = normalizar_nombre_equipo(raw_local, "futbol")
            equipo_visitante = normalizar_nombre_equipo(raw_visitante, "futbol")
            name = f"{equipo_local} vs {equipo_visitante}"

            date_str = item.get("date")  # ej. "2026-11-22"
            time_iso = item.get("time")  # ej. "2026-11-22T17:30:00Z" o None

            if not date_str:
                continue

            fecha_dt = dt.datetime.strptime(date_str[:10], "%Y-%m-%d")
            if fecha_dt < FECHA_INICIO_TEMPORADA:
                continue

            hora_confirmada = False
            if time_iso and "T" in str(time_iso):
                dt_utc = dt.datetime.fromisoformat(str(time_iso).replace("Z", "+00:00"))
                # Si en la API viene a las 00:00 UTC exactas y sin confirmar
                hora_madrid = dt_utc.astimezone(TZ_MADRID)
                if hora_madrid.hour == 0 and hora_madrid.minute == 0:
                    hora_confirmada = False
                    fecha_hora_inicio_local = dt.datetime(
                        fecha_dt.year, fecha_dt.month, fecha_dt.day, 3, 0, tzinfo=TZ_MADRID
                    )
                    fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                else:
                    hora_confirmada = True
                    fecha_hora_inicio_utc = dt_utc.astimezone(dt.timezone.utc)
            else:
                hora_confirmada = False
                fecha_hora_inicio_local = dt.datetime(
                    fecha_dt.year, fecha_dt.month, fecha_dt.day, 3, 0, tzinfo=TZ_MADRID
                )
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)

            fecha_hora_fin_utc = fecha_hora_inicio_utc + dt.timedelta(hours=2)

            venue_name = (item.get("venue") or {}).get("name") or item.get("venueName")
            estadio_final = resolver_estadio_futbol(equipo_local, venue_name)

            comp_name = (item.get("competition") or {}).get("name") or ""
            gw_obj = item.get("gameweek") or {}
            gw_name = gw_obj.get("name") or gw_obj.get("shortName") or ""
            info_comp = " - ".join(p for p in [comp_name, gw_name] if p)

            home_score = item.get("homeScore")
            away_score = item.get("awayScore")
            es_resultado = (
                active_tab == "results"
                or (home_score is not None and away_score is not None)
            )

            evento_dict = {
                "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                "estadio": estadio_final,
                "name": name,
                "deporte": "futbol",
                "competicion": info_comp,
                "hora_confirmada": hora_confirmada,
            }

            if es_resultado and home_score is not None and away_score is not None:
                resultado_final = f"{home_score} - {away_score}"
                desc = f"Resultado Málaga CF: {resultado_final}"
                if info_comp:
                    desc += f" | {info_comp}"
                evento_dict["descripcion"] = desc
                evento_dict["resultado"] = resultado_final
            else:
                desc = "Próximo partido Málaga CF"
                if info_comp:
                    desc += f" ({info_comp})"
                if not hora_confirmada:
                    desc += " (Hora por confirmar)"
                evento_dict["descripcion"] = desc

            eventos.append(evento_dict)
        except Exception as e:
            print(f"Error procesando partido API Málaga ({active_tab}): {e}")
            continue

    return eventos


def parsear_tarjetas_malaga_html(html):
    """Parsea las tarjetas HTML de malagacf.com/partidos (usado como fallback DOM y en tests)."""
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('article', class_='MkFootballMatchCard')
    eventos = []

    for partido in partidos:
        try:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            raw_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            raw_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            equipo_local = normalizar_nombre_equipo(raw_local, "futbol")
            equipo_visitante = normalizar_nombre_equipo(raw_visitante, "futbol")

            div_time = partido.find('div', class_='MkFootballMatchCard__time')
            div_date = partido.find('div', class_='MkFootballMatchCard__date')
            div_venue = partido.find('div', class_='MkFootballMatchCard__venue')
            span_comp = partido.find('span', class_='MkFootballMatchCard__competition')
            span_gw = partido.find('span', class_='MkFootballMatchCard__matchWeek')

            hora_raw = div_time.text.strip() if div_time else None
            fecha_raw = div_date.text.strip() if div_date else None
            estadio_raw = div_venue.text.strip() if div_venue else None
            comp_str = span_comp.text.strip() if span_comp else ""
            gw_str = span_gw.text.strip() if span_gw else ""
            info_comp = " - ".join(p for p in [comp_str, gw_str] if p)

            name = f"{equipo_local} vs {equipo_visitante}"
            if not fecha_raw:
                continue

            hora_confirmada = True
            if not hora_raw or '--' in hora_raw or ':' not in hora_raw:
                hora_limpia = "03:00"
                hora_confirmada = False
            else:
                hora_limpia = hora_raw.replace('.', '').strip()

            fecha_numerica = traducir_fecha_malaga_a_numeros(fecha_raw)
            if not fecha_numerica:
                print(f"AVISO: No se pudo parsear fecha de {name} (Raw: '{fecha_raw}')")
                continue

            mes_partido_num = int(fecha_numerica.split('.')[1])
            ano_partido = ANO_ACTUAL
            if mes_partido_num < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL + 1
            elif mes_partido_num >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL - 1

            hora_para_strptime = hora_limpia
            es_pm = "PM" in hora_limpia.upper()
            es_am = "AM" in hora_limpia.upper()

            if es_pm or es_am:
                match_hm = re.search(r'(\d{1,2}):(\d{2})', hora_limpia)
                if match_hm:
                    hora = int(match_hm.group(1))
                    minutos = match_hm.group(2)
                    if es_pm and hora != 12:
                        hora += 12
                    if es_am and hora == 12:
                        hora = 0
                    hora_para_strptime = f"{str(hora).zfill(2)}:{minutos}"
            else:
                match_hm = re.search(r'(\d{1,2}):(\d{2})', hora_limpia)
                if match_hm:
                    hora_para_strptime = f"{match_hm.group(1).zfill(2)}:{match_hm.group(2)}"
                else:
                    hora_para_strptime = "03:00"
                    hora_confirmada = False

            fecha_hora_str = f"{fecha_numerica}.{ano_partido} {hora_para_strptime}"
            try:
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
            except ValueError as e:
                print(f"Error parseando fecha Málaga Próximos: {fecha_hora_str} | Error: {e}")
                continue

            fecha_partido_dt_naive = dt.datetime(fecha_hora_naive.year, fecha_hora_naive.month, fecha_hora_naive.day)
            if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                continue

            fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
            fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
            fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
            fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)

            estadio_final = resolver_estadio_futbol(equipo_local, estadio_raw)
            descripcion = "Próximo partido Málaga CF"
            if info_comp:
                descripcion += f" ({info_comp})"
            if not hora_confirmada:
                descripcion += " (Hora por confirmar)"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                "estadio": estadio_final,
                "name": name,
                "descripcion": descripcion,
                "deporte": "futbol",
                "competicion": info_comp,
                "hora_confirmada": hora_confirmada,
            })
        except Exception as e:
            print(f"Error procesando un partido próximo de Málaga: {e}")
            continue
    return eventos


def obtener_proximos_partidos_malaga(driver=None):
    print("Buscando próximos partidos Málaga CF (API oficial + fallback web)...")
    try:
        eventos_api = obtener_partidos_malaga_api(active_tab="fixtures")
        if eventos_api:
            print(f"Procesados {len(eventos_api)} próximos partidos de Málaga CF vía API oficial.")
            return eventos_api
    except Exception as e:
        print(f"AVISO: Fallo en API oficial de próximos partidos Málaga ({e}). Usando fallback Selenium...")

    if not driver:
        return []

    try:
        driver.get("https://www.malagacf.com/partidos")
        clicks_ver_mas = 0
        while clicks_ver_mas < 6:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard"))
                )
                ver_mas_span = WebDriverWait(driver, 2).until(
                    EC.visibility_of_element_located(
                        (By.XPATH, "//span[contains(@class, 'sc-') and (contains(text(), 'Ver más') or contains(text(), 'Load more'))]")
                    )
                )
                load_more_button = ver_mas_span.find_element(By.XPATH, "./ancestor::button")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(random.uniform(2.0, 3.5))
                clicks_ver_mas += 1
            except Exception:
                break
        eventos = parsear_tarjetas_malaga_html(driver.page_source)
        print(f"Procesados {len(eventos)} próximos partidos de Málaga CF vía DOM.")
        return eventos
    except Exception as e:
        print(f"ERROR: No se pudo cargar/encontrar estructura inicial próximos Málaga: {e}")
        return []


# --- FUNCIÓN 2: RESULTADOS MÁLAGA (API OFICIAL + FLASHSCORE BLINDADO) ---
def _extraer_nombre_participante_flashscore(partido_tag, side="home"):
    """
    Extrae de forma limpia el nombre del equipo en Flashscore en orden de prioridad,
    evitando capturar el <title> de los iconos SVG (ej. 'Advancing to next round').
    """
    if side == "home":
        selectores_prioridad = [
            ".event__homeParticipant [data-testid='wcl-simple-text-01']",
            ".event__homeParticipant [data-testid='wcl-scores-simpleText-01']",
            ".event__homeParticipant [class*='wcl-name']",
            ".event__participant--home",
        ]
        contenedor_sel = ".event__homeParticipant"
    else:
        selectores_prioridad = [
            ".event__awayParticipant [data-testid='wcl-simple-text-01']",
            ".event__awayParticipant [data-testid='wcl-scores-simpleText-01']",
            ".event__awayParticipant [class*='wcl-name']",
            ".event__participant--away",
        ]
        contenedor_sel = ".event__awayParticipant"

    for sel in selectores_prioridad:
        nodo = partido_tag.select_one(sel)
        if nodo:
            txt = limpiar_nombre_equipo_raw(nodo.get_text(" ", strip=True))
            if txt:
                return txt

    contenedor = partido_tag.select_one(contenedor_sel)
    if contenedor:
        img = contenedor.find("img", alt=True)
        if img and img.get("alt", "").strip():
            return limpiar_nombre_equipo_raw(img["alt"])
        # Eliminar SVGs antes de extraer texto del contenedor padre
        clon = BeautifulSoup(str(contenedor), 'html.parser')
        for svg in clon.find_all("svg"):
            svg.decompose()
        txt = limpiar_nombre_equipo_raw(clon.get_text(" ", strip=True))
        if txt:
            return txt

    return None


def parsear_resultados_flashscore_html(html):
    """Parsea el HTML de resultados de Flashscore filtrando amistosos y normalizando equipos."""
    soup = BeautifulSoup(html, 'html.parser')
    partidos_flashscore = soup.select("div.event__match")
    competiciones_excluidas = ["club friendly", "amistosos de clubs", "world", "friendly"]
    eventos = []

    for partido in partidos_flashscore:
        try:
            # En Flashscore el encabezado de competición es un hermano anterior (sibling) de div.event__match
            comp_header = partido.find_previous_sibling(
                class_=re.compile(r"headerLeague__wrapper|event__header")
            )
            competition_tag = comp_header or partido.select_one("span.event__title--type, .event__titleBox")
            if competition_tag:
                competition_name = competition_tag.get_text(" ", strip=True).lower()
                if any(excluded in competition_name for excluded in competiciones_excluidas):
                    continue

            raw_local = _extraer_nombre_participante_flashscore(partido, "home")
            raw_visitante = _extraer_nombre_participante_flashscore(partido, "away")
            if not raw_local or not raw_visitante:
                continue

            equipo_local = normalizar_nombre_equipo(raw_local, "futbol")
            equipo_visitante = normalizar_nombre_equipo(raw_visitante, "futbol")
            name = f"{equipo_local} vs {equipo_visitante}"

            home_score_tag = partido.select_one(".event__score--home")
            away_score_tag = partido.select_one(".event__score--away")
            if not home_score_tag or not away_score_tag:
                continue

            sh_match = re.search(r'\d+', home_score_tag.get_text(strip=True))
            sa_match = re.search(r'\d+', away_score_tag.get_text(strip=True))
            if not sh_match or not sa_match:
                continue
            resultado_final = f"{sh_match.group(0)} - {sa_match.group(0)}"

            datetime_tag = partido.select_one(
                "[data-testid='wcl-stageTime'], .event__stageTime, .event__time"
            )
            if not datetime_tag:
                continue

            datetime_text = datetime_tag.get_text(" ", strip=True)
            match_fecha = re.search(r'(\d{2})\.(\d{2})\.(?:(\d{4}))?', datetime_text)
            if not match_fecha:
                continue

            dia_str = match_fecha.group(1)
            mes_num_str = match_fecha.group(2)
            mes_num = int(mes_num_str)
            ano_explicito = match_fecha.group(3)

            match_hora = re.search(r'(\d{2}:\d{2})', datetime_text)
            hora_limpia = match_hora.group(1) if match_hora else "12:00"

            if ano_explicito:
                ano_partido = int(ano_explicito)
            else:
                ano_partido = ANO_ACTUAL
                if MES_ACTUAL < MES_INICIO_TEMPORADA and mes_num >= MES_INICIO_TEMPORADA:
                    ano_partido = ANO_ACTUAL - 1
                elif MES_ACTUAL >= MES_INICIO_TEMPORADA and mes_num > MES_ACTUAL:
                    ano_partido = ANO_ACTUAL - 1

            fecha_partido_dt_naive = dt.datetime(ano_partido, mes_num, int(dia_str))
            if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                continue

            fecha_str_procesada = f"{dia_str}.{mes_num_str}.{ano_partido} {hora_limpia}"
            fecha_hora_naive = dt.datetime.strptime(fecha_str_procesada, '%d.%m.%Y %H:%M')

            fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
            fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
            fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
            fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)

            estadio_final = resolver_estadio_futbol(equipo_local)
            descripcion = f"Resultado Málaga CF: {resultado_final}"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                "estadio": estadio_final,
                "name": name,
                "descripcion": descripcion,
                "resultado": resultado_final,
                "deporte": "futbol",
                "hora_confirmada": bool(match_hora),
            })
        except Exception as e:
            print(f"Error procesando un resultado de Flashscore: {e}")
            continue

    return eventos


def obtener_resultados_malaga_flashscore(driver=None):
    print("Buscando resultados Málaga CF (API oficial + Flashscore)...")
    eventos_combinados = []

    # 1. Fuente primaria: API oficial malagacf.com (tiene hora exacta, estadio oficial y nombres idénticos)
    try:
        eventos_oficiales = obtener_partidos_malaga_api(active_tab="results")
        if eventos_oficiales:
            print(f"Obtenidos {len(eventos_oficiales)} resultados oficiales de Málaga CF vía API.")
            eventos_combinados.extend(eventos_oficiales)
    except Exception as e:
        print(f"AVISO: No se pudieron obtener resultados vía API Málaga ({e}).")

    # 2. Fuente secundaria / enriquecimiento en tiempo real: Flashscore
    if not driver:
        return eventos_combinados

    url_flashscore = "https://www.flashscore.com/team/malaga/25tIqYiJ/results/"
    try:
        driver.get(url_flashscore)
        print(f"Página {driver.current_url} cargada.")
        try:
            cookie_button_id = "onetrust-accept-btn-handler"
            xpath_accept_text = "//button[contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'acepto') or contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'accept')]"
            try:
                cookie_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            except Exception:
                cookie_button = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath_accept_text)))
            driver.execute_script("arguments[0].click();", cookie_button)
            time.sleep(random.uniform(0.8, 1.5))
        except Exception:
            pass

        clicks_ver_mas = 0
        while clicks_ver_mas < 4:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.event__match")))
                load_more_button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.event__more, [data-testid='wcl-buttonLink']"))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.4)
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(random.uniform(1.5, 2.5))
                clicks_ver_mas += 1
            except Exception:
                break

        eventos_fs = parsear_resultados_flashscore_html(driver.page_source)
        print(f"Procesados {len(eventos_fs)} resultados de Málaga CF en Flashscore.")

        # Añadir solo los de Flashscore que no estén ya cubiertos por la API oficial (misma pareja de equipos)
        nombres_oficiales = {ev["name"] for ev in eventos_combinados}
        for ev_fs in eventos_fs:
            if ev_fs["name"] not in nombres_oficiales:
                eventos_combinados.append(ev_fs)

    except Exception as e:
        print(f"ERROR: No se pudo cargar/encontrar estructura inicial Flashscore: {e}")

    return eventos_combinados


# --- FUNCIÓN 3 Y 4: UNICAJA BALONCESTO (UNIFICADO + FICHAS OFICIALES DE PABELLÓN) ---
_CACHE_DATOS_UNICAJA = None


def _extraer_nombre_contenedor_unicaja(contenedor):
    """
    Extrae el nombre del equipo de un div.contenedor_logo_equipo en unicajabaloncesto.com.
    Prioridad:
    1) div.nombre_equipo
    2) img[alt]
    3) a[title]
    4) Si enlaza a /equipo/ver/3-unicaja.html -> 'Unicaja'
    """
    if not contenedor:
        return "Unicaja"

    nombre_div = contenedor.find('div', class_='nombre_equipo')
    if nombre_div and nombre_div.text and nombre_div.text.strip():
        return normalizar_nombre_equipo(nombre_div.text.strip(), "basket")

    img_tag = contenedor.find('img')
    if img_tag and img_tag.get('alt') and img_tag.get('alt').strip():
        return normalizar_nombre_equipo(img_tag.get('alt').strip(), "basket")

    a_tag = contenedor.find('a')
    if a_tag:
        if a_tag.get('title') and a_tag.get('title').strip():
            return normalizar_nombre_equipo(a_tag.get('title').strip(), "basket")
        href = a_tag.get('href', '')
        if 'unicaja' in href.lower():
            return "Unicaja"

    return "Unicaja"


def _obtener_metadatos_ics_y_pabellones_unicaja(session=None):
    """
    Descarga el feed oficial /calendario/ics y las fichas /partido/ver/id/<id> en paralelo
    para conocer el pabellón oficial exacto, competición y fecha provisional de cada partido.
    """
    s = session or requests.Session()
    info_por_equipos = {}
    info_por_id = {}

    try:
        resp_ics = s.get("https://www.unicajabaloncesto.com/calendario/ics", headers=DEFAULT_HEADERS, timeout=10)
        if resp_ics.status_code != 200:
            return info_por_equipos, info_por_id

        cal = Calendar.from_ical(resp_ics.content)
        tareas = []
        for comp in cal.walk():
            if comp.name != "VEVENT":
                continue
            uid = str(comp.get("uid", ""))
            match_id = uid.split("-")[-1] if "-" in uid else ""
            summary = str(comp.get("summary", ""))
            desc = str(comp.get("description", ""))
            dtstart_prop = comp.get("dtstart")
            dtstart_val = dtstart_prop.dt if dtstart_prop else None
            partes = [p.strip() for p in summary.split(" - ")]
            if len(partes) == 2:
                eq_local = normalizar_nombre_equipo(partes[0], "basket")
                eq_visit = normalizar_nombre_equipo(partes[1], "basket")
                clave = f"{eq_local} vs {eq_visit}"
            else:
                clave = summary
            tareas.append((match_id, clave, desc, dtstart_val))

        def _fetch_ficha(item):
            mid, clave, desc, dt_val = item
            pabellon_oficial = None
            if mid and mid.isdigit():
                try:
                    r_ficha = s.get(
                        f"https://www.unicajabaloncesto.com/partido/ver/id/{mid}",
                        headers=DEFAULT_HEADERS,
                        timeout=8
                    )
                    if r_ficha.status_code == 200:
                        soup_f = BeautifulSoup(r_ficha.text, 'html.parser')
                        pab_div = soup_f.find('div', class_='pabellon')
                        if pab_div and pab_div.text.strip():
                            pabellon_oficial = pab_div.text.strip()
                except Exception:
                    pass
            return mid, clave, desc, dt_val, pabellon_oficial

        with ThreadPoolExecutor(max_workers=8) as executor:
            for mid, clave, desc, dt_val, pab in executor.map(_fetch_ficha, tareas):
                datos = {
                    "match_id": mid,
                    "competicion": desc,
                    "dtstart": dt_val,
                    "pabellon": pab,
                }
                info_por_equipos[clave] = datos
                if mid:
                    info_por_id[mid] = datos
    except Exception as e:
        print(f"AVISO: No se pudo enriquecer con ICS/fichas de Unicaja: {e}")

    return info_por_equipos, info_por_id


def parsear_calendario_unicaja_html(html, info_por_equipos=None, info_por_id=None):
    """
    Parsea el HTML de unicajabaloncesto.com/calendario devolviendo (proximos, resultados)
    en una sola pasada.
    """
    info_por_equipos = info_por_equipos or {}
    info_por_id = info_por_id or {}
    proximos = []
    resultados = []

    soup = BeautifulSoup(html, 'html.parser')
    secciones_mes = soup.find_all('section', class_='contenedora_calendario')
    meses_es_a_num = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }

    filas_partido_con_mes = []
    for seccion in secciones_mes:
        h1_tag = seccion.find('h1', class_='titulo_principal')
        mes_actual_str = h1_tag.text.strip().lower() if h1_tag and h1_tag.text else None
        if not mes_actual_str or mes_actual_str not in meses_es_a_num:
            continue
        mes_num = meses_es_a_num.get(mes_actual_str)
        filas = seccion.find_all('div', class_='fila_interior')
        for fila in filas:
            filas_partido_con_mes.append((mes_num, fila))

    for mes_num, fila in filas_partido_con_mes:
        try:
            marcador_div = fila.find('div', class_='marcador')
            es_resultado = False
            resultado_final = "N/A"
            match_id_fila = None

            if marcador_div:
                resultado_link = marcador_div.find('a')
                if resultado_link:
                    href = resultado_link.get('href', '')
                    m_id = re.search(r'/id/(\d+)', href)
                    if m_id:
                        match_id_fila = m_id.group(1)
                    if '|' in resultado_link.text:
                        es_resultado = True
                        partes = resultado_link.text.split('|')
                        resultado_final = f"{partes[0].strip()} - {partes[1].strip()}"

            contenedores_equipo = fila.find_all('div', class_='contenedor_logo_equipo')
            if len(contenedores_equipo) < 2:
                continue

            equipo_local = _extraer_nombre_contenedor_unicaja(contenedores_equipo[0])
            equipo_visitante = _extraer_nombre_contenedor_unicaja(contenedores_equipo[1])
            name = f"{equipo_local} vs {equipo_visitante}"

            meta = (
                (info_por_id.get(match_id_fila) if match_id_fila else None)
                or info_por_equipos.get(name)
                or {}
            )

            # Competición y jornada
            jornada_span = fila.find('span', class_='jornada')
            jornada_txt = jornada_span.text.strip() if jornada_span else ""
            comp_img = fila.select_one('.contenedor_logo_competicion img')
            comp_src = comp_img.get('src', '') if comp_img else ''
            comp_nombre = meta.get("competicion") or ""
            if not comp_nombre:
                if "logo-7" in comp_src:
                    comp_nombre = f"Liga Endesa ({jornada_txt})" if jornada_txt else "Liga Endesa"
                elif "logo-9" in comp_src:
                    comp_nombre = f"Basketball Champions League ({jornada_txt})" if jornada_txt else "Basketball Champions League"
                elif jornada_txt:
                    comp_nombre = jornada_txt

            fecha_div = fila.find('div', class_='celda prioridad-1 fecha')
            if not fecha_div:
                continue
            fecha_textos = [t.strip() for t in fecha_div.find_all(string=True) if t.strip()]
            if not fecha_textos:
                continue

            ano_partido = ANO_ACTUAL
            mes_num_int = int(mes_num)
            if mes_num_int < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL + 1
            elif mes_num_int >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL - 1

            # Extraer día del mes (soportando 'Domingo 27' o 'POR CONFIRMAR')
            match_dia = re.search(r'\b(\d{1,2})\b', fecha_textos[0])
            hora_confirmada = False
            hora_limpia = "12:00" if es_resultado else "03:00"

            if match_dia:
                dia_str = match_dia.group(1).zfill(2)
                hora_raw = fecha_textos[1] if len(fecha_textos) > 1 else None
                if hora_raw and ':' in hora_raw and 'falta' not in hora_raw.lower():
                    m_hora = re.search(r'(\d{1,2}:\d{2})', hora_raw)
                    if m_hora:
                        partes_h = m_hora.group(1).split(':')
                        hora_limpia = f"{partes_h[0].zfill(2)}:{partes_h[1]}"
                        hora_confirmada = True
            elif meta.get("dtstart"):
                # Caso 'POR CONFIRMAR' (ej. Jornada 34): rescatamos la fecha provisional del ICS oficial
                dt_ics = meta["dtstart"]
                dia_str = f"{dt_ics.day:02d}"
                mes_num = f"{dt_ics.month:02d}"
                mes_num_int = dt_ics.month
                ano_partido = dt_ics.year
                hora_limpia = "03:00"
                hora_confirmada = False
            else:
                continue

            try:
                fecha_partido_dt = dt.datetime(ano_partido, mes_num_int, int(dia_str))
                if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                    continue
                fecha_hora_str = f"{dia_str}.{mes_num}.{ano_partido} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')

                fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)
            except ValueError:
                continue

            lugar_span = fila.find('span', class_='pabellon') or fila.find('div', class_='pabellon')
            pabellon_candidato = (
                (lugar_span.text.strip() if lugar_span and lugar_span.text else None)
                or meta.get("pabellon")
            )
            lugar = resolver_pabellon_basket(equipo_local, pabellon_candidato)

            if es_resultado:
                descripcion = f"Resultado Unicaja: {resultado_final}"
                if comp_nombre:
                    descripcion += f" | {comp_nombre}"
                resultados.append({
                    "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                    "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                    "estadio": lugar,
                    "name": name,
                    "descripcion": descripcion,
                    "resultado": resultado_final,
                    "deporte": "basket",
                    "competicion": comp_nombre,
                    "hora_confirmada": True,
                })
            else:
                descripcion = "Próximo partido Unicaja"
                if comp_nombre:
                    descripcion += f" ({comp_nombre})"
                if not hora_confirmada:
                    descripcion += " (Hora por confirmar)"
                proximos.append({
                    "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                    "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                    "estadio": lugar,
                    "name": name,
                    "descripcion": descripcion,
                    "deporte": "basket",
                    "competicion": comp_nombre,
                    "hora_confirmada": hora_confirmada,
                })
        except Exception as e:
            print(f"Error procesando una fila de Unicaja: {e}")
            continue

    return proximos, resultados


def _obtener_datos_unicaja_unificados(driver=None, force_refresh=False):
    global _CACHE_DATOS_UNICAJA
    if _CACHE_DATOS_UNICAJA is not None and not force_refresh:
        return _CACHE_DATOS_UNICAJA

    session = requests.Session()
    info_equipos, info_id = _obtener_metadatos_ics_y_pabellones_unicaja(session)

    html = None
    try:
        resp = session.get("https://www.unicajabaloncesto.com/calendario", headers=DEFAULT_HEADERS, timeout=10)
        if resp.status_code == 200 and "fila_interior" in resp.text:
            html = resp.text
    except Exception:
        pass

    if not html and driver:
        try:
            driver.get("https://www.unicajabaloncesto.com/calendario")
            try:
                cookie_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "aceptocookies")))
                driver.execute_script("arguments[0].click();", cookie_button)
                time.sleep(1.0)
            except Exception:
                pass
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.fila.fila_interior")))
            html = driver.page_source
        except Exception as e:
            print(f"ERROR al cargar página Unicaja con driver: {e}")

    if not html:
        return [], []

    _CACHE_DATOS_UNICAJA = parsear_calendario_unicaja_html(html, info_equipos, info_id)
    return _CACHE_DATOS_UNICAJA


def obtener_proximos_partidos_unicaja(driver=None):
    print("Buscando próximos partidos Unicaja...")
    proximos, _ = _obtener_datos_unicaja_unificados(driver)
    print(f"Procesados {len(proximos)} próximos partidos de Unicaja.")
    return proximos


def obtener_resultados_unicaja(driver=None):
    print("Buscando resultados Unicaja...")
    _, resultados = _obtener_datos_unicaja_unificados(driver)
    print(f"Procesados {len(resultados)} resultados de Unicaja.")
    return resultados


# --- FUNCIÓN 4B: CLUB DEPORTIVO HEREDIA 21 FS (RFAF SENIOR FEMENINO F.S.) ---
def _descargar_html_rfaf(url, session, marcadores_esperados=None, reintentos=3):
    """
    Descarga una página de rfaf.es gestionando la cookie JSESSIONID inicial (que redirige
    a /pnfg/NLogin en la primera petición sin sesión) y la codificación ISO-8859-15.
    """
    marcadores = marcadores_esperados or ["NFG_", "<table"]
    for intento in range(reintentos):
        try:
            resp = session.get(url, headers=DEFAULT_HEADERS, timeout=12)
            if resp.status_code == 200:
                html = resp.content.decode("iso-8859-15", errors="replace")
                if any(m in html for m in marcadores) and "NLogin" not in resp.url:
                    return html
            time.sleep(0.6 * (intento + 1))
        except Exception:
            time.sleep(0.6 * (intento + 1))
    return None


def parsear_campos_rfaf_html(html):
    """
    Extrae el campo designado (y fecha/hora si figura) de cada partido desde el HTML de RFAF,
    soportando tanto la vista de jornada (`NFG_CmpJornada`) como el calendario extendido
    (`NFG_VisCalendario_Vis` con `CDetalle=1`).
    Devuelve un diccionario indexado por `(equipo_local_norm, equipo_visitante_norm)` y
    `(fecha_dd_mm_yyyy, equipo_local_norm, equipo_visitante_norm)`.
    """
    campos_map = {}
    if not html:
        return campos_map

    soup = BeautifulSoup(html, "html.parser")

    def _registrar(raw_loc, raw_vis, campo_raw, fecha_hora_texto=""):
        campo_limpio = limpiar_campo_rfaf(campo_raw)
        if not campo_limpio:
            return
        loc_norm = normalizar_nombre_equipo(raw_loc, "futsal")
        vis_norm = normalizar_nombre_equipo(raw_vis, "futsal")
        if not loc_norm or not vis_norm or loc_norm == "Desconocido" or vis_norm == "Desconocido":
            return

        m_f = re.search(r"(\d{2}-\d{2}-\d{4})", fecha_hora_texto or "")
        m_h = re.search(r"(\d{1,2}:\d{2})", fecha_hora_texto or "")
        fecha_str = m_f.group(1) if m_f else None
        hora_str = m_h.group(1) if m_h else None

        info = {"campo": campo_limpio, "fecha": fecha_str, "hora": hora_str}
        campos_map[(loc_norm, vis_norm)] = info
        if fecha_str:
            campos_map[(fecha_str, loc_norm, vis_norm)] = info

    # 1. Formato NFG_VisCalendario_Vis (CDetalle=1): filas div.row con col-sm-7 (tabla equipos) y col-sm-5 (fa-map-marker)
    for row in soup.find_all("div", class_="row"):
        if row.find("div", class_="row"):
            continue
        col_info = row.find("div", class_=lambda c: c and "col-sm-5" in c)
        tabla_eq = row.find("table")
        if not col_info or not tabla_eq:
            continue
        tds = tabla_eq.find_all("td")
        if len(tds) < 3:
            continue
        raw_local = " ".join(tds[0].get_text(" ", strip=True).split())
        raw_visitante = " ".join(tds[2].get_text(" ", strip=True).split())

        partes_campo = []
        partes_fecha = []
        for frag in col_info.stripped_strings:
            texto_frag = " ".join(frag.replace("\xa0", " ").split())
            if not texto_frag:
                continue
            if re.search(r"\d{2}-\d{2}-\d{4}", texto_frag):
                partes_fecha.append(texto_frag)
            else:
                partes_campo.append(texto_frag)

        if partes_campo:
            _registrar(raw_local, raw_visitante, " ".join(partes_campo), " ".join(partes_fecha))

    # 2. Formato NFG_CmpJornada: tablas de partido con enlaces NFG_VisEquipos y NFG_VisCampos
    for table in soup.find_all("table"):
        if table.find("table"):
            continue
        a_campo = table.find("a", href=re.compile(r"NFG_VisCampos"))
        if not a_campo:
            continue
        enlaces_eq = table.find_all("a", href=re.compile(r"NFG_VisEquipos"))
        if len(enlaces_eq) >= 2:
            raw_local = " ".join(enlaces_eq[0].get_text(" ", strip=True).split())
            raw_visitante = " ".join(enlaces_eq[1].get_text(" ", strip=True).split())
        else:
            div_l = table.find("div", class_="font_widgetL")
            div_v = table.find("div", class_="font_widgetV")
            if not div_l or not div_v:
                continue
            raw_local = " ".join(div_l.get_text(" ", strip=True).split())
            raw_visitante = " ".join(div_v.get_text(" ", strip=True).split())

        campo_raw = " ".join(a_campo.get_text(" ", strip=True).split())
        horarios = [" ".join(sp.get_text(" ", strip=True).split()) for sp in table.find_all("span", class_="horario")]
        _registrar(raw_local, raw_visitante, campo_raw, " ".join(horarios))

    return campos_map


def _extraer_campo_de_mapa(campos_rfaf, claves):
    """Busca en `campos_rfaf` por orden de prioridad de claves y devuelve (campo_str, hora_str)."""
    if not campos_rfaf:
        return None, None
    for k in claves:
        if k in campos_rfaf:
            val = campos_rfaf[k]
            if isinstance(val, dict):
                return val.get("campo"), val.get("hora")
            if isinstance(val, str):
                return val, None
    return None, None


def parsear_partidos_heredia21_html(
    html,
    nombre_competicion="2ª Andaluza Femenina Sénior F.S.",
    campos_rfaf=None,
):
    """
    Parsea la tabla de partidos de RFAF (NFG_VisCompeticiones_Grupo) para el
    Club Deportivo Heredia 21 FS, cruzando opcionalmente con el mapa de campos
    designados en cada jornada (`NFG_CmpJornada` / `NFG_VisCalendario_Vis`)
    y devolviendo `(proximos, resultados)`.
    """
    proximos = []
    resultados = []
    if not html:
        return proximos, resultados

    mapa_campos = dict(campos_rfaf) if campos_rfaf else {}
    campos_inline_html = parsear_campos_rfaf_html(html)
    for k, v in campos_inline_html.items():
        mapa_campos.setdefault(k, v)

    soup = BeautifulSoup(html, "html.parser")
    filas = soup.find_all("tr")

    for fila in filas:
        try:
            tds = fila.find_all("td", recursive=False)
            if len(tds) != 3:
                continue

            h5_equipos_fecha = tds[1].find_all("h5")
            if len(h5_equipos_fecha) < 3:
                continue

            jornada_raw = " ".join(tds[0].get_text(" ", strip=True).split())
            raw_local = " ".join(h5_equipos_fecha[0].get_text(" ", strip=True).split())
            raw_visitante = " ".join(h5_equipos_fecha[1].get_text(" ", strip=True).split())
            fecha_hora_raw = " ".join(h5_equipos_fecha[2].get_text(" ", strip=True).split())

            match_fecha = re.search(r'(\d{2})-(\d{2})-(\d{4})', fecha_hora_raw)
            if not match_fecha:
                continue

            fecha_str = match_fecha.group(0)
            dia_int = int(match_fecha.group(1))
            mes_int = int(match_fecha.group(2))
            ano_int = int(match_fecha.group(3))

            fecha_partido_dt = dt.datetime(ano_int, mes_int, dia_int)
            if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                continue

            equipo_local = normalizar_nombre_equipo(raw_local, "futsal")
            equipo_visitante = normalizar_nombre_equipo(raw_visitante, "futsal")
            name = f"{equipo_local} vs {equipo_visitante}"

            etiqueta_jornada = f"J{jornada_raw}" if jornada_raw.isdigit() else jornada_raw

            # Detectar campo designado en la propia fila (si existe) o en el mapa de NFG_CmpJornada / NFG_VisCalendario_Vis
            campo_designado = None
            a_campo_fila = fila.find("a", href=re.compile(r"NFG_VisCampos"))
            if a_campo_fila:
                campo_designado = " ".join(a_campo_fila.get_text(" ", strip=True).split())
            elif len(h5_equipos_fecha) >= 4:
                campo_designado = " ".join(h5_equipos_fecha[3].get_text(" ", strip=True).split())

            campo_mapa, hora_mapa = _extraer_campo_de_mapa(
                mapa_campos,
                [
                    (jornada_raw, equipo_local, equipo_visitante),
                    (etiqueta_jornada, equipo_local, equipo_visitante),
                    (fecha_str, equipo_local, equipo_visitante),
                    (equipo_local, equipo_visitante),
                ],
            )
            if not campo_designado and campo_mapa:
                campo_designado = campo_mapa

            match_hora = re.search(r'(\d{1,2}):(\d{2})', fecha_hora_raw)
            if not match_hora and hora_mapa:
                match_hora = re.search(r'(\d{1,2}):(\d{2})', hora_mapa)

            if match_hora:
                hora_int = int(match_hora.group(1))
                min_int = int(match_hora.group(2))
                hora_confirmada = True
            else:
                hora_int = 3
                min_int = 0
                hora_confirmada = False

            fecha_hora_inicio_local = dt.datetime(
                ano_int, mes_int, dia_int, hora_int, min_int, tzinfo=TZ_MADRID
            )
            fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
            fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
            fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)

            estadio_final = resolver_pabellon_futsal(equipo_local, campo_designado)

            info_comp = " - ".join(p for p in [nombre_competicion, etiqueta_jornada] if p)

            texto_marcador = " ".join(tds[2].get_text(" ", strip=True).split())
            match_marcador = re.search(r'(\d+)\s*-\s*(\d+)', texto_marcador)

            if match_marcador:
                resultado_final = f"{match_marcador.group(1)} - {match_marcador.group(2)}"
                descripcion = f"Resultado Heredia 21 FS: {resultado_final}"
                if info_comp:
                    descripcion += f" | {info_comp}"
                resultados.append({
                    "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                    "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                    "estadio": estadio_final,
                    "name": name,
                    "descripcion": descripcion,
                    "resultado": resultado_final,
                    "deporte": "futsal",
                    "competicion": info_comp,
                    "hora_confirmada": True,
                })
            else:
                descripcion = "Próximo partido Heredia 21 FS"
                if info_comp:
                    descripcion += f" ({info_comp})"
                if not hora_confirmada:
                    descripcion += " (Hora por confirmar)"
                proximos.append({
                    "fecha_hora_inicio": fecha_hora_inicio_utc.isoformat(),
                    "fecha_hora_fin": fecha_hora_fin_utc.isoformat(),
                    "estadio": estadio_final,
                    "name": name,
                    "descripcion": descripcion,
                    "deporte": "futsal",
                    "competicion": info_comp,
                    "hora_confirmada": hora_confirmada,
                })
        except Exception as e:
            print(f"Error procesando fila de Heredia 21 FS en RFAF: {e}")
            continue

    return proximos, resultados


def obtener_campos_designados_rfaf(
    session,
    codgrupo,
    codcompeticion=RFAF_CODCOMPETICION_HEREDIA21_DEFAULT,
    codtemporada=RFAF_CODTEMPORADA_HEREDIA21_DEFAULT,
    html_grupo=None,
):
    """
    Obtiene el mapa de campos designados en cada jornada de la RFAF para un grupo/competición.
    1) Consulta `NFG_VisCalendario_Vis` con `CDetalle=1` (que devuelve todas las jornadas con su campo en una sola petición).
    2) Si alguna jornada con horario confirmado aún no tiene campo en el mapa (o si `NFG_VisCalendario_Vis` no devolvió datos),
       consulta `NFG_CmpJornada` para esa jornada específica.
    """
    campos_rfaf = {}
    if not codcompeticion:
        return campos_rfaf

    url_calendario_det = (
        f"https://www.rfaf.es/pnfg/NPcd/NFG_VisCalendario_Vis"
        f"?cod_primaria=1000120&codtemporada={codtemporada}"
        f"&codcompeticion={codcompeticion}&codgrupo={codgrupo}&CDetalle=1"
    )
    html_cal = _descargar_html_rfaf(
        url_calendario_det,
        session,
        marcadores_esperados=["fa-map-marker", "HEREDIA", "NFG_"],
    )
    if html_cal:
        campos_rfaf.update(parsear_campos_rfaf_html(html_cal))

    # Verificar si alguna jornada con horario confirmado en html_grupo necesita consulta puntual a NFG_CmpJornada
    jornadas_pendientes = []
    if html_grupo:
        soup_g = BeautifulSoup(html_grupo, "html.parser")
        for fila in soup_g.find_all("tr"):
            tds = fila.find_all("td", recursive=False)
            if len(tds) != 3:
                continue
            h5s = tds[1].find_all("h5")
            if len(h5s) < 3:
                continue
            j_raw = " ".join(tds[0].get_text(" ", strip=True).split())
            if not j_raw.isdigit():
                continue
            loc = normalizar_nombre_equipo(" ".join(h5s[0].get_text(" ", strip=True).split()), "futsal")
            vis = normalizar_nombre_equipo(" ".join(h5s[1].get_text(" ", strip=True).split()), "futsal")
            fh_raw = " ".join(h5s[2].get_text(" ", strip=True).split())
            tiene_hora = bool(re.search(r"\d{1,2}:\d{2}", fh_raw))
            if (loc, vis) not in campos_rfaf and (tiene_hora or not campos_rfaf):
                if j_raw not in jornadas_pendientes:
                    jornadas_pendientes.append(j_raw)

    for j_num in jornadas_pendientes[:6]:
        url_jornada = (
            f"https://www.rfaf.es/pnfg/NPcd/NFG_CmpJornada"
            f"?cod_primaria=1000120&CodCompeticion={codcompeticion}"
            f"&CodGrupo={codgrupo}&CodTemporada={codtemporada}&CodJornada={j_num}"
        )
        html_jor = _descargar_html_rfaf(
            url_jornada,
            session,
            marcadores_esperados=["NFG_VisCampos", "HEREDIA", "NFG_"],
        )
        if html_jor:
            campos_rfaf.update(parsear_campos_rfaf_html(html_jor))
        time.sleep(0.25)

    return campos_rfaf


def obtener_partidos_heredia21_rfaf(driver=None, session=None):
    """
    Obtiene todos los partidos (próximos y resultados) de la temporada actual del
    Club Deportivo Heredia 21 FS desde la web oficial de la RFAF, incluyendo el
    campo designado en cada jornada (`NFG_VisCalendario_Vis` / `NFG_CmpJornada`).
    """
    print("Buscando partidos de Heredia 21 Femenino FS en RFAF...")
    s = session or requests.Session()

    # 1. Calentar sesión con la ficha del equipo para obtener cookie JSESSIONID de /pnfg
    _descargar_html_rfaf(RFAF_URL_EQUIPO_HEREDIA21, s, marcadores_esperados=["HEREDIA 21", "NFG_"])

    # 2. Descubrir grupos de competición activos del equipo (con fallback seguro al grupo 48466076)
    grupos_a_consultar = []
    url_comp_equipo = (
        f"https://www.rfaf.es/pnfg/NPcd/NFG_VisCompeticiones_Equipo"
        f"?cod_primaria=1000123&codequipo={RFAF_CODIGO_EQUIPO_HEREDIA21}"
    )
    html_comp = _descargar_html_rfaf(url_comp_equipo, s, marcadores_esperados=["NFG_VisCompeticiones_Grupo"])
    if html_comp:
        soup_comp = BeautifulSoup(html_comp, "html.parser")
        for tr in soup_comp.find_all("tr"):
            if tr.find("tr"):
                continue
            a_grp = tr.find("a", href=re.compile(r"NFG_VisCompeticiones_Grupo.*codgrupo=\d+"))
            if not a_grp:
                continue
            m_grp = re.search(r"codgrupo=(\d+)", a_grp.get("href", ""))
            if not m_grp:
                continue
            codgrupo = m_grp.group(1)
            # Evitar consultar el grupo de la liga 2025/26 anterior (46676649)
            if codgrupo == "46676649":
                continue

            codcompeticion = (
                RFAF_CODCOMPETICION_HEREDIA21_DEFAULT
                if codgrupo == RFAF_CODGRUPO_HEREDIA21_DEFAULT
                else None
            )
            a_comp = tr.find("a", href=re.compile(r"codcompeticion=\d+", re.IGNORECASE))
            if a_comp:
                m_comp = re.search(r"codcompeticion=(\d+)", a_comp.get("href", ""), flags=re.IGNORECASE)
                if m_comp:
                    codcompeticion = m_comp.group(1)

            tds_tr = tr.find_all("td")
            nombre_comp = " ".join(tds_tr[0].get_text(" ", strip=True).split()) if tds_tr else "2ª Andaluza Femenina Sénior F.S."
            item_grupo = (codgrupo, codcompeticion, nombre_comp)
            if not any(g[0] == codgrupo for g in grupos_a_consultar):
                grupos_a_consultar.append(item_grupo)

    if not grupos_a_consultar:
        grupos_a_consultar = [
            (
                RFAF_CODGRUPO_HEREDIA21_DEFAULT,
                RFAF_CODCOMPETICION_HEREDIA21_DEFAULT,
                "2ª Andaluza Femenina Sénior F.S. (Málaga)",
            )
        ]

    todos_eventos = []
    for codgrupo, codcompeticion, nombre_comp in grupos_a_consultar:
        url_grupo = (
            f"https://www.rfaf.es/pnfg/NPcd/NFG_VisCompeticiones_Grupo"
            f"?cod_primaria=1000123&codequipo={RFAF_CODIGO_EQUIPO_HEREDIA21}&codgrupo={codgrupo}"
        )
        html_grupo = _descargar_html_rfaf(url_grupo, s, marcadores_esperados=["HEREDIA 21"])
        if not html_grupo and driver:
            try:
                driver.get(RFAF_URL_EQUIPO_HEREDIA21)
                time.sleep(0.8)
                driver.get(url_grupo)
                time.sleep(1.0)
                html_grupo = driver.page_source
            except Exception as e:
                print(f"AVISO: Fallback Selenium RFAF falló para grupo {codgrupo}: {e}")

        if html_grupo:
            campos_rfaf = obtener_campos_designados_rfaf(
                s,
                codgrupo=codgrupo,
                codcompeticion=codcompeticion,
                html_grupo=html_grupo,
            )
            prox, res = parsear_partidos_heredia21_html(
                html_grupo,
                nombre_comp,
                campos_rfaf=campos_rfaf,
            )
            todos_eventos.extend(prox)
            todos_eventos.extend(res)
        time.sleep(0.3)

    print(f"Procesados {len(todos_eventos)} partidos de Heredia 21 FS en RFAF.")
    return todos_eventos


# --- FUNCIÓN 5: GENERAR ICS CON RECONCILIACIÓN INTELIGENTE Y ANTI-BORRADO ---
def _detectar_deporte_texto(summary="", description="", location="", deporte_explicito=None):
    """Determina el deporte ('futbol', 'basket' o 'futsal') a partir de los metadatos del evento."""
    if deporte_explicito in ("futbol", "basket", "futsal"):
        return deporte_explicito
    texto = f"{summary} {description} {location}".lower()
    if (
        "heredia 21" in texto
        or "f.s." in texto
        or "futsal" in texto
        or "fútbol sala" in texto
        or "futbol sala" in texto
        or "carranque" in texto
        or "rubén ruzafa" in texto
        or "ruben ruzafa" in texto
    ):
        return "futsal"
    if (
        "unicaja" in texto
        or "carpena" in texto
        or "liga endesa" in texto
        or "champions league" in texto
    ):
        return "basket"
    return "futbol"


def _extraer_info_uid_o_summary(component):
    """
    Extrae (fecha_dt, par_equipos_normalizado, deporte, es_corrupto) de un VEVENT existente
    para poder detectar duplicados cuando un partido cambia de fecha o se normaliza el nombre.
    """
    uid = str(component.get("uid", ""))
    summary = str(component.get("summary", ""))
    location = str(component.get("location", ""))
    description = str(component.get("description", ""))

    # Detectar eventos antiguos corruptos por SVGs de Flashscore o países (Esp)
    es_corrupto = False
    if "Advancing to next round" in summary or "Advancingtonextround" in uid:
        es_corrupto = True
    if re.search(r'\([A-Za-z]{2,3}\)', summary):
        es_corrupto = True

    deporte = _detectar_deporte_texto(summary, description, location)

    # Limpiar emojis y resultado final "(89 - 87)" del summary
    titulo_limpio = re.sub(r'^[⚽🏀🥅]\s*', '', summary).strip()
    titulo_limpio = re.sub(r'\s*\(\d+\s*-\s*\d+\)\s*$', '', titulo_limpio).strip()

    par_normalizado = None
    if " vs " in titulo_limpio:
        partes = titulo_limpio.split(" vs ", 1)
        loc = normalizar_nombre_equipo(partes[0], deporte)
        vis = normalizar_nombre_equipo(partes[1], deporte)
        par_normalizado = f"{loc} vs {vis}"

    dtstart_prop = component.get("dtstart")
    fecha_dt = None
    if dtstart_prop and hasattr(dtstart_prop, "dt"):
        d = dtstart_prop.dt
        if isinstance(d, dt.datetime):
            fecha_dt = d.astimezone(TZ_MADRID).date() if d.tzinfo else d.date()
        elif isinstance(d, dt.date):
            fecha_dt = d

    return fecha_dt, par_normalizado, deporte, es_corrupto


def cargar_eventos_previos_ics(nombre_archivo="partidos.ics"):
    """Lee el archivo .ics existente para no perder eventos si un scraper falla puntualmente."""
    eventos_previos = {}
    if not os.path.exists(nombre_archivo):
        return eventos_previos
    try:
        with open(nombre_archivo, 'rb') as f:
            cal_previo = Calendar.from_ical(f.read())
            for component in cal_previo.walk():
                if component.name == "VEVENT":
                    uid = str(component.get('uid', ''))
                    if uid:
                        eventos_previos[uid] = component
        print(f"INFO: Cargados {len(eventos_previos)} eventos existentes de '{nombre_archivo}' como respaldo.")
    except Exception as e:
        print(f"AVISO: No se pudo leer el archivo .ics previo para respaldo: {e}")
    return eventos_previos


def _normalizar_partido_entrada(partido):
    """Normaliza nombres de equipos y recinto de un diccionario de partido antes de crear el VEVENT."""
    copia = dict(partido)
    name = copia.get("name", "")
    desc = copia.get("descripcion", "")
    estadio = copia.get("estadio", "")

    deporte = _detectar_deporte_texto(name, desc, estadio, copia.get("deporte"))
    copia["deporte"] = deporte

    if " vs " in name:
        p1, p2 = name.split(" vs ", 1)
        loc = normalizar_nombre_equipo(p1, deporte)
        vis = normalizar_nombre_equipo(p2, deporte)
        copia["name"] = f"{loc} vs {vis}"
        if deporte == "basket":
            copia["estadio"] = resolver_pabellon_basket(loc, estadio)
        elif deporte == "futsal":
            copia["estadio"] = resolver_pabellon_futsal(loc, estadio)
        else:
            copia["estadio"] = resolver_estadio_futbol(loc, estadio)

    return copia


def generar_archivo_ics(
    lista_partidos,
    nombre_archivo="partidos.ics",
    calname="Calendario Málaga CF y Unicaja",
    deportes_permitidos=None,
):
    eventos_previos = cargar_eventos_previos_ics(nombre_archivo)

    cal = Calendar()
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', calname)
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    partidos_normalizados = [_normalizar_partido_entrada(p) for p in lista_partidos]
    if deportes_permitidos:
        partidos_normalizados = [
            p for p in partidos_normalizados if p.get("deporte") in deportes_permitidos
        ]

    print(f"Procesando {len(partidos_normalizados)} eventos recién scrapeados para {nombre_archivo}...")
    nuevos_eventos_dict = {}
    nuevos_meta = []  # Lista de (uid, fecha_date, name_normalizado, tiene_resultado, hora_confirmada)

    # Prioridad: 1) Con resultado final, 2) Con hora confirmada, 3) Hora por confirmar
    def _prioridad_partido(x):
        tiene_res = bool(x.get('resultado') and x.get('resultado') != "N/A")
        hora_conf = x.get('hora_confirmada', "Hora por confirmar" not in x.get('descripcion', ''))
        if tiene_res:
            return 0
        if hora_conf:
            return 1
        return 2

    lista_ordenada = sorted(partidos_normalizados, key=_prioridad_partido)

    for partido in lista_ordenada:
        try:
            if not isinstance(partido.get('fecha_hora_inicio'), str) or not isinstance(partido.get('fecha_hora_fin'), str):
                continue

            dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
            dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])
            fecha_madrid_date = dt_inicio.astimezone(TZ_MADRID).date()

            tiene_resultado = bool(partido.get('resultado') and partido['resultado'] != "N/A")
            hora_confirmada = partido.get(
                'hora_confirmada',
                "Hora por confirmar" not in partido.get('descripcion', '')
            )

            # Evitar que un evento duplicado de la misma semana pise a uno ya procesado con mayor prioridad
            duplicado_en_ventana = False
            for _, f_prev, name_prev, _, _ in nuevos_meta:
                if name_prev == partido['name'] and abs((fecha_madrid_date - f_prev).days) <= 12:
                    duplicado_en_ventana = True
                    break
            if duplicado_en_ventana:
                continue

            evento = Event()
            titulo = partido['name']
            descripcion = partido.get('descripcion', '')
            if tiene_resultado:
                titulo = f"{partido['name']} ({partido['resultado']})"
                if "Próximo partido" in descripcion:
                    descripcion = descripcion.replace("Próximo partido", "Resultado")

            fecha_inicio_str = fecha_madrid_date.strftime('%Y%m%d')
            uid_base = f"{fecha_inicio_str}-{partido['name'].replace(' ', '')}"
            uid = f"{uid_base}@sportsmlg.com"

            if uid in nuevos_eventos_dict:
                continue

            # Preservar DTSTAMP previo si el evento no ha cambiado para no ensuciar git diff
            dtstamp_usar = datetime.now(dt.timezone.utc)
            if uid in eventos_previos:
                ev_ant = eventos_previos[uid]
                mismo_summary = str(ev_ant.get('summary', '')) == titulo
                mismo_loc = str(ev_ant.get('location', '')) == partido.get('estadio', 'Lugar no especificado')
                mismo_desc = str(ev_ant.get('description', '')) == descripcion
                dt_ant = ev_ant.get('dtstart').dt if ev_ant.get('dtstart') else None
                mismo_inicio = (dt_ant == dt_inicio)
                if mismo_summary and mismo_loc and mismo_desc and mismo_inicio and ev_ant.get('dtstamp'):
                    dtstamp_usar = ev_ant.get('dtstamp').dt

            evento.add('summary', titulo)
            evento.add('dtstart', dt_inicio)
            evento.add('dtend', dt_fin)
            evento.add('dtstamp', dtstamp_usar)
            evento.add('location', partido.get('estadio', 'Lugar no especificado'))
            evento.add('description', descripcion)
            evento.add('uid', uid)

            nuevos_eventos_dict[uid] = evento
            nuevos_meta.append((uid, fecha_madrid_date, partido['name'], tiene_resultado, hora_confirmada))
        except Exception as e:
            print(f"ERROR al generar evento para {partido.get('name', 'Partido Desconocido')}: {e}")
            continue

    # Reconciliación inteligente con eventos previos:
    # Mantenemos eventos previos de respaldo SOLO si:
    # 1) No están corruptos (ej. 'Advancing to next round' o '(Esp)')
    # 2) Pertenecen a los deportes permitidos de este archivo .ics
    # 3) No han sido reemplazados por el mismo partido en una fecha actualizada (±12 días)
    eventos_fusionados = {}
    for uid_prev, comp_prev in eventos_previos.items():
        if uid_prev in nuevos_eventos_dict:
            continue
        f_prev, par_prev, dep_prev, es_corrupto = _extraer_info_uid_o_summary(comp_prev)
        if es_corrupto:
            continue
        if deportes_permitidos and dep_prev not in deportes_permitidos:
            continue

        reemplazado = False
        if f_prev and par_prev:
            for uid_nuevo, f_nuevo, name_nuevo, _, _ in nuevos_meta:
                if name_nuevo == par_prev and abs((f_nuevo - f_prev).days) <= 12:
                    reemplazado = True
                    break
        if not reemplazado:
            # Si el evento previo tenía un estadio genérico antiguo ("Pabellón por confirmar", "Estadio Visitante"),
            # lo actualizamos automáticamente con nuestro resolvedor de recintos
            if par_prev and " vs " in par_prev:
                loc_eq, _ = par_prev.split(" vs ", 1)
                loc_actual = str(comp_prev.get("location", ""))
                if dep_prev == "basket":
                    nuevo_loc = resolver_pabellon_basket(loc_eq, loc_actual)
                elif dep_prev == "futsal":
                    nuevo_loc = resolver_pabellon_futsal(loc_eq, loc_actual)
                else:
                    nuevo_loc = resolver_estadio_futbol(loc_eq, loc_actual)
                if nuevo_loc != loc_actual:
                    comp_prev["location"] = nuevo_loc
            eventos_fusionados[uid_prev] = comp_prev

    eventos_fusionados.update(nuevos_eventos_dict)

    if len(eventos_fusionados) > 0:
        # Ordenar cronológicamente para generar un archivo .ics limpio y determinista
        def _clave_orden_vevent(item):
            _, ev = item
            dt_prop = ev.get('dtstart')
            if dt_prop and hasattr(dt_prop, 'dt'):
                d = dt_prop.dt
                if isinstance(d, dt.datetime):
                    return (d.astimezone(dt.timezone.utc).isoformat(), str(ev.get('uid', '')))
                return (d.isoformat(), str(ev.get('uid', '')))
            return ("", str(ev.get('uid', '')))

        for _, ev in sorted(eventos_fusionados.items(), key=_clave_orden_vevent):
            cal.add_component(ev)

        with open(nombre_archivo, 'wb') as f:
            f.write(cal.to_ical())
        print(f"¡ÉXITO! Archivo '{nombre_archivo}' guardado con {len(eventos_fusionados)} eventos ({len(nuevos_eventos_dict)} actualizados hoy).")
    else:
        print(f"ALERTA: No hay eventos nuevos ni previos para '{nombre_archivo}'. No se sobrescribe el archivo.")


def generar_todos_los_calendarios_ics(todos_los_eventos, directorio="."):
    """
    Genera todos los archivos .ics modulares para que cada usuario pueda suscribirse
    exactamente a la combinación de equipos que prefiera:
    - completo.ics (Málaga CF + Unicaja + Heredia 21 FS)
    - partidos.ics (Málaga CF + Unicaja)
    - malaga.ics (Solo Málaga CF)
    - unicaja.ics (Solo Unicaja)
    - heredia21.ics (Solo Heredia 21 FS)
    - malaga_heredia21.ics (Málaga CF + Heredia 21 FS)
    - unicaja_heredia21.ics (Unicaja + Heredia 21 FS)
    """
    rutas_generadas = {}
    for archivo, cfg in CALENDARIOS_MODULARES.items():
        ruta = os.path.join(directorio, archivo) if directorio != "." else archivo
        generar_archivo_ics(
            todos_los_eventos,
            nombre_archivo=ruta,
            calname=cfg["calname"],
            deportes_permitidos=cfg["deportes"],
        )
        rutas_generadas[archivo] = ruta
    return rutas_generadas


def generar_dashboard_html(nombre_ics="completo.ics", nombre_html="index.html"):
    """
    Genera una página web estática moderna (index.html) para GitHub Pages con los
    próximos partidos, resultados recientes y un selector interactivo de suscripción
    para elegir cualquier combinación de Málaga CF, Unicaja y Heredia 21 Femenino FS.
    """
    archivo_lectura = nombre_ics if os.path.exists(nombre_ics) else "partidos.ics"
    if not os.path.exists(archivo_lectura):
        return
    try:
        with open(archivo_lectura, "rb") as f:
            cal = Calendar.from_ical(f.read())

        ahora_utc = datetime.now(dt.timezone.utc)
        proximos = []
        resultados = []

        for comp in cal.walk():
            if comp.name != "VEVENT":
                continue
            summary = str(comp.get("summary", ""))
            location = str(comp.get("location", ""))
            description = str(comp.get("description", ""))
            dt_inicio = comp.get("dtstart").dt
            if not isinstance(dt_inicio, dt.datetime):
                dt_inicio = dt.datetime.combine(dt_inicio, dt.time(12, 0), tzinfo=TZ_MADRID)
            dt_madrid = dt_inicio.astimezone(TZ_MADRID)

            deporte = _detectar_deporte_texto(summary, description, location)
            tiene_res = bool(re.search(r'\(\d+\s*-\s*\d+\)$', summary))
            por_confirmar = "Hora por confirmar" in description

            item = {
                "summary": summary,
                "location": location,
                "description": description,
                "dt_madrid": dt_madrid,
                "fecha_str": dt_madrid.strftime("%d/%m/%Y"),
                "hora_str": "Por confirmar" if por_confirmar else dt_madrid.strftime("%H:%M"),
                "deporte": deporte,
                "tiene_res": tiene_res,
            }
            if tiene_res or dt_inicio < ahora_utc - dt.timedelta(hours=3):
                resultados.append(item)
            else:
                proximos.append(item)

        proximos.sort(key=lambda x: x["dt_madrid"])
        resultados.sort(key=lambda x: x["dt_madrid"], reverse=True)

        def _render_card(it):
            if it["deporte"] == "basket":
                badge_cls = "badge-basket"
                icono = "🏀 Unicaja"
            elif it["deporte"] == "futsal":
                badge_cls = "badge-futsal"
                icono = "🥅 Heredia 21 FS"
            else:
                badge_cls = "badge-futbol"
                icono = "⚽ Málaga CF"
            return (
                f'<div class="match-card" data-sport="{it["deporte"]}">'
                f'<div class="match-header"><span class="badge {badge_cls}">{icono}</span>'
                f'<span class="match-date">{it["fecha_str"]} · {it["hora_str"]}</span></div>'
                f'<div class="match-title">{it["summary"]}</div>'
                f'<div class="match-loc">📍 {it["location"]}</div>'
                f'<div class="match-desc">{it["description"]}</div>'
                f'</div>'
            )

        cards_proximos = "\n".join(_render_card(x) for x in proximos)
        cards_resultados = "\n".join(_render_card(x) for x in resultados[:24])

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Calendario Deportivo Málaga: Málaga CF, Unicaja y Heredia 21 FS</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #1e293b;
      --card-alt: #162032;
      --text: #f8fafc;
      --muted: #94a3b8;
      --malaga: #0072ce;
      --unicaja: #009639;
      --heredia: #db2777;
      --border: #334155;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1rem;
    }}
    .container {{ max-width: 1040px; margin: 0 auto; }}
    header {{
      text-align: center;
      margin-bottom: 2rem;
      padding: 2rem 1.5rem;
      background: linear-gradient(135deg, rgba(0,114,206,0.22), rgba(0,150,57,0.22), rgba(219,39,119,0.18));
      border: 1px solid var(--border);
      border-radius: 1rem;
    }}
    h1 {{ font-size: 1.85rem; margin-bottom: 0.4rem; }}
    .subtitle {{ color: var(--muted); margin-bottom: 1.35rem; font-size: 0.96rem; }}
    .customizer {{
      background: rgba(15, 23, 42, 0.72);
      border: 1px solid var(--border);
      border-radius: 0.85rem;
      padding: 1.25rem;
      max-width: 780px;
      margin: 0 auto;
    }}
    .customizer-title {{
      font-size: 0.95rem;
      font-weight: 700;
      margin-bottom: 0.75rem;
      color: #e2e8f0;
    }}
    .team-toggles {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.65rem;
      justify-content: center;
      margin-bottom: 0.9rem;
    }}
    .team-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.5rem 1rem;
      border-radius: 2rem;
      border: 1.5px solid var(--border);
      background: var(--card);
      color: var(--muted);
      cursor: pointer;
      font-weight: 600;
      font-size: 0.9rem;
      user-select: none;
      transition: all 0.15s;
    }}
    .team-toggle input {{ accent-color: #38bdf8; width: 1rem; height: 1rem; cursor: pointer; }}
    .team-toggle.checked-futbol {{ border-color: #38bdf8; color: #f8fafc; background: rgba(0,114,206,0.28); }}
    .team-toggle.checked-basket {{ border-color: #4ade80; color: #f8fafc; background: rgba(0,150,57,0.28); }}
    .team-toggle.checked-futsal {{ border-color: #f472b6; color: #f8fafc; background: rgba(219,39,119,0.28); }}
    .selected-feed-info {{
      font-size: 0.84rem;
      color: #cbd5e1;
      margin-bottom: 0.95rem;
    }}
    .selected-feed-info code {{
      background: rgba(255,255,255,0.08);
      padding: 0.15rem 0.45rem;
      border-radius: 0.35rem;
      color: #38bdf8;
      font-weight: 600;
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 0.7rem; justify-content: center; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.65rem 1.15rem;
      border-radius: 0.5rem;
      font-weight: 600;
      font-size: 0.9rem;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      transition: transform 0.15s, border-color 0.15s, opacity 0.15s;
    }}
    .btn:hover {{ transform: translateY(-2px); border-color: #64748b; }}
    .btn-primary {{ background: var(--malaga); border-color: var(--malaga); }}
    .btn-success {{ background: var(--unicaja); border-color: var(--unicaja); }}
    .filters {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      justify-content: center;
      margin-bottom: 1.5rem;
    }}
    .filter-btn {{
      padding: 0.45rem 1rem;
      border-radius: 2rem;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--muted);
      cursor: pointer;
      font-weight: 600;
    }}
    .filter-btn.active {{ color: var(--text); border-color: var(--text); }}
    h2 {{ margin: 1.5rem 0 1rem; font-size: 1.35rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1rem;
    }}
    .match-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }}
    .match-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; }}
    .badge {{ padding: 0.15rem 0.6rem; border-radius: 1rem; font-weight: 600; font-size: 0.78rem; }}
    .badge-futbol {{ background: rgba(0,114,206,0.25); color: #60a5fa; }}
    .badge-basket {{ background: rgba(0,150,57,0.25); color: #4ade80; }}
    .badge-futsal {{ background: rgba(219,39,119,0.25); color: #f472b6; }}
    .match-date {{ color: var(--muted); font-weight: 500; }}
    .match-title {{ font-size: 1.05rem; font-weight: 700; margin-top: 0.2rem; }}
    .match-loc {{ font-size: 0.88rem; color: #cbd5e1; }}
    .match-desc {{ font-size: 0.8rem; color: var(--muted); }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚽ Málaga CF · 🏀 Unicaja · 🥅 Heredia 21 FS</h1>
      <p class="subtitle">Calendario sincronizado automáticamente ({len(proximos)} próximos partidos · {len(resultados)} resultados registrados)</p>

      <div class="customizer">
        <div class="customizer-title">1. Elige a qué equipos quieres suscribirte en tu calendario:</div>
        <div class="team-toggles">
          <label class="team-toggle checked-futbol" id="lbl-futbol">
            <input type="checkbox" id="chk-futbol" checked onchange="actualizarSuscripcion()" />
            ⚽ Málaga CF
          </label>
          <label class="team-toggle checked-basket" id="lbl-basket">
            <input type="checkbox" id="chk-basket" checked onchange="actualizarSuscripcion()" />
            🏀 Unicaja Baloncesto
          </label>
          <label class="team-toggle checked-futsal" id="lbl-futsal">
            <input type="checkbox" id="chk-futsal" checked onchange="actualizarSuscripcion()" />
            🥅 Heredia 21 Femenino FS
          </label>
        </div>

        <div class="selected-feed-info" id="feed-status">
          Suscripción seleccionada: <strong id="feed-label">Málaga CF + Unicaja + Heredia 21 FS</strong> (<code id="feed-file">completo.ics</code>)
        </div>

        <div class="actions" id="subscription-actions">
          <a class="btn btn-primary" id="btn-gcal" href="https://calendar.google.com/calendar/r?cid=webcal://espimlg.github.io/sportsmlgcalendar/completo.ics" target="_blank" rel="noopener">📅 Añadir a Google Calendar</a>
          <a class="btn btn-success" id="btn-webcal" href="webcal://espimlg.github.io/sportsmlgcalendar/completo.ics">🍏 Suscribirse en Apple / Outlook</a>
          <a class="btn" id="btn-download" href="completo.ics" download>⬇️ Descargar .ics</a>
          <button class="btn" id="btn-copy" type="button" onclick="copiarEnlace()">📋 Copiar URL</button>
        </div>
      </div>
    </header>

    <div class="filters">
      <button class="filter-btn active" onclick="filtrar('all', this)">Todos ({len(proximos) + len(resultados)})</button>
      <button class="filter-btn" onclick="filtrar('futbol', this)">⚽ Málaga CF</button>
      <button class="filter-btn" onclick="filtrar('basket', this)">🏀 Unicaja</button>
      <button class="filter-btn" onclick="filtrar('futsal', this)">🥅 Heredia 21 FS</button>
    </div>

    <h2>Próximos Partidos ({len(proximos)})</h2>
    <div class="grid">
      {cards_proximos}
    </div>

    <h2>Últimos Resultados</h2>
    <div class="grid">
      {cards_resultados}
    </div>
  </div>
  <script>
    const BASE_HOST = "espimlg.github.io/sportsmlgcalendar";
    const MAPA_CALENDARIOS = {{
      "1-1-1": {{ file: "completo.ics", label: "Málaga CF + Unicaja + Heredia 21 FS" }},
      "1-1-0": {{ file: "partidos.ics", label: "Málaga CF + Unicaja" }},
      "1-0-0": {{ file: "malaga.ics", label: "Solo Málaga CF" }},
      "0-1-0": {{ file: "unicaja.ics", label: "Solo Unicaja Baloncesto" }},
      "0-0-1": {{ file: "heredia21.ics", label: "Solo Heredia 21 Femenino FS" }},
      "1-0-1": {{ file: "malaga_heredia21.ics", label: "Málaga CF + Heredia 21 FS" }},
      "0-1-1": {{ file: "unicaja_heredia21.ics", label: "Unicaja + Heredia 21 FS" }}
    }};

    function actualizarSuscripcion() {{
      const f = document.getElementById('chk-futbol').checked;
      const b = document.getElementById('chk-basket').checked;
      const s = document.getElementById('chk-futsal').checked;

      document.getElementById('lbl-futbol').classList.toggle('checked-futbol', f);
      document.getElementById('lbl-basket').classList.toggle('checked-basket', b);
      document.getElementById('lbl-futsal').classList.toggle('checked-futsal', s);

      const key = `${{f ? 1 : 0}}-${{b ? 1 : 0}}-${{s ? 1 : 0}}`;
      const actionsDiv = document.getElementById('subscription-actions');
      const statusDiv = document.getElementById('feed-status');

      if (!MAPA_CALENDARIOS[key]) {{
        statusDiv.innerHTML = '<span style="color:#f87171;">Selecciona al menos un equipo para generar tu enlace de suscripción.</span>';
        actionsDiv.style.opacity = '0.4';
        actionsDiv.style.pointerEvents = 'none';
        return;
      }}

      actionsDiv.style.opacity = '1';
      actionsDiv.style.pointerEvents = 'auto';
      const cfg = MAPA_CALENDARIOS[key];
      statusDiv.innerHTML = `Suscripción seleccionada: <strong id="feed-label">${{cfg.label}}</strong> (<code id="feed-file">${{cfg.file}}</code>)`;

      const webcalUrl = `webcal://${{BASE_HOST}}/${{cfg.file}}`;
      document.getElementById('btn-gcal').href = `https://calendar.google.com/calendar/r?cid=${{webcalUrl}}`;
      document.getElementById('btn-webcal').href = webcalUrl;
      document.getElementById('btn-download').href = cfg.file;

      // Filtrar tarjetas visualmente según los equipos marcados
      const deportesActivos = new Set();
      if (f) deportesActivos.add('futbol');
      if (b) deportesActivos.add('basket');
      if (s) deportesActivos.add('futsal');

      document.querySelectorAll('.match-card').forEach(card => {{
        card.style.display = deportesActivos.has(card.dataset.sport) ? 'flex' : 'none';
      }});
    }}

    function copiarEnlace() {{
      const fileEl = document.getElementById('feed-file');
      const archivo = fileEl ? fileEl.textContent : 'completo.ics';
      const url = `https://${{BASE_HOST}}/${{archivo}}`;
      navigator.clipboard.writeText(url).then(() => {{
        const btn = document.getElementById('btn-copy');
        const original = btn.textContent;
        btn.textContent = '✅ ¡Enlace copiado!';
        setTimeout(() => {{ btn.textContent = original; }}, 2000);
      }});
    }}

    function filtrar(deporte, btn) {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.match-card').forEach(card => {{
        card.style.display = (deporte === 'all' || card.dataset.sport === deporte) ? 'flex' : 'none';
      }});
    }}
  </script>
</body>
</html>
"""
        with open(nombre_html, "w", encoding="utf-8") as f_html:
            f_html.write(html_content)
        print(f"INFO: Dashboard web '{nombre_html}' actualizado correctamente.")
    except Exception as e:
        print(f"AVISO: No se pudo generar '{nombre_html}': {e}")


# --- LÓGICA PRINCIPAL ---
if __name__ == "__main__":
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"user-agent={DEFAULT_HEADERS['User-Agent']}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        try:
            driver = webdriver.Chrome(options=options)
            print("ChromeDriver iniciado con Selenium Manager nativo.")
        except Exception as native_error:
            print(f"Aviso Selenium Manager nativo: {native_error}. Probando ChromeDriverManager...")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            print("ChromeDriver iniciado con webdriver_manager.")

        if driver:
            try:
                driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Europe/Madrid"})
            except Exception:
                pass
            try:
                stealth(
                    driver,
                    languages=["es-ES", "es", "en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True
                )
                print("Stealth y zona horaria Europe/Madrid aplicados.")
            except Exception as stealth_error:
                print(f"ADVERTENCIA Stealth: {stealth_error}")

        todos_los_eventos = []
        print("\n--- Iniciando scrape de Málaga ---")
        try:
            todos_los_eventos.extend(obtener_proximos_partidos_malaga(driver))
        except Exception as e:
            print(f"ERROR GRAVE scrape próximos Málaga: {e}")

        try:
            todos_los_eventos.extend(obtener_resultados_malaga_flashscore(driver))
        except Exception as e:
            print(f"ERROR GRAVE scrape resultados Málaga: {e}")
        print("--- Fin scrape de Málaga ---")

        print("\n--- Iniciando scrape de Unicaja ---")
        try:
            todos_los_eventos.extend(obtener_proximos_partidos_unicaja(driver))
        except Exception as e:
            print(f"ERROR GRAVE scrape próximos Unicaja: {e}")

        try:
            todos_los_eventos.extend(obtener_resultados_unicaja(driver))
        except Exception as e:
            print(f"ERROR GRAVE scrape resultados Unicaja: {e}")
        print("--- Fin scrape de Unicaja ---")

        print("\n--- Iniciando scrape de Heredia 21 Femenino FS (RFAF) ---")
        try:
            todos_los_eventos.extend(obtener_partidos_heredia21_rfaf(driver))
        except Exception as e:
            print(f"ERROR GRAVE scrape Heredia 21 FS: {e}")
        print("--- Fin scrape de Heredia 21 Femenino FS ---")

        print("\n--- Iniciando generación de calendarios ICS modulares ---")
        if todos_los_eventos:
            print(f"Total de eventos encontrados en esta ejecución: {len(todos_los_eventos)}")
        else:
            print("No se encontró info nueva en esta ejecución.")
        generar_todos_los_calendarios_ics(todos_los_eventos)
        generar_dashboard_html("completo.ics", "index.html")
        print("--- Fin generación de calendarios ICS y Dashboard ---")
    except Exception as e:
        print(f"Error general no recuperable: {e}")
    finally:
        if driver:
            try:
                driver.quit()
                print("Driver cerrado.")
            except Exception as quit_error:
                print(f"Error al cerrar driver: {quit_error}")
        else:
            print("Driver no iniciado.")
