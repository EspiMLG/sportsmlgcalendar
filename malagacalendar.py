import os
import time
import datetime as dt
from datetime import datetime
import random
import locale # <-- ¡NUEVO! Para forzar el idioma en fechas
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
from selenium_stealth import stealth

# --- ZONA HORARIA ---
TZ_MADRID = pytz.timezone('Europe/Madrid')
ANO_ACTUAL = dt.datetime.now().year

# --- FUNCIÓN 1: PRÓXIMOS MÁLAGA (¡Esta ya funciona!) ---
def traducir_fecha_malaga(fecha_es):
    traduccion = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    # Corregimos traducción para 3 letras exactas requeridas por %b
    traduccion_3_letras = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    fecha_es_limpia = fecha_es.lower().replace('.', '')
    for mes_es, mes_en in traduccion.items():
        if mes_es in fecha_es_limpia:
            # Usamos el diccionario de 3 letras para el reemplazo final
            return fecha_es_limpia.replace(mes_es, traduccion_3_letras[mes_es])
    return None

def obtener_proximos_partidos_malaga(driver):
    print("Buscando próximos partidos Málaga CF...")
    eventos = []
    try:
        driver.get("https://www.malagacf.com/partidos")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard"))
        )
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        partidos = soup.find_all('article', class_='MkFootballMatchCard')
    except Exception as e:
        print(f"ERROR: No se pudo cargar o encontrar la estructura inicial de próximos partidos Málaga: {e}")
        return []

    for partido in partidos:
        try:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            hora_raw = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else None
            fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else None
            estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'
            
            name = f"{equipo_local} vs {equipo_visitante}"

            if not hora_raw or not fecha_raw or hora_raw == '-- : --':
                print(f"Saltando partido (sin fecha/hora confirmada): {name}")
                continue 

            if ',' in fecha_raw:
                fecha_sin_dia = fecha_raw.split(', ')[1]
            else:
                fecha_sin_dia = fecha_raw
            
            fecha_traducida = traducir_fecha_malaga(fecha_sin_dia)
            if not fecha_traducida:
                print(f"Error al traducir fecha próximo Málaga: {fecha_raw}")
                continue

            fecha_normalizada = fecha_traducida.replace(" de ", " ")
            fecha_hora_str = f"{fecha_normalizada} {ANO_ACTUAL} {hora_raw.replace('.', '')}"
            fecha_hora_naive = None
            
            # Forzamos locale a inglés antes de parsear con %b
            current_locale = locale.getlocale(locale.LC_TIME)
            try:
                locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'C') # Fallback para entornos mínimos
                except locale.Error:
                    print("ADVERTENCIA: No se pudo forzar el locale a inglés. El parseo de fechas podría fallar.")

            try:
                formato = '%d %b %Y %I:%M %p'
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
            except ValueError:
                try:
                    formato = '%d %b %Y %H:%M'
                    fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
                except ValueError as e:
                    print(f"Error parseando fecha próximo Málaga: {name} | String: '{fecha_hora_str}' | Error: {e}")
                    continue
            finally:
                # Restauramos el locale original
                try: locale.setlocale(locale.LC_TIME, current_locale)
                except: pass # Ignorar si falla la restauración
            
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
        except Exception as e:
            print(f"Error procesando un partido próximo de Málaga: {e}")
            continue # Pasar al siguiente partido si uno falla
            
    print(f"Encontrados {len(eventos)} próximos partidos de Málaga CF.")
    return eventos

