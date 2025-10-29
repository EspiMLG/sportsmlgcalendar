import os
import time
import datetime as dt
from datetime import datetime
import random
# No importamos locale
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

# --- ZONA HORARIA Y LÓGICA DE TEMPORADA ---
TZ_MADRID = pytz.timezone('Europe/Madrid') # Zona horaria correcta
ANO_ACTUAL = dt.datetime.now().year
MES_ACTUAL = dt.datetime.now().month

MES_INICIO_TEMPORADA = 8
ANO_INICIO_TEMPORADA = ANO_ACTUAL
if MES_ACTUAL < MES_INICIO_TEMPORADA:
    ANO_INICIO_TEMPORADA = ANO_ACTUAL - 1
FECHA_INICIO_TEMPORADA = dt.datetime(ANO_INICIO_TEMPORADA, MES_INICIO_TEMPORADA, 1)
print(f"INFO: Filtrando resultados de ambas webs anteriores al {FECHA_INICIO_TEMPORADA.strftime('%Y-%m-%d')}")
# --- FIN LÓGICA DE TEMPORADA ---

# --- FUNCIÓN DE AYUDA PARA ZONA HORARIA ---
def crear_fecha_correcta_madrid(fecha_hora_naive):
    """
    Toma un datetime 'naive' (sin zona) que representa la hora local de Madrid
    y lo convierte a un datetime con zona horaria correcta, manejando DST.
    """
    # NO USAMOS localize(naive, is_dst=None) porque falla en GitHub Actions
    # Método alternativo:
    # 1. Creamos la fecha como si fuera UTC
    fecha_utc = pytz.utc.localize(fecha_hora_naive)
    # 2. La convertimos a la zona horaria de Madrid
    fecha_madrid = fecha_utc.astimezone(TZ_MADRID)
    # 3. Pytz puede equivocarse en la conversión si la hora es ambigua
    # (ej. la 1:30 AM del día del cambio de hora).
    # Comprobamos si el offset resultante es el que debería ser.
    
    # Solución más simple y robusta:
    # Asumimos que la fecha naive ES la hora de Madrid.
    # Le quitamos la info de zona (si la tuviera) y la "forzamos" a Madrid
    fecha_sin_tz = fecha_hora_naive.replace(tzinfo=None)
    # Usamos localize() PERO le decimos que NO ES ambigua (is_dst=None falla)
    # La forma correcta es averiguar si DST está activo en esa fecha
    es_dst = bool(TZ_MADRID.dst(fecha_sin_tz))
    fecha_hora_con_tz = TZ_MADRID.localize(fecha_sin_tz, is_dst=es_dst)
    return fecha_hora_con_tz


