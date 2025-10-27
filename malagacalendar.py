import os
import time
import datetime as dt
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import pytz
from icalendar import Calendar, Event

# --- Función de scraping (Modificada) ---
def traducir_fecha(fecha_es):
    traduccion = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    fecha_es_limpia = fecha_es.lower().replace('.', '')
    for mes_es, mes_en in traduccion.items():
        if mes_es in fecha_es_limpia:
            return fecha_es_limpia.replace(mes_es, mes_en)
    return None

def obtener_proximos_partidos():
    options = Options()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get("https://www.malagacf.com/partidos")
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        partidos = soup.find_all('article', class_='MkFootballMatchCard')

        eventos = []
        ano_actual = dt.datetime.now().year
        tz_madrid = pytz.timezone('Europe/Madrid')

        for partido in partidos:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            hora_raw = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else '10:00'
            fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else 'Desconocido'
            estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'
            
            name = f"{equipo_local} vs {equipo_visitante}"

            if hora_raw == '-- : --':
                hora_raw = '10:00'

            # 1. Limpiar día de la semana (ej: "dom, 26 oct" -> "26 oct")
            if ',' in fecha_raw:
                fecha_sin_dia = fecha_raw.split(', ')[1]
            else:
                fecha_sin_dia = fecha_raw
            
            # 2. Traducir mes (ej: "26 oct" -> "26 Oct")
            fecha_traducida = traducir_fecha(fecha_sin_dia)
            if not fecha_traducida:
                print(f"Error al traducir la fecha: {fecha_raw}")
                continue

            # 3. Combinar y probar formatos
            fecha_hora_str = f"{fecha_traducida} {ano_actual} {hora_raw.replace('.', '')}"
            fecha_hora_naive = None
            
            try:
                # Formato 12h: "26 Oct 2025 01:00 pm"
                # --- CORRECCIÓN AQUÍ ---
                formato = '%d %b %Y %I:%M %p'
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
            except ValueError:
                try:
                    # Formato 24h: "30 Nov 2025 10:00"
                    # --- CORRECCIÓN AQUÍ ---
                    formato = '%d %b %Y %H:%M'
                    fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
                except ValueError as e:
                    print(f"Error al procesar la fecha y hora para el partido: {name} en {fecha_hora_str}")
                    print(f"Error detallado: {e}")
                    continue
            
            # 4. Asignar zona horaria
            fecha_hora_local = tz_madrid.localize(fecha_hora_naive)
            fecha_hora_inicio = fecha_hora_local.isoformat()
            fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()

            localidad = "local" if "Málaga CF" in equipo_local else "visitante"
            descripcion = "Próximo partido del Málaga CF"
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "localidad": localidad,
                "descripcion": descripcion,
                "estadio": estadio_final,
                "name": name
            })
            
        return eventos # <-- ¡OJO! Tu código original tenía un 'return' aquí dentro del bucle, lo he sacado.
    except Exception as e:
        print(f"No se pudo extraer la información de los partidos: {e}")
        return None
    finally:
        driver.quit()
        
# --- NUEVA FUNCIÓN PARA GENERAR EL .ICS (Sin cambios) ---
def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    cal = Calendar()
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    print(f"Generando {len(lista_partidos)} eventos para {nombre_archivo}...")

    for partido in lista_partidos:
        evento = Event()
        dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
        dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

        evento.add('summary', partido['name'])
        evento.add('dtstart', dt_inicio)
        evento.add('dtend', dt_fin)
        evento.add('dtstamp', datetime.now(tz=pytz.utc))
        evento.add('location', partido['estadio'])
        evento.add('description', partido['descripcion'])
        
        uid = f"{partido['fecha_hora_inicio']}-{partido['name'].replace(' ', '')}@sportsmlg.com"
        evento.add('uid', uid)
        cal.add_component(evento)

    with open(nombre_archivo, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"¡Éxito! Archivo '{nombre_archivo}' generado correctamente.")

# --- LÓGICA PRINCIPAL (Modificada para que no falle si no hay partidos) ---
def actualizar_proximos_partidos():
    proximos_partidos = obtener_proximos_partidos()
    
    if proximos_partidos and len(proximos_partidos) > 0:
        print(f"Próximos partidos encontrados: {len(proximos_partidos)}")
        generar_archivo_ics(proximos_partidos, "partidos.ics")
    else:
        print("No se encontró información de los próximos partidos o la lista está vacía.")
        # Creamos un .ics vacío para que el git add no falle
        # aunque lo ideal es que el 'if' del git add lo maneje.
        # Por seguridad, nos aseguramos de que el script no falle.
        # Opcional: generar un ics vacío
        # generar_archivo_ics([], "partidos.ics") 
        # print("Se ha generado un archivo .ics vacío.")

if __name__ == "__main__":
    actualizar_proximos_partidos()