# --- FUNCIÓN 2: RESULTADOS MÁLAGA (CORREGIDA) ---
def obtener_resultados_malaga(driver):
    print("Buscando resultados Málaga CF...")
    eventos = []
    try:
        driver.get("https://www.malagacf.com/partidos?activeTab=results")
        # Esperamos solo a las tarjetas, no a los marcadores directamente
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard"))
        )
        print("Tarjetas de resultados de Málaga cargadas.")
    except Exception as e:
        print(f"ERROR: No se pudo cargar o encontrar la estructura inicial de resultados Málaga: {e}")
        return []
    
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    partidos = soup.find_all('article', class_='MkFootballMatchCard')

    for partido in partidos:
        try:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            name = f"{equipo_local} vs {equipo_visitante}"
            
            score_element = partido.find('div', class_='MkFootballMatchCard__result')
            if not score_element:
                print(f"Saltando resultado (sin elemento __result): {name}")
                continue 
            
            home_score_span = score_element.find('span', class_='MkFootballMatchCard__homeScore')
            away_score_span = score_element.find('span', class_='MkFootballMatchCard__awayScore')
            if not home_score_span or not away_score_span:
                print(f"Saltando resultado (sin span de marcador): {name}")
                continue 

            resultado_final = f"{home_score_span.text.strip()} - {away_score_span.text.strip()}"

            fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip()
            print(f"DEBUG MÁLAGA RESULTADOS: Fecha raw para '{name}' es: '{fecha_raw}'")
            
            hora_raw = "12:00" 
            fecha_hora_naive = None
            
            if ',' in fecha_raw:
                fecha_sin_dia = fecha_raw.split(', ')[1]
            else:
                fecha_sin_dia = fecha_raw

            fecha_traducida = traducir_fecha_malaga(fecha_sin_dia)
            if not fecha_traducida:
                print(f"Error FATAL al traducir fecha resultado Málaga: {name} en {fecha_raw}")
                continue

            fecha_normalizada = fecha_traducida.replace(" de ", " ")
            fecha_str_procesada = f"{fecha_normalizada} {ANO_ACTUAL} {hora_raw}"
            formato_esperado = '%d %b %Y %H:%M'

            # Forzamos locale a inglés antes de parsear con %b
            current_locale = locale.getlocale(locale.LC_TIME)
            try:
                locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, 'C') # Fallback
                except locale.Error:
                     print("ADVERTENCIA: No se pudo forzar el locale a inglés. El parseo de fechas podría fallar.")

            try:
                fecha_hora_naive = dt.datetime.strptime(fecha_str_procesada, formato_esperado)
            except ValueError as e:
                print(f"Error FATAL al parsear fecha resultado Málaga: {name} | String: '{fecha_str_procesada}' | Error: {e}")
                continue
            finally:
                 # Restauramos el locale original
                try: locale.setlocale(locale.LC_TIME, current_locale)
                except: pass
            
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
                "resultado": resultado_final
            })
        except Exception as e:
             print(f"Error procesando un resultado de Málaga: {e}")
             continue # Pasar al siguiente resultado si uno falla

    print(f"Encontrados {len(eventos)} resultados de Málaga CF.")
    return eventos


# --- FUNCIÓN 3: PRÓXIMOS UNICAJA (CORREGIDA) ---
def obtener_proximos_partidos_unicaja(driver):
    print("Buscando próximos partidos Unicaja...")
    eventos = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")

        # --- Lógica de cookies más flexible ---
        try:
            iframe_id = "CybotCookiebotDialogBody"
            cookie_button_id = "CybotCookiebotDialogBodyButtonAccept"
            
            print(f"Intentando aceptar cookies (espera máx 10 seg)...")
            WebDriverWait(driver, 10).until( # Aumentado a 10 segundos
                EC.frame_to_be_available_and_switch_to_it((By.ID, iframe_id))
            )
            
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, cookie_button_id))
            )
            cookie_button.click()
            print("Cookies aceptadas.")
            driver.switch_to.default_content()
            time.sleep(random.uniform(1.0, 2.0))
            
        except Exception as e:
            print(f"AVISO: No se aceptaron cookies (banner no encontrado o error): {e}")
            try: driver.switch_to.default_content()
            except: pass
        # --- FIN LÓGICA DE COOKIES ---

        # --- Comprobamos si la página cargó el contenido ---
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.partido"))
            )
            print("Contenido principal de Unicaja cargado.")
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            partidos = soup.find_all('div', class_='partido')
        except Exception as e:
            print(f"ERROR: La página de Unicaja no cargó el contenido esperado (div.partido) tras {10} seg. Posible bloqueo anti-bot.")
            print(f"Error detallado: {e}")
            return [] 
        # --- FIN DE LA COMPROBACIÓN ---
    except Exception as e:
        print(f"ERROR GRAVE al cargar la página de Unicaja (próximos): {e}")
        return []

    for partido in partidos:
        try:
            if partido.find('div', class_='marcador_local'):
                continue
                
            equipo_local = partido.find('span', class_='team_name_local').text.strip()
            equipo_visitante = partido.find('span', class_='team_name_visitante').text.strip()
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_raw = partido.find('span', class_='fecha').text.strip() 
            hora_raw = partido.find('span', class_='hora').text.strip()   
            
            if not fecha_raw or not hora_raw or 'falta' in hora_raw.lower():
                print(f"Saltando próximo Unicaja (sin fecha/hora confirmada): {name}")
                continue 

            try:
                hora_limpia = hora_raw.split(' ')[0] 
                fecha_hora_str = f"{fecha_raw} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
                fecha_hora_local = TZ_MADRID.localize(fecha_hora_naive)
                fecha_hora_inicio = fecha_hora_local.isoformat()
                fecha_hora_fin = (fecha_hora_local + dt.timedelta(hours=2)).isoformat()
            except ValueError as e:
                print(f"Error procesando fecha próximo Unicaja: {name} en {fecha_hora_str}")
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
        except Exception as e:
            print(f"Error procesando un partido próximo de Unicaja: {e}")
            continue

    print(f"Encontrados {len(eventos)} próximos partidos de Unicaja.")
    return eventos