# --- FUNCIÓN 1: PRÓXIMOS MÁLAGA ---
def traducir_fecha_malaga(fecha_es):
    traduccion_a_ingles_3 = {
        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug', 'sep': 'Sep', 'sept': 'Sep',
        'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    fecha_es_limpia = fecha_es.lower().replace('.', '').replace(' de ', ' ')
    partes = fecha_es_limpia.split(' ')
    if len(partes) < 2: return None
    dia = partes[0]
    mes_es = partes[1]
    if mes_es in traduccion_a_ingles_3:
        mes_en_3 = traduccion_a_ingles_3[mes_es]
        return f"{dia} {mes_en_3}"
    else: return None

def obtener_proximos_partidos_malaga(driver):
    print("Buscando próximos partidos Málaga CF (web oficial)...")
    eventos = []
    try:
        driver.get("https://www.malagacf.com/partidos")
        clicks_ver_mas = 0
        while clicks_ver_mas < 5:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.MkFootballMatchCard")))
                ver_mas_span = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.XPATH, "//span[contains(@class, 'sc-') and contains(text(), 'Ver más')]")))
                load_more_button = ver_mas_span.find_element(By.XPATH, "./ancestor::button")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(random.uniform(2.0, 3.5))
                clicks_ver_mas += 1
            except Exception: break
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        partidos = soup.find_all('article', class_='MkFootballMatchCard')
        print(f"Total de tarjetas (próximos Málaga) encontradas tras clics: {len(partidos)}")
    except Exception as e:
        print(f"ERROR: No se pudo cargar/encontrar estructura inicial próximos Málaga: {e}")
        return []

    partidos_procesados = 0
    for partido in partidos:
        try:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            hora_raw = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else None
            fecha_raw = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else None
            estadio = partido.find('div', class_='MkFootballMatchCard__venue').text.strip() if partido.find('div', class_='MkFootballMatchCard__venue') else 'Estadio Visitante'
            name = f"{equipo_local} vs {equipo_visitante}"

            hora_confirmada = True
            if not hora_raw or not fecha_raw: continue
            if hora_raw == '-- : --':
                hora_limpia = "03:00"; hora_confirmada = False
            else: hora_limpia = hora_raw.replace('.', '')

            if ',' in fecha_raw: fecha_sin_dia = fecha_raw.split(', ')[1]
            else: fecha_sin_dia = fecha_raw
            fecha_ingles_3_letras = traducir_fecha_malaga(fecha_sin_dia)
            if not fecha_ingles_3_letras: continue

            mes_partido_num = int(datetime.strptime(fecha_ingles_3_letras.split(' ')[1], '%b').strftime('%m'))
            ano_partido = ANO_ACTUAL
            if mes_partido_num < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL + 1
            elif mes_partido_num >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL - 1

            fecha_hora_str = f"{fecha_ingles_3_letras} {ano_partido} {hora_limpia}"
            fecha_hora_naive = None
            try:
                formato = '%d %b %Y %I:%M %p'
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
            except ValueError:
                try:
                    formato = '%d %b %Y %H:%M'
                    fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
                except ValueError as e: continue

            fecha_partido_dt_naive = dt.datetime(fecha_hora_naive.year, fecha_hora_naive.month, fecha_hora_naive.day)
            if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                continue

            # --- ¡CORRECCIÓN DE ZONA HORARIA! ---
            fecha_hora_con_tz = crear_fecha_correcta_madrid(fecha_hora_naive)
            # --- FIN CORRECCIÓN ---

            fecha_hora_inicio = fecha_hora_con_tz.isoformat()
            fecha_hora_fin = (fecha_hora_con_tz + dt.timedelta(hours=2)).isoformat()
            localidad = "local" if "Málaga CF" in equipo_local else "visitante"
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio
            descripcion = "Próximo partido Málaga CF"
            if not hora_confirmada: descripcion += " (Hora por confirmar)"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio, "fecha_hora_fin": fecha_hora_fin,
                "estadio": estadio_final, "name": name, "descripcion": descripcion
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando un partido próximo de Málaga: {e}")
            continue

    print(f"Procesados {partidos_procesados} próximos partidos de Málaga CF.")
    return eventos

