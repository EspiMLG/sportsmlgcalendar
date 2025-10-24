import os
import time
import datetime as dt
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pytz
from icalendar import Calendar, Event

# --- ZONA HORARIA ---
TZ_MADRID = pytz.timezone('Europe/Madrid')
ANO_ACTUAL = dt.datetime.now().year

# --- FUNCIÓN 1: PRÓXIMOS MÁLAGA (Tu función original, adaptada) ---
def traducir_fecha_malaga(fecha_es):
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

def obtener_proximos_partidos_malaga(driver):
    print("Buscando próximos partidos Málaga CF...")
    eventos = []
    driver.get("https://www.malagacf.com/partidos")
    # Esperamos a que la card esté presente
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard"))
    )
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('article', class_='MkFootballMatchCard')

    for partido in partidos:
        equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
        equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
        equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
        hora_raw = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else '10:00'
        fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else 'Desconocido'
        estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'
        
        name = f"{equipo_local} vs {equipo_visitante}"

        if hora_raw == '-- : --':
            continue # Si no hay hora, no es un próximo partido confirmado

        if ',' in fecha_raw:
            fecha_sin_dia = fecha_raw.split(', ')[1]
        else:
            fecha_sin_dia = fecha_raw
        
        fecha_traducida = traducir_fecha_malaga(fecha_sin_dia)
        if not fecha_traducida:
            print(f"Error al traducir fecha Málaga: {fecha_raw}")
            continue

        fecha_hora_str = f"{fecha_traducida} {ANO_ACTUAL} {hora_raw.replace('.', '')}"
        fecha_hora_naive = None
        
        try:
            formato = '%d de %b %Y %I:%M %p'
            fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
        except ValueError:
            try:
                formato = '%d de %b %Y %H:%M'
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
            except ValueError as e:
                print(f"Error procesando fecha Málaga: {name} en {fecha_hora_str}")
                continue
        
        fecha_hora_local = TZ_MADRID.localize(fecha_hora_naive)
        fecha_hora_inicio = fecha_hora_local.isoformat()
        fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()

        localidad = "local" if "Málaga CF" in equipo_local else "visitante"
        estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio

        eventos.append({
            "fecha_hora_inicio": fecha_hora_inicio,
            "fecha_hora_fin": fecha_hora_fin,
            "estadio": estadio_final,
            "name": name,
            "descripcion": "Próximo partido del Málaga CF"
        })
            
    print(f"Encontrados {len(eventos)} próximos partidos de Málaga CF.")
    return eventos

# --- FUNCIÓN 2: RESULTADOS MÁLAGA ---
def obtener_resultados_malaga(driver):
    print("Buscando resultados Málaga CF...")
    eventos = []
    driver.get("https://www.malagacf.com/partidos?activeTab=results")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard"))
    )
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('article', class_='MkFootballMatchCard')

    for partido in partidos:
        equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
        equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
        equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
        
        # --- Lógica para el resultado ---
        score_element = partido.find('div', class_='MkFootballMatchCard__score')
        if not score_element:
            continue # Si no hay score, no es un resultado
        
        resultado_local = score_element.find_all('span')[0].text.strip()
        resultado_visitante = score_element.find_all('span')[1].text.strip()
        resultado_final = f"{resultado_local} - {resultado_visitante}"

        # --- Lógica para la fecha (es diferente en resultados) ---
        fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else 'Desconocido'
        # Asumimos una hora fija (ej. 12:00) ya que la web no la proporciona claramente en resultados
        hora_raw = "12:00" 
        name = f"{equipo_local} vs {equipo_visitante}"

        if ',' in fecha_raw:
            fecha_sin_dia = fecha_raw.split(', ')[1]
        else:
            fecha_sin_dia = fecha_raw
        
        fecha_traducida = traducir_fecha_malaga(fecha_sin_dia)
        if not fecha_traducida:
            print(f"Error al traducir fecha resultado Málaga: {fecha_raw}")
            continue

        fecha_hora_str = f"{fecha_traducida} {ANO_ACTUAL} {hora_raw}"
        
        try:
            formato = '%d de %b %Y %H:%M'
            fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
        except ValueError as e:
            print(f"Error procesando fecha resultado Málaga: {name} en {fecha_hora_str}")
            continue
        
        fecha_hora_local = TZ_MADRID.localize(fecha_hora_naive)
        fecha_hora_inicio = fecha_hora_local.isoformat()
        fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()

        localidad = "local" if "Málaga CF" in equipo_local else "visitante"
        estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'
        estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio

        eventos.append({
            "fecha_hora_inicio": fecha_hora_inicio,
            "fecha_hora_fin": fecha_hora_fin,
            "estadio": estadio_final,
            "name": name,
            "descripcion": "Resultado partido del Málaga CF",
            "resultado": resultado_final # <-- ¡Aquí está el resultado!
        })

    print(f"Encontrados {len(eventos)} resultados de Málaga CF.")
    return eventos