# --- FUNCIÓN 4: RESULTADOS UNICAJA (CORREGIDA) ---
def obtener_resultados_unicaja(driver):
    print("Buscando resultados Unicaja...")
    eventos = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")

        # --- Lógica de cookies más flexible ---
        try:
            iframe_id = "CybotCookiebotDialogBody"
            cookie_button_id = "CybotCookiebotDialogBodyButtonAccept"
            
            print(f"Intentando aceptar cookies (espera máx 10 seg)...")
            WebDriverWait(driver, 10).until( # Aumentado a 10 segundos
                EC.frame_to_be_available_and_switch_to_it((By.ID, iframe_id))
            )
            
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.ID, cookie_button_id))
            )
            cookie_button.click()
            print("Cookies aceptadas.")
            driver.switch_to.default_content()
            time.sleep(random.uniform(1.0, 2.0))
            
        except Exception as e:
            print(f"AVISO: No se aceptaron cookies (banner no encontrado o error): {e}")
            try: driver.switch_to.default_content()
            except: pass
        # --- FIN LÓGICA DE COOKIES ---

        # --- Comprobamos si la página cargó el contenido ---
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.partido"))
            )
            print("Contenido principal de Unicaja cargado.")
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            partidos = soup.find_all('div', class_='partido')
        except Exception as e:
            print(f"ERROR: La página de Unicaja no cargó el contenido esperado (div.partido) tras {10} seg. Posible bloqueo anti-bot.")
            print(f"Error detallado: {e}")
            return [] 
        # --- FIN DE LA COMPROBACIÓN ---
    except Exception as e:
        print(f"ERROR GRAVE al cargar la página de Unicaja (resultados): {e}")
        return []

    for partido in partidos:
        try:
            resultado_local_raw = partido.find('div', class_='marcador_local')
            resultado_visitante_raw = partido.find('div', class_='marcador_visitante')
            
            if not resultado_local_raw or not resultado_visitante_raw:
                continue # No es un resultado, es un partido futuro
                
            resultado_final = f"{resultado_local_raw.text.strip()} - {resultado_visitante_raw.text.strip()}"
            
            equipo_local = partido.find('span', class_='team_name_local').text.strip()
            equipo_visitante = partido.find('span', class_='team_name_visitante').text.strip()
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_raw = partido.find('span', class_='fecha').text.strip() 
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
                "resultado": resultado_final
            })
        except Exception as e:
            print(f"Error procesando un resultado de Unicaja: {e}")
            continue
        
    print(f"Encontrados {len(eventos)} resultados de Unicaja.")
    return eventos