# --- FUNCIÓN 2: RESULTADOS MÁLAGA (FLASHSCORE - CORREGIDA) ---
def obtener_resultados_malaga_flashscore(driver):
    print("Buscando resultados Málaga CF (Resultados.com)...")
    eventos = []
    url_flashscore = "https://www.flashscore.com/team/malaga/25tIqYiJ/results/"
    try:
        driver.get(url_flashscore)
        print(f"Página {driver.current_url} cargada.")
        try:
            cookie_button_id = "onetrust-accept-btn-handler"
            xpath_accept_text = "//button[contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'acepto') or contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'accept')]"
            try: cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            except: cookie_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xpath_accept_text)))
            driver.execute_script("arguments[0].click();", cookie_button)
            print("Cookies Resultados.com aceptadas (o intentado).")
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"AVISO: No se aceptaron cookies Resultados.com: {e}")

        clicks_ver_mas = 0
        while clicks_ver_mas < 10:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.event__match")))
                load_more_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.event__more")))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(random.uniform(2.5, 4.0))
                clicks_ver_mas += 1
            except Exception:
                break
        print(f"Clics 'Ver más' realizados: {clicks_ver_mas}")

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        partidos_flashscore = soup.select("div.event__match")
        print(f"Total de contenedores de resultados (Resultados.com) encontrados: {len(partidos_flashscore)}")

    except Exception as e:
        print(f"ERROR: No se pudo cargar/encontrar estructura inicial Resultados.com: {e}")
        return []

    partidos_procesados = 0
    competiciones_excluidas = ["club friendly", "amistosos de clubs", "world"]

    for partido in partidos_flashscore:
        try:
            competition_tag = partido.select_one("span.event__title--type")
            if competition_tag:
                competition_name = competition_tag.text.strip().lower()
                if any(excluded in competition_name for excluded in competiciones_excluidas):
                    continue
            
            home_team_tag = partido.select_one("div.event__participant--home")
            away_team_tag = partido.select_one("div.event__participant--away")
            if not home_team_tag or not away_team_tag: continue
            equipo_local = home_team_tag.text.strip()
            equipo_visitante = away_team_tag.text.strip()
            name = f"{equipo_local} vs {equipo_visitante}"

            home_score_tag = partido.select_one("span.event__score--home")
            away_score_tag = partido.select_one("span.event__score--away")
            if not home_score_tag or not away_score_tag or \
               not home_score_tag.text.strip().isdigit() or not away_score_tag.text.strip().isdigit():
                continue
            resultado_final = f"{home_score_tag.text.strip()} - {away_score_tag.text.strip()}"

            datetime_tag = partido.select_one("div.event__time")
            if not datetime_tag: continue
            datetime_text = datetime_tag.text.strip()

            partes_dt = datetime_text.split(' ')
            fecha_part = partes_dt[0].strip()
            hora_limpia = "12:00"
            if len(partes_dt) > 1 and ':' in partes_dt[1]:
                hora_limpia = partes_dt[1].strip()
            
            try:
                partes_fecha = fecha_part.split('.')
                dia_str = partes_fecha[0]
                mes_num_str = partes_fecha[1]
                mes_num = int(mes_num_str)

                ano_partido = ANO_ACTUAL
                if len(partes_fecha) >= 3 and len(partes_fecha[2].strip()) == 4:
                    ano_partido = int(partes_fecha[2].strip())
                else:
                    if MES_ACTUAL < MES_INICIO_TEMPORADA and mes_num >= MES_INICIO_TEMPORADA:
                        ano_partido = ANO_ACTUAL - 1
                    
                fecha_partido_dt_naive = dt.datetime(ano_partido, mes_num, int(dia_str))
                if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                    continue

                fecha_str_procesada = f"{dia_str}.{mes_num_str}.{ano_partido} {hora_limpia}"
                formato_esperado = '%d.%m.%Y %H:%M'

            except (IndexError, ValueError):
                 print(f"Error parseando fecha/hora Flashscore: {name} | Raw: '{datetime_text}'")
                 continue

            fecha_hora_naive = None
            try:
                fecha_hora_naive = dt.datetime.strptime(fecha_str_procesada, formato_esperado)
            except ValueError as e:
                print(f"Error strptime resultado Flashscore: {name} | String: '{fecha_str_procesada}' | Error: {e}")
                continue

            # --- ¡CORRECCIÓN DE ZONA HORARIA! ---
            fecha_hora_con_tz = crear_fecha_correcta_madrid(fecha_hora_naive)
            # --- FIN CORRECCIÓN ---

            fecha_hora_inicio = fecha_hora_con_tz.isoformat()
            fecha_hora_fin = (fecha_hora_con_tz + dt.timedelta(hours=2)).isoformat()

            localidad = "local" if equipo_local.lower() == "malaga" else ("visitante" if equipo_visitante.lower() == "malaga" else "neutral")
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else 'Estadio Visitante (Flashscore)'
            descripcion = f"Resultado: {resultado_final}"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio, "fecha_hora_fin": fecha_hora_fin,
                "estadio": estadio_final, "name": name, "descripcion": descripcion,
                "resultado": resultado_final
            })
            partidos_procesados += 1
        except Exception as e:
             print(f"Error procesando un resultado de Flashscore: {name if 'name' in locals() else 'Partido desconocido'} | Error: {e}")
             continue

    print(f"Procesados {partidos_procesados} resultados de Málaga CF (Resultados.com).")
    return eventos

