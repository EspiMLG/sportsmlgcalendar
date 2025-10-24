import os
import time
import datetime as dt
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import pytz
from icalendar import Calendar, Event # <-- Importación añadida

# --- Función de scraping (sin cambios) ---
def traducir_fecha(fecha_es):
    traduccion = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    for mes_es, mes_en in traduccion.items():
        if mes_es in fecha_es:
            return fecha_es.replace(mes_es, mes_en)
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
        for partido in partidos:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            hora = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else '10:00'
            fecha = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else 'Desconocido'
            estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'

            if hora == '-- : --':
                hora = '10:00'

            fecha_traducida = traducir_fecha(fecha)
            if not fecha_traducida:
                print(f"Error al procesar la fecha: {fecha}")
                continue

            try:
                fecha_hora_naive = dt.datetime.strptime(f"{fecha_traducida} {hora}", '%d %b %Y %H:%M')
                tz_madrid = pytz.timezone('Europe/Madrid')
                # La hora de la web del Málaga ya es la hora de España, no sumes 2 horas.
                # Solo localízala
                fecha_hora_local = tz_madrid.localize(fecha_hora_naive) 

                fecha_hora_inicio = fecha_hora_local.isoformat()
                fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()
            except ValueError:
                print(f"Error al procesar la fecha y hora para el partido: {equipo_local} vs {equipo_visitante} en {fecha} {hora}")
                continue

            localidad = "local" if "Málaga CF" in equipo_local else "visitante"
            descripcion = "Próximo partido del Málaga CF"
            name = f"{equipo_local} vs {equipo_visitante}"

            # Replicamos la lógica del estadio que tenías
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "localidad": localidad,
                "descripcion": descripcion,
                "estadio": estadio_final,
                "name": name
            })
            
        return eventos
    except Exception as e:
        print(f"No se pudo extraer la información de los partidos: {e}")
        return None
    finally:
        driver.quit()

# --- NUEVA FUNCIÓN PARA GENERAR EL .ICS ---
def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    """
    Toma la lista de partidos y genera el archivo .ics
    """
    cal = Calendar()
    
    # Propiedades estándar del calendario
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    print(f"Generando eventos para {nombre_archivo}...")

    for partido in lista_partidos:
        evento = Event()
        
        # Obtenemos las fechas ISO (que ya tienen timezone)
        dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
        dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

        evento.add('summary', partido['name'])
        evento.add('dtstart', dt_inicio)
        evento.add('dtend', dt_fin)
        evento.add('dtstamp', datetime.now(tz=pytz.utc))
        evento.add('location', partido['estadio'])
        evento.add('description', partido['descripcion'])
        
        # UID único para que el calendario sepa qué evento actualizar
        uid = f"{partido['fecha_hora_inicio']}-{partido['name'].replace(' ', '')}@sportsmlg.com"
        evento.add('uid', uid)
        
        cal.add_component(evento)

    # Guarda el calendario en un archivo
    with open(nombre_archivo, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"¡Éxito! Archivo '{nombre_archivo}' generado correctamente.")

# --- LÓGICA PRINCIPAL MODIFICADA ---
def actualizar_proximos_partidos():
    proximos_partidos = obtener_proximos_partidos()
    
    if proximos_partidos:
        print(f"Próximos partidos encontrados: {len(proximos_partidos)}")
        
        # 1. Generar el archivo .ics
        generar_archivo_ics(proximos_partidos, "partidos.ics")
        
        # 2. (Opcional) Aquí podrías añadir la lógica para Unicaja
        # y añadirla a la misma lista antes de generar el .ics
        
    else:
        print("No se encontró información de los próximos partidos.")

# Llamada principal
if __name__ == "__main__":
    actualizar_proximos_partidos()