# --- FUNCIÓN GENERAR ICS (Sin cambios significativos) ---
def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    cal = Calendar()
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    print(f"Generando {len(lista_partidos)} eventos totales (partidos y resultados) para {nombre_archivo}...")

    eventos_validos = 0
    for partido in lista_partidos:
        try: # Añadido try/except por si algún dato del partido es inválido
            evento = Event()
            
            titulo = partido['name']
            if 'resultado' in partido and partido['resultado']:
                titulo = f"{partido['name']} ({partido['resultado']})"
            
            # Comprobar si las fechas son strings antes de parsear
            if not isinstance(partido.get('fecha_hora_inicio'), str) or not isinstance(partido.get('fecha_hora_fin'), str):
                print(f"ADVERTENCIA: Saltando evento con fechas inválidas: {titulo}")
                continue

            dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
            dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

            evento.add('summary', titulo) 
            evento.add('dtstart', dt_inicio)
            evento.add('dtend', dt_fin)
            evento.add('dtstamp', datetime.now(tz=pytz.utc))
            evento.add('location', partido.get('estadio', 'Lugar no especificado')) # Usar .get() por seguridad
            evento.add('description', partido.get('descripcion', '')) # Usar .get() por seguridad
            
            uid = f"{partido['fecha_hora_inicio']}-{partido['name'].replace(' ', '')}@sportsmlg.com"
            evento.add('uid', uid)
            cal.add_component(evento)
            eventos_validos += 1
        except Exception as e:
            print(f"ERROR al generar evento para {partido.get('name', 'Partido Desconocido')}: {e}")
            continue

    if eventos_validos > 0:
        with open(nombre_archivo, 'wb') as f:
            f.write(cal.to_ical())
        print(f"¡Éxito! Archivo '{nombre_archivo}' generado con {eventos_validos} eventos.")
    else:
        print("No se generó ningún evento válido.")


# --- LÓGICA PRINCIPAL (Sin cambios significativos) ---
if __name__ == "__main__":
    
    options = Options()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080") # Tamaño de ventana más común
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
        
    driver = None
    
    try:
        # Intenta instalar/usar el driver
        try:
             driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        except Exception as driver_error:
             print(f"ERROR CRÍTICO al iniciar ChromeDriver: {driver_error}")
             # Intentar fallback si falla la instalación automática (requiere chromedriver en PATH)
             try:
                 print("Intentando usar ChromeDriver desde el PATH...")
                 driver = webdriver.Chrome(options=options)
             except Exception as fallback_error:
                 print(f"ERROR CRÍTICO: Falló también al usar ChromeDriver desde el PATH: {fallback_error}")
                 exit(1) # Salir si no se puede iniciar el driver

        # Aplicar stealth si el driver se inició correctamente
        if driver:
            stealth(driver,
                    languages=["en-US", "en"],
                    vendor="Google Inc.",
                    platform="Win32",
                    webgl_vendor="Intel Inc.",
                    renderer="Intel Iris OpenGL Engine",
                    fix_hairline=True,
                    )
            
            todos_los_eventos = []
            
            # --- Ejecutar scrapes ---
            try:
                todos_los_eventos.extend(obtener_proximos_partidos_malaga(driver))
            except Exception as e:
                print(f"ERROR GRAVE al scrapear próximos Málaga: {e}")

            try:
                todos_los_eventos.extend(obtener_resultados_malaga(driver))
            except Exception as e:
                print(f"ERROR GRAVE al scrapear resultados Málaga: {e}")
                
            try:
                todos_los_eventos.extend(obtener_proximos_partidos_unicaja(driver))
            except Exception as e:
                print(f"ERROR GRAVE al scrapear próximos Unicaja: {e}")

            try:
                todos_los_eventos.extend(obtener_resultados_unicaja(driver))
            except Exception as e:
                print(f"ERROR GRAVE al scrapear resultados Unicaja: {e}")
            
            # --- Generar ICS ---
            if todos_los_eventos and len(todos_los_eventos) > 0:
                print(f"Total de eventos encontrados: {len(todos_los_eventos)}")
                generar_archivo_ics(todos_los_eventos, "partidos.ics")
            else:
                print("No se encontró información de ningún partido o resultado para generar el ICS.")
        
    except Exception as e:
        print(f"Ha ocurrido un error general no recuperable: {e}")
    finally:
        # Asegurarse de cerrar el driver si existe
        if driver:
            try:
                driver.quit()
                print("Driver cerrado correctamente.")
            except Exception as quit_error:
                print(f"Error al cerrar el driver: {quit_error}")