# --- FUNCIÓN 3: PRÓXIMOS UNICAJA (CON HORA POR DEFECTO Y FILTRO TEMPORADA) ---
def obtener_proximos_partidos_unicaja(driver):
    print("Buscando próximos partidos Unicaja...")
    eventos = []; filas_partido_con_mes = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")
        try:
            cookie_button_id = "aceptocookies"
            cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            driver.execute_script("arguments[0].click();", cookie_button)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception: pass

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.fila.fila_interior")))
            html = driver.page_source; soup = BeautifulSoup(html, 'html.parser')
            secciones_mes = soup.find_all('section', class_='contenedora_calendario')
            meses_es_a_num = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06','julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            for seccion in secciones_mes:
                h1_tag = seccion.find('h1', class_='titulo_principal'); mes_actual_str = h1_tag.text.strip().lower() if h1_tag else None
                if not mes_actual_str or mes_actual_str not in meses_es_a_num: continue
                mes_num = meses_es_a_num.get(mes_actual_str); filas = seccion.find_all('div', class_='fila_interior')
                for fila in filas: filas_partido_con_mes.append((mes_num, fila))
        except Exception as e: print(f"ERROR: No se pudo leer estructura Unicaja (próximos): {e}"); return []
    except Exception as e: print(f"ERROR GRAVE al cargar página Unicaja (próximos): {e}"); return []

    partidos_procesados = 0
    for mes_num, fila in filas_partido_con_mes:
        try:
            marcador_div = fila.find('div', class_='marcador'); es_resultado = False
            if marcador_div:
                resultado_link = marcador_div.find('a')
                if resultado_link and '|' in resultado_link.text: es_resultado = True
            if es_resultado: continue

            contenedores_equipo = fila.find_all('div', class_='contenedor_logo_equipo');
            if len(contenedores_equipo) < 2: continue
            equipo_local_div = contenedores_equipo[0].find('div', class_='nombre_equipo'); equipo_visitante_div = contenedores_equipo[1].find('div', class_='nombre_equipo')
            equipo_local = equipo_local_div.text.strip() if equipo_local_div and equipo_local_div.text.strip() else "Unicaja"
            equipo_visitante = equipo_visitante_div.text.strip() if equipo_visitante_div and equipo_visitante_div.text.strip() else "Unicaja"
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_div = fila.find('div', class_='celda prioridad-1 fecha');
            if not fecha_div: continue
            fecha_textos = [t.strip() for t in fecha_div.find_all(string=True) if t.strip()]
            if len(fecha_textos) < 1: continue
            try: dia_str = fecha_textos[0].split(' ')[1]
            except IndexError: continue

            hora_raw = fecha_textos[1] if len(fecha_textos) > 1 else None
            hora_limpia = "03:00"; hora_confirmada = False
            if hora_raw and ':' in hora_raw and 'falta' not in hora_raw.lower():
                 try: hora_limpia = hora_raw.split(' ')[0]; hora_confirmada = True
                 except: pass

            ano_partido = ANO_ACTUAL
            mes_num_int = int(mes_num)
            if mes_num_int < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA: ano_partido = ANO_ACTUAL + 1
            elif mes_num_int >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA: ano_partido = ANO_ACTUAL - 1
            
            try:
                fecha_partido_dt = dt.datetime(ano_partido, mes_num_int, int(dia_str))
                if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                    continue
            except ValueError: continue
            
            try:
                fecha_hora_str = f"{dia_str}.{mes_num}.{ano_partido} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
                
                # --- ¡CORRECCIÓN DE ZONA HORARIA! ---
                fecha_hora_con_tz = crear_fecha_correcta_madrid(fecha_hora_naive)
                # --- FIN CORRECCIÓN ---

                fecha_hora_inicio = fecha_hora_con_tz.isoformat()
                fecha_hora_fin = (fecha_hora_con_tz + dt.timedelta(hours=2)).isoformat()
            except ValueError as e: continue

            lugar_raw = fila.find('span', class_='pabellon'); lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón por confirmar"
            descripcion = "Próximo partido Unicaja";
            if not hora_confirmada: descripcion += " (Hora por confirmar)"

            eventos.append({"fecha_hora_inicio": fecha_hora_inicio, "fecha_hora_fin": fecha_hora_fin,"estadio": lugar, "name": name, "descripcion": descripcion})
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando una fila de próximo Unicaja: {e}")
            continue

    print(f"Procesados {partidos_procesados} próximos partidos de Unicaja.")
    return eventos