# --- FUNCIÓN 3: PRÓXIMOS PARTIDOS UNICAJA ---
def obtener_proximos_partidos_unicaja(driver):
    print("Buscando próximos partidos Unicaja...")
    eventos = []
    driver.get("https://www.unicajabaloncesto.com/calendario")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.partido"))
    )
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('div', class_='partido')

    for partido in partidos:
        # Si tiene marcador, es un resultado, lo saltamos
        if partido.find('div', class_='marcador_local'):
            continue
            
        equipo_local = partido.find('span', class_='team_name_local').text.strip()
        equipo_visitante = partido.find('span', class_='team_name_visitante').text.strip()
        name = f"{equipo_local} vs {equipo_visitante}"

        fecha_raw = partido.find('span', class_='fecha').text.strip() # Formato "dd.mm.yyyy"
        hora_raw = partido.find('span', class_='hora').text.strip()   # Formato "hh:mm h."
        
        if not fecha_raw or not hora_raw or 'falta' in hora_raw.lower():
            continue # No hay fecha/hora confirmada

        try:
            hora_limpia = hora_raw.split(' ')[0] # "20:00 h." -> "20:00"
            fecha_hora_str = f"{fecha_raw} {hora_limpia}"
            fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
            fecha_hora_local = TZ_MADRID.localize(fecha_hora_naive)
            fecha_hora_inicio = fecha_hora_local.isoformat()
            fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()
        except ValueError as e:
            print(f"Error procesando fecha Unicaja: {name} en {fecha_hora_str}")
            continue

        lugar_raw = partido.find('span', class_='pabellon')
        lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón por confirmar"

        eventos.append({
            "fecha_hora_inicio": fecha_hora_inicio,
            "fecha_hora_fin": fecha_hora_fin,
            "estadio": lugar,
            "name": name,
            "descripcion": "Próximo partido del Unicaja"
        })
        
    print(f"Encontrados {len(eventos)} próximos partidos de Unicaja.")
    return eventos

# --- FUNCIÓN 4: RESULTADOS UNICAJA ---
def obtener_resultados_unicaja(driver):
    print("Buscando resultados Unicaja...")
    eventos = []
    driver.get("https://www.unicajabaloncesto.com/calendario")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.partido"))
    )
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('div', class_='partido')

    for partido in partidos:
        resultado_local_raw = partido.find('div', class_='marcador_local')
        resultado_visitante_raw = partido.find('div', class_='marcador_visitante')
        
        # Si NO tiene marcador, es un partido futuro, lo saltamos
        if not resultado_local_raw or not resultado_visitante_raw:
            continue
            
        resultado_final = f"{resultado_local_raw.text.strip()} - {resultado_visitante_raw.text.strip()}"
        
        equipo_local = partido.find('span', class_='team_name_local').text.strip()
        equipo_visitante = partido.find('span', class_='team_name_visitante').text.strip()
        name = f"{equipo_local} vs {equipo_visitante}"

        fecha_raw = partido.find('span', class_='fecha').text.strip() # Formato "dd.mm.yyyy"
        # Asumimos hora fija para resultados, ya que la web no la muestra
        hora_limpia = "12:00" 

        try:
            fecha_hora_str = f"{fecha_raw} {hora_limpia}"
            fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
            fecha_hora_local = TZ_MADRID.localize(fecha_hora_naive)
            fecha_hora_inicio = fecha_hora_local.isoformat()
            fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()
        except ValueError as e:
            print(f"Error procesando fecha resultado Unicaja: {name} en {fecha_hora_str}")
            continue

        lugar_raw = partido.find('span', class_='pabellon')
        lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón"

        eventos.append({
            "fecha_hora_inicio": fecha_hora_inicio,
            "fecha_hora_fin": fecha_hora_fin,
            "estadio": lugar,
            "name": name,
            "descripcion": "Resultado partido del Unicaja",
            "resultado": resultado_final # <-- ¡Aquí está el resultado!
        })
        
    print(f"Encontrados {len(eventos)} resultados de Unicaja.")
    return eventos


# --- FUNCIÓN PRINCIPAL PARA GENERAR EL .ICS (Modificada) ---
def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    cal = Calendar()
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    print(f"Generando {len(lista_partidos)} eventos totales (partidos y resultados) para {nombre_archivo}...")

    for partido in lista_partidos:
        evento = Event()
        
        # --- LÓGICA DE TÍTULO MODIFICADA ---
        # Si el partido tiene un resultado, lo añade al título
        titulo = partido['name']
        if 'resultado' in partido and partido['resultado']:
            titulo = f"{partido['name']} ({partido['resultado']})"
        
        dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
        dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

        evento.add('summary', titulo) # <--- Título modificado
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

# --- LÓGICA PRINCIPAL (Modificada para llamarlo todo) ---
if __name__ == "__main__":
    
    # --- Configurar driver de Selenium UNA VEZ (CON NUEVAS OPCIONES) ---
    options = Options()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
    
    # --- LÍNEAS NUEVAS ANTI-BOT ---
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    # --- FIN DE LÍNEAS NUEVAS ---
    
    driver = None
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        todos_los_eventos = []

        # 1. Obtener próximos Málaga
        try:
            todos_los_eventos.extend(obtener_proximos_partidos_malaga(driver))
        except Exception as e:
            print(f"ERROR GRAVE al scrapear próximos Málaga: {e}")

        # 2. Obtener resultados Málaga
        try:
            todos_los_eventos.extend(obtener_resultados_malaga(driver))
        except Exception as e:
            print(f"ERROR GRAVE al scrapear resultados Málaga: {e}")
            
        # 3. Obtener próximos Unicaja
        try:
            todos_los_eventos.extend(obtener_proximos_partidos_unicaja(driver))
        except Exception as e:
            print(f"ERROR GRAVE al scrapear próximos Unicaja: {e}")

        # 4. Obtener resultados Unicaja
        try:
            todos_los_eventos.extend(obtener_resultados_unicaja(driver))
        except Exception as e:
            print(f"ERROR GRAVE al scrapear resultados Unicaja: {e}")


        # 5. Generar el archivo .ics final
        if todos_los_eventos and len(todos_los_eventos) > 0:
            print(f"Total de eventos a generar: {len(todos_los_eventos)}")
            generar_archivo_ics(todos_los_eventos, "partidos.ics")
        else:
            print("No se encontró información de ningún partido o resultado.")
            
    except Exception as e:
        print(f"Ha ocurrido un error general: {e}")
    finally:
        # Asegúrate de cerrar el driver pase lo que pase
        if driver:
            driver.quit()