# --- FUNCIÓN 4: RESULTADOS UNICAJA (CON HORA ORIGINAL Y FILTRO) ---
def obtener_resultados_unicaja(driver):
    print("Buscando resultados Unicaja...")
    eventos = []; filas_partido_con_mes = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")
        try:
            cookie_button_id = "aceptocookies"
            cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            driver.execute_script("arguments[0].click();", cookie_button)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception: pass

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.fila.fila_interior")))
            html = driver.page_source; soup = BeautifulSoup(html, 'html.parser')
            secciones_mes = soup.find_all('section', class_='contenedora_calendario')
            meses_es_a_num = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06','julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
            for seccion in secciones_mes:
                h1_tag = seccion.find('h1', class_='titulo_principal'); mes_actual_str = h1_tag.text.strip().lower() if h1_tag else None
                if not mes_actual_str or mes_actual_str not in meses_es_a_num: continue
                mes_num = meses_es_a_num.get(mes_actual_str); filas = seccion.find_all('div', class_='fila_interior')
                for fila in filas: filas_partido_con_mes.append((mes_num, fila))
        except Exception as e: print(f"ERROR: No se pudo leer estructura Unicaja (resultados): {e}"); return []
    except Exception as e: print(f"ERROR GRAVE al cargar página Unicaja (resultados): {e}"); return []

    partidos_procesados = 0
    for mes_num, fila in filas_partido_con_mes:
        try:
            marcador_div = fila.find('div', class_='marcador'); es_resultado = False; resultado_final = "N/A"
            if marcador_div:
                resultado_link = marcador_div.find('a')
                if resultado_link and '|' in resultado_link.text:
                    es_resultado = True
                    try: marcador_partes = resultado_link.text.split('|'); resultado_final = f"{marcador_partes[0].strip()} - {marcador_partes[1].strip()}"
                    except: pass
            if not es_resultado: continue

            contenedores_equipo = fila.find_all('div', class_='contenedor_logo_equipo');
            if len(contenedores_equipo) < 2: continue
            equipo_local_div = contenedores_equipo[0].find('div', class_='nombre_equipo'); equipo_visitante_div = contenedores_equipo[1].find('div', class_='nombre_equipo')
            equipo_local = equipo_local_div.text.strip() if equipo_local_div and equipo_local_div.text.strip() else "Unicaja"
            equipo_visitante = equipo_visitante_div.text.strip() if equipo_visitante_div and equipo_visitante_div.text.strip() else "Unicaja"
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_div = fila.find('div', class_='celda prioridad-1 fecha');
            if not fecha_div: continue
            fecha_textos = [t.strip() for t in fecha_div.find_all(string=True) if t.strip()]
            if len(fecha_textos) < 1: continue
            try: dia_str = fecha_textos[0].split(' ')[1]
            except IndexError: continue

            hora_raw = fecha_textos[1] if len(fecha_textos) > 1 else None; hora_limpia = "12:00" # Fallback
            if hora_raw and ':' in hora_raw and 'falta' not in hora_raw.lower():
                 try: hora_limpia = hora_raw.split(' ')[0]
                 except: pass

            ano_partido = ANO_ACTUAL
            mes_num_int = int(mes_num)
            if mes_num_int < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA: ano_partido = ANO_ACTUAL + 1
            elif mes_num_int >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA: ano_partido = ANO_ACTUAL - 1
            
            try:
                fecha_partido_dt = dt.datetime(ano_partido, mes_num_int, int(dia_str))
                if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                    continue
            except ValueError: continue
            
            fecha_raw_completa = f"{dia_str}.{mes_num}.{ano_partido}"

            try:
                fecha_hora_str = f"{fecha_raw_completa} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')
                
                # --- ¡CORRECCIÓN DE ZONA HORARIA! ---
                fecha_hora_con_tz = crear_fecha_correcta_madrid(fecha_hora_naive)
                # --- FIN CORRECCIÓN ---

                fecha_hora_inicio = fecha_hora_con_tz.isoformat()
                fecha_hora_fin = (fecha_hora_con_tz + dt.timedelta(hours=2)).isoformat()
            except ValueError as e: continue

            lugar_raw = fila.find('span', class_='pabellon'); lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón (Resultado)"
            descripcion = f"Resultado Unicaja: {resultado_final}"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio, "fecha_hora_fin": fecha_hora_fin,
                "estadio": lugar, "name": name, "descripcion": descripcion, "resultado": resultado_final
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando una fila de resultado Unicaja: {e}")
            continue

    print(f"Procesados {partidos_procesados} resultados de Unicaja.")
    return eventos


# --- FUNCIÓN GENERAR ICS (Actualizada descripción y UID base) ---
def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    cal = Calendar(); cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES'); cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN'); cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')
    print(f"Generando {len(lista_partidos)} eventos totales para {nombre_archivo}...")
    eventos_validos = 0; ids_unicos = set()
    for partido in lista_partidos:
        try:
            evento = Event(); titulo = partido['name']; descripcion = partido.get('descripcion', '')
            if 'resultado' in partido and partido['resultado'] and partido['resultado'] != "N/A":
                titulo = f"{partido['name']} ({partido['resultado']})"
                if "Próximo partido" in descripcion: descripcion = descripcion.replace("Próximo partido", "Resultado")
            if not isinstance(partido.get('fecha_hora_inicio'), str) or not isinstance(partido.get('fecha_hora_fin'), str): continue
            
            dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
            dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

            fecha_inicio_str = dt_inicio.strftime('%Y%m%d'); uid_base = f"{fecha_inicio_str}-{partido['name'].replace(' ', '')}"
            uid = f"{uid_base}@sportsmlg.com"
            if uid_base in ids_unicos: continue
            ids_unicos.add(uid_base)
            
            evento.add('summary', titulo)
            evento.add('dtstart', dt_inicio) # dt_inicio ya tiene la info de timezone
            evento.add('dtend', dt_fin)       # dt_fin ya tiene la info de timezone
            evento.add('dtstamp', datetime.now(pytz.utc)) # Usamos UTC para dtstamp
            evento.add('location', partido.get('estadio', 'Lugar no especificado'))
            evento.add('description', descripcion); evento.add('uid', uid); cal.add_component(evento)
            eventos_validos += 1
        except Exception as e: print(f"ERROR al generar evento para {partido.get('name', 'Partido Desconocido')}: {e}"); continue
    if eventos_validos > 0:
        with open(nombre_archivo, 'wb') as f: f.write(cal.to_ical())
        print(f"¡ÉXITO! Archivo '{nombre_archivo}' generado con {eventos_validos} eventos.")
    else:
        print("No se generó ningún evento válido. Creando archivo .ics vacío.")
        cal = Calendar(); cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES'); cal.add('version', '2.0')
        with open(nombre_archivo, 'wb') as f: f.write(cal.to_ical())

# --- LÓGICA PRINCIPAL (Llama a función Flashscore para resultados Málaga) ---
if __name__ == "__main__":
    options = Options(); options.headless = True
    options.add_argument("--disable-gpu"); options.add_argument("--no-sandbox"); options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled"); options.add_experimental_option("excludeSwitches", ["enable-automation"]); options.add_experimental_option('useAutomationExtension', False)
    driver = None
    try:
        try:
             driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options); print("ChromeDriver iniciado.")
        except Exception as driver_error:
             print(f"ERROR CRÍTICO ChromeDriver: {driver_error}")
             try: print("Intentando fallback ChromeDriver..."); driver = webdriver.Chrome(options=options); print("Fallback ChromeDriver OK.")
             except Exception as fallback_error: print(f"ERROR CRÍTICO Fallback: {fallback_error}"); driver = None
        if driver:
            try:
                stealth(driver, languages=["en-US", "en"], vendor="Google Inc.", platform="Win32", webgl_vendor="Intel Inc.", renderer="Intel Iris OpenGL Engine", fix_hairline=True); print("Stealth aplicado.")
            except Exception as stealth_error: print(f"ADVERTENCIA Stealth: {stealth_error}")
            todos_los_eventos = []
            print("\n--- Iniciando scrape de Málaga ---")
            try: todos_los_eventos.extend(obtener_proximos_partidos_malaga(driver))
            except Exception as e: print(f"ERROR GRAVE scrape próximos Málaga: {e}")
            try: todos_los_eventos.extend(obtener_resultados_malaga_flashscore(driver)) # <--- LLAMA A FLASHSCORE
            except Exception as e: print(f"ERROR GRAVE scrape resultados Málaga (Flashscore): {e}")
            print("--- Fin scrape de Málaga ---")
            print("\n--- Iniciando scrape de Unicaja ---")
            try: todos_los_eventos.extend(obtener_proximos_partidos_unicaja(driver))
            except Exception as e: print(f"ERROR GRAVE scrape próximos Unicaja: {e}")
            try: todos_los_eventos.extend(obtener_resultados_unicaja(driver))
            except Exception as e: print(f"ERROR GRAVE scrape resultados Unicaja: {e}")
            print("--- Fin scrape de Unicaja ---")
            print("\n--- Iniciando generación de ICS ---")
            if todos_los_eventos: print(f"Total de eventos encontrados: {len(todos_los_eventos)}")
            else: print("No se encontró info para generar el ICS.")
            generar_archivo_ics(todos_los_eventos, "partidos.ics")
            print("--- Fin generación de ICS ---")
    except Exception as e: print(f"Error general no recuperable: {e}")
    finally:
        if driver:
            try: driver.quit(); print("Driver cerrado.")
            except Exception as quit_error: print(f"Error al cerrar driver: {quit_error}")
        else: print("Driver no iniciado.")
