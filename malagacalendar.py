import os
import re
import time
import random
import datetime as dt
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

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
ANO_ACTUAL = dt.datetime.now().year
MES_ACTUAL = dt.datetime.now().month

MES_INICIO_TEMPORADA = 8
ANO_INICIO_TEMPORADA = ANO_ACTUAL
if MES_ACTUAL < MES_INICIO_TEMPORADA:
    ANO_INICIO_TEMPORADA = ANO_ACTUAL - 1
FECHA_INICIO_TEMPORADA = dt.datetime(ANO_INICIO_TEMPORADA, MES_INICIO_TEMPORADA, 1)
print(f"INFO: Filtrando resultados de ambas webs anteriores al {FECHA_INICIO_TEMPORADA.strftime('%Y-%m-%d')}")
# --- FIN LÓGICA DE TEMPORADA ---


# --- FUNCIÓN 1: PRÓXIMOS MÁLAGA (BLINDADA CON REGEX) ---
def traducir_fecha_malaga_a_numeros(fecha_es):
    """
    Soporta formatos con o sin día de la semana y en ES/EN:
    'sáb 7 de nov', 'mié, 21 de abr', '8 nov', 'Nov 8', 'dom 3 de ene'
    """
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
    texto = fecha_es.lower().replace('.', '').replace(',', ' ').strip()

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


def obtener_proximos_partidos_malaga(driver):
    print("Buscando próximos partidos Málaga CF (web oficial)...")
    eventos = []
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
            
            div_time = partido.find('div', class_='MkFootballMatchCard__time')
            div_date = partido.find('div', class_='MkFootballMatchCard__date')
            div_venue = partido.find('div', class_='MkFootballMatchCard__venue')

            hora_raw = div_time.text.strip() if div_time else None
            fecha_raw = div_date.text.strip() if div_date else None
            estadio = div_venue.text.strip() if div_venue else 'Estadio Visitante'
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
                formato = '%d.%m.%Y %H:%M'
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, formato)
            except ValueError as e:
                print(f"Error parseando fecha Málaga Próximos: {fecha_hora_str} | Error: {e}")
                continue

            fecha_partido_dt_naive = dt.datetime(fecha_hora_naive.year, fecha_hora_naive.month, fecha_hora_naive.day)
            if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                continue

            # Gestión de Zona Horaria según entorno (GitHub Actions vs Local)
            if os.environ.get('GITHUB_ACTIONS') == 'true':
                if not hora_confirmada:
                    # Si la hora no está confirmada (03:00), la fijamos en hora Madrid para que no salte al día anterior
                    fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                    fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                else:
                    fecha_hora_inicio_utc = fecha_hora_naive.replace(tzinfo=dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_inicio_utc + dt.timedelta(hours=2)
            else:
                fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)

            fecha_hora_inicio = fecha_hora_inicio_utc.isoformat()
            fecha_hora_fin = fecha_hora_fin_utc.isoformat()

            localidad = "local" if "Málaga" in equipo_local or "Malaga" in equipo_local else "visitante"
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else estadio
            descripcion = "Próximo partido Málaga CF"
            if not hora_confirmada:
                descripcion += " (Hora por confirmar)"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "estadio": estadio_final,
                "name": name,
                "descripcion": descripcion
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando un partido próximo de Málaga: {e}")
            continue

    print(f"Procesados {partidos_procesados} próximos partidos de Málaga CF.")
    return eventos


# --- FUNCIÓN 2: RESULTADOS MÁLAGA (FLASHSCORE - SELECTORES ACTUALIZADOS) ---
def obtener_resultados_malaga_flashscore(driver):
    print("Buscando resultados Málaga CF (Flashscore)...")
    eventos = []
    url_flashscore = "https://www.flashscore.com/team/malaga/25tIqYiJ/results/"
    try:
        driver.get(url_flashscore)
        print(f"Página {driver.current_url} cargada.")
        try:
            cookie_button_id = "onetrust-accept-btn-handler"
            xpath_accept_text = "//button[contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'acepto') or contains(translate(., 'ACDEGIKLMNOPRSTUVZ', 'acdegiklmnoprstuvz'), 'accept')]"
            try:
                cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            except Exception:
                cookie_button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, xpath_accept_text)))
            driver.execute_script("arguments[0].click();", cookie_button)
            print("Cookies Flashscore aceptadas (o intentado).")
            time.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            print(f"AVISO: No se aceptaron cookies Flashscore: {e}")

        clicks_ver_mas = 0
        while clicks_ver_mas < 5:
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.event__match")))
                load_more_button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.event__more, [data-testid='wcl-buttonLink']"))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_more_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", load_more_button)
                time.sleep(random.uniform(2.0, 3.5))
                clicks_ver_mas += 1
            except Exception:
                break
        print(f"Clics 'Ver más' realizados: {clicks_ver_mas}")

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        partidos_flashscore = soup.select("div.event__match")
        print(f"Total de contenedores de resultados (Flashscore) encontrados: {len(partidos_flashscore)}")

    except Exception as e:
        print(f"ERROR: No se pudo cargar/encontrar estructura inicial Flashscore: {e}")
        return []

    partidos_procesados = 0
    competiciones_excluidas = ["club friendly", "amistosos de clubs", "world"]

    for partido in partidos_flashscore:
        try:
            competition_tag = partido.select_one("span.event__title--type, .event__titleBox")
            if competition_tag:
                competition_name = competition_tag.get_text(" ", strip=True).lower()
                if any(excluded in competition_name for excluded in competiciones_excluidas):
                    continue

            # Selectores compatibles con todas las versiones del DOM de Flashscore (2024-2026)
            home_team_tag = partido.select_one(
                ".event__participant--home, .event__homeParticipant [data-testid='wcl-scores-simpleText-01'], .event__homeParticipant"
            )
            away_team_tag = partido.select_one(
                ".event__participant--away, .event__awayParticipant [data-testid='wcl-scores-simpleText-01'], .event__awayParticipant"
            )
            if not home_team_tag or not away_team_tag:
                continue

            equipo_local = home_team_tag.get_text(" ", strip=True)
            equipo_visitante = away_team_tag.get_text(" ", strip=True)
            # Normalizar el nombre a "Málaga CF" para que el UID coincida con el de próximos partidos
            if equipo_local.lower() in ["malaga", "málaga"]:
                equipo_local = "Málaga CF"
            if equipo_visitante.lower() in ["malaga", "málaga"]:
                equipo_visitante = "Málaga CF"
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

            # Selector compatible con la estructura antigua y la nueva de Flashscore
            datetime_tag = partido.select_one(
                "[data-testid='wcl-stageTime'], "
                ".event__stageTime, "
                ".event__time"
            )

            if not datetime_tag:
                print("AVISO: No se encontró el elemento de fecha/hora.")
                print("HTML del partido:", partido.prettify()[:2000])
                continue

            #FOR DEBUG PURPOSES:
            datetime_text = datetime_tag.get_text(" ", strip=True)
            #print(f"DEBUG Flashscore - Fecha/hora encontrada: {datetime_text}")

            # Extraer fecha DD.MM.(YYYY) y hora HH:MM mediante Regex (ignora textos como "AET", "Pen", "FRO")
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
                    # Si estamos en Nov 2026 y aparece un resultado de Dic sin año, es de Dic 2025
                    ano_partido = ANO_ACTUAL - 1

            fecha_partido_dt_naive = dt.datetime(ano_partido, mes_num, int(dia_str))
            if fecha_partido_dt_naive < FECHA_INICIO_TEMPORADA:
                continue

            fecha_str_procesada = f"{dia_str}.{mes_num_str}.{ano_partido} {hora_limpia}"
            fecha_hora_naive = dt.datetime.strptime(fecha_str_procesada, '%d.%m.%Y %H:%M')

            if os.environ.get('GITHUB_ACTIONS') == 'true':
                fecha_hora_inicio_utc = fecha_hora_naive.replace(tzinfo=dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_inicio_utc + dt.timedelta(hours=2)
            else:
                fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)

            fecha_hora_inicio = fecha_hora_inicio_utc.isoformat()
            fecha_hora_fin = fecha_hora_fin_utc.isoformat()

            localidad = "local" if "málaga" in equipo_local.lower() or "malaga" in equipo_local.lower() else "visitante"
            estadio_final = 'Estadio La Rosaleda' if localidad == 'local' else 'Estadio Visitante (Flashscore)'
            descripcion = f"Resultado: {resultado_final}"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "estadio": estadio_final,
                "name": name,
                "descripcion": descripcion,
                "resultado": resultado_final
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando un resultado de Flashscore: {e}")
            continue
    if partidos_flashscore and partidos_procesados == 0:
        print(
            "ALERTA: Se encontraron partidos, "
            "pero ninguno pudo convertirse en resultado."
        )
    print(f"Procesados {partidos_procesados} resultados de Málaga CF (Flashscore).")
    return eventos


# --- FUNCIÓN 3: PRÓXIMOS UNICAJA ---
def obtener_proximos_partidos_unicaja(driver):
    print("Buscando próximos partidos Unicaja...")
    eventos = []
    filas_partido_con_mes = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")
        try:
            cookie_button_id = "aceptocookies"
            cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            driver.execute_script("arguments[0].click();", cookie_button)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.fila.fila_interior")))
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            secciones_mes = soup.find_all('section', class_='contenedora_calendario')
            meses_es_a_num = {
                'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
            }
            for seccion in secciones_mes:
                h1_tag = seccion.find('h1', class_='titulo_principal')
                mes_actual_str = h1_tag.text.strip().lower() if h1_tag else None
                if not mes_actual_str or mes_actual_str not in meses_es_a_num:
                    continue
                mes_num = meses_es_a_num.get(mes_actual_str)
                filas = seccion.find_all('div', class_='fila_interior')
                for fila in filas:
                    filas_partido_con_mes.append((mes_num, fila))
        except Exception as e:
            print(f"ERROR: No se pudo leer estructura Unicaja (próximos): {e}")
            return []
    except Exception as e:
        print(f"ERROR GRAVE al cargar página Unicaja (próximos): {e}")
        return []

    partidos_procesados = 0
    for mes_num, fila in filas_partido_con_mes:
        try:
            marcador_div = fila.find('div', class_='marcador')
            es_resultado = False
            if marcador_div:
                resultado_link = marcador_div.find('a')
                if resultado_link and '|' in resultado_link.text:
                    es_resultado = True
            if es_resultado:
                continue

            contenedores_equipo = fila.find_all('div', class_='contenedor_logo_equipo')
            if len(contenedores_equipo) < 2:
                continue
            equipo_local_div = contenedores_equipo[0].find('div', class_='nombre_equipo')
            equipo_visitante_div = contenedores_equipo[1].find('div', class_='nombre_equipo')
            equipo_local = equipo_local_div.text.strip() if equipo_local_div and equipo_local_div.text.strip() else "Unicaja"
            equipo_visitante = equipo_visitante_div.text.strip() if equipo_visitante_div and equipo_visitante_div.text.strip() else "Unicaja"
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_div = fila.find('div', class_='celda prioridad-1 fecha')
            if not fecha_div:
                continue
            fecha_textos = [t.strip() for t in fecha_div.find_all(string=True) if t.strip()]
            if len(fecha_textos) < 1:
                continue
            try:
                dia_str = fecha_textos[0].split(' ')[1]
            except IndexError:
                continue

            hora_raw = fecha_textos[1] if len(fecha_textos) > 1 else None
            hora_limpia = "03:00"
            hora_confirmada = False
            if hora_raw and ':' in hora_raw and 'falta' not in hora_raw.lower():
                try:
                    hora_limpia = hora_raw.split(' ')[0]
                    hora_confirmada = True
                except Exception:
                    pass

            ano_partido = ANO_ACTUAL
            mes_num_int = int(mes_num)
            if mes_num_int < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL + 1
            elif mes_num_int >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL - 1

            try:
                fecha_partido_dt = dt.datetime(ano_partido, mes_num_int, int(dia_str))
                if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                    continue
            except ValueError:
                continue

            try:
                fecha_hora_str = f"{dia_str}.{mes_num}.{ano_partido} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')

                fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)
                fecha_hora_inicio = fecha_hora_inicio_utc.isoformat()
                fecha_hora_fin = fecha_hora_fin_utc.isoformat()
            except ValueError:
                continue

            lugar_raw = fila.find('span', class_='pabellon')
            lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón por confirmar"
            descripcion = "Próximo partido Unicaja"
            if not hora_confirmada:
                descripcion += " (Hora por confirmar)"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "estadio": lugar,
                "name": name,
                "descripcion": descripcion
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando una fila de próximo Unicaja: {e}")
            continue

    print(f"Procesados {partidos_procesados} próximos partidos de Unicaja.")
    return eventos


# --- FUNCIÓN 4: RESULTADOS UNICAJA ---
def obtener_resultados_unicaja(driver):
    print("Buscando resultados Unicaja...")
    eventos = []
    filas_partido_con_mes = []
    try:
        driver.get("https://www.unicajabaloncesto.com/calendario")
        try:
            cookie_button_id = "aceptocookies"
            cookie_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.ID, cookie_button_id)))
            driver.execute_script("arguments[0].click();", cookie_button)
            time.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.fila.fila_interior")))
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            secciones_mes = soup.find_all('section', class_='contenedora_calendario')
            meses_es_a_num = {
                'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
            }
            for seccion in secciones_mes:
                h1_tag = seccion.find('h1', class_='titulo_principal')
                mes_actual_str = h1_tag.text.strip().lower() if h1_tag else None
                if not mes_actual_str or mes_actual_str not in meses_es_a_num:
                    continue
                mes_num = meses_es_a_num.get(mes_actual_str)
                filas = seccion.find_all('div', class_='fila_interior')
                for fila in filas:
                    filas_partido_con_mes.append((mes_num, fila))
        except Exception as e:
            print(f"ERROR: No se pudo leer estructura Unicaja (resultados): {e}")
            return []
    except Exception as e:
        print(f"ERROR GRAVE al cargar página Unicaja (resultados): {e}")
        return []

    partidos_procesados = 0
    for mes_num, fila in filas_partido_con_mes:
        try:
            marcador_div = fila.find('div', class_='marcador')
            es_resultado = False
            resultado_final = "N/A"
            if marcador_div:
                resultado_link = marcador_div.find('a')
                if resultado_link and '|' in resultado_link.text:
                    es_resultado = True
                    try:
                        marcador_partes = resultado_link.text.split('|')
                        resultado_final = f"{marcador_partes[0].strip()} - {marcador_partes[1].strip()}"
                    except Exception:
                        pass
            if not es_resultado:
                continue

            contenedores_equipo = fila.find_all('div', class_='contenedor_logo_equipo')
            if len(contenedores_equipo) < 2:
                continue
            equipo_local_div = contenedores_equipo[0].find('div', class_='nombre_equipo')
            equipo_visitante_div = contenedores_equipo[1].find('div', class_='nombre_equipo')
            equipo_local = equipo_local_div.text.strip() if equipo_local_div and equipo_local_div.text.strip() else "Unicaja"
            equipo_visitante = equipo_visitante_div.text.strip() if equipo_visitante_div and equipo_visitante_div.text.strip() else "Unicaja"
            name = f"{equipo_local} vs {equipo_visitante}"

            fecha_div = fila.find('div', class_='celda prioridad-1 fecha')
            if not fecha_div:
                continue
            fecha_textos = [t.strip() for t in fecha_div.find_all(string=True) if t.strip()]
            if len(fecha_textos) < 1:
                continue
            try:
                dia_str = fecha_textos[0].split(' ')[1]
            except IndexError:
                continue

            hora_raw = fecha_textos[1] if len(fecha_textos) > 1 else None
            hora_limpia = "12:00"
            if hora_raw and ':' in hora_raw and 'falta' not in hora_raw.lower():
                try:
                    hora_limpia = hora_raw.split(' ')[0]
                except Exception:
                    pass

            ano_partido = ANO_ACTUAL
            mes_num_int = int(mes_num)
            if mes_num_int < MES_INICIO_TEMPORADA and MES_ACTUAL >= MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL + 1
            elif mes_num_int >= MES_INICIO_TEMPORADA and MES_ACTUAL < MES_INICIO_TEMPORADA:
                ano_partido = ANO_ACTUAL - 1

            try:
                fecha_partido_dt = dt.datetime(ano_partido, mes_num_int, int(dia_str))
                if fecha_partido_dt < FECHA_INICIO_TEMPORADA:
                    continue
            except ValueError:
                continue

            fecha_raw_completa = f"{dia_str}.{mes_num}.{ano_partido}"

            try:
                fecha_hora_str = f"{fecha_raw_completa} {hora_limpia}"
                fecha_hora_naive = dt.datetime.strptime(fecha_hora_str, '%d.%m.%Y %H:%M')

                fecha_hora_inicio_local = fecha_hora_naive.replace(tzinfo=TZ_MADRID)
                fecha_hora_fin_local = fecha_hora_inicio_local + dt.timedelta(hours=2)
                fecha_hora_inicio_utc = fecha_hora_inicio_local.astimezone(dt.timezone.utc)
                fecha_hora_fin_utc = fecha_hora_fin_local.astimezone(dt.timezone.utc)
                fecha_hora_inicio = fecha_hora_inicio_utc.isoformat()
                fecha_hora_fin = fecha_hora_fin_utc.isoformat()
            except ValueError:
                continue

            lugar_raw = fila.find('span', class_='pabellon')
            lugar = lugar_raw.text.strip() if lugar_raw else "Pabellón (Resultado)"
            descripcion = f"Resultado Unicaja: {resultado_final}"

            eventos.append({
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "estadio": lugar,
                "name": name,
                "descripcion": descripcion,
                "resultado": resultado_final
            })
            partidos_procesados += 1
        except Exception as e:
            print(f"Error procesando una fila de resultado Unicaja: {e}")
            continue

    print(f"Procesados {partidos_procesados} resultados de Unicaja.")
    return eventos


# --- FUNCIÓN 5: GENERAR ICS CON PROTECCIÓN ANTI-BORRADO ---
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


def generar_archivo_ics(lista_partidos, nombre_archivo="partidos.ics"):
    eventos_previos = cargar_eventos_previos_ics(nombre_archivo)

    cal = Calendar()
    cal.add('prodid', '-//SportsMLGCalendar//espi.mlg//ES')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('X-WR-CALNAME', 'Calendario Málaga CF y Unicaja')
    cal.add('X-WR-TIMEZONE', 'Europe/Madrid')

    print(f"Procesando {len(lista_partidos)} eventos recién scrapeados para {nombre_archivo}...")
    nuevos_eventos_dict = {}

    # Ordenamos para que los eventos CON resultado tengan prioridad sobre los "Próximo partido"
    lista_ordenada = sorted(
        lista_partidos,
        key=lambda x: 0 if ('resultado' in x and x['resultado'] and x['resultado'] != "N/A") else 1
    )

    for partido in lista_ordenada:
        try:
            evento = Event()
            titulo = partido['name']
            descripcion = partido.get('descripcion', '')
            if 'resultado' in partido and partido['resultado'] and partido['resultado'] != "N/A":
                titulo = f"{partido['name']} ({partido['resultado']})"
                if "Próximo partido" in descripcion:
                    descripcion = descripcion.replace("Próximo partido", "Resultado")

            if not isinstance(partido.get('fecha_hora_inicio'), str) or not isinstance(partido.get('fecha_hora_fin'), str):
                continue

            dt_inicio = datetime.fromisoformat(partido['fecha_hora_inicio'])
            dt_fin = datetime.fromisoformat(partido['fecha_hora_fin'])

            # Usamos la fecha en hora de Madrid para construir el UID y evitar duplicados por salto de día UTC
            fecha_inicio_str = dt_inicio.astimezone(TZ_MADRID).strftime('%Y%m%d')
            uid_base = f"{fecha_inicio_str}-{partido['name'].replace(' ', '')}"
            uid = f"{uid_base}@sportsmlg.com"

            if uid in nuevos_eventos_dict:
                continue

            evento.add('summary', titulo)
            evento.add('dtstart', dt_inicio)
            evento.add('dtend', dt_fin)
            evento.add('dtstamp', datetime.now(dt.timezone.utc))
            evento.add('location', partido.get('estadio', 'Lugar no especificado'))
            evento.add('description', descripcion)
            evento.add('uid', uid)

            nuevos_eventos_dict[uid] = evento
        except Exception as e:
            print(f"ERROR al generar evento para {partido.get('name', 'Partido Desconocido')}: {e}")
            continue

    # Fusionar: mantener eventos previos que no hayan sido reemplazados en esta ejecución
    eventos_fusionados = dict(eventos_previos)
    eventos_fusionados.update(nuevos_eventos_dict)

    if len(eventos_fusionados) > 0:
        for uid, ev in eventos_fusionados.items():
            cal.add_component(ev)
        with open(nombre_archivo, 'wb') as f:
            f.write(cal.to_ical())
        print(f"¡ÉXITO! Archivo '{nombre_archivo}' guardado con {len(eventos_fusionados)} eventos ({len(nuevos_eventos_dict)} actualizados hoy).")
    else:
        print("ALERTA: No hay eventos nuevos ni previos. No se sobrescribe el archivo.")


# --- LÓGICA PRINCIPAL ---
if __name__ == "__main__":
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        try:
            # Selenium 4.10+ gestiona ChromeDriver automáticamente con Selenium Manager
            driver = webdriver.Chrome(options=options)
            print("ChromeDriver iniciado con Selenium Manager nativo.")
        except Exception as native_error:
            print(f"Aviso Selenium Manager nativo: {native_error}. Probando ChromeDriverManager...")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            print("ChromeDriver iniciado con webdriver_manager.")

        if driver:
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
                print("Stealth aplicado.")
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
                print(f"ERROR GRAVE scrape resultados Málaga (Flashscore): {e}")
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

            print("\n--- Iniciando generación de ICS ---")
            if todos_los_eventos:
                print(f"Total de eventos encontrados en esta ejecución: {len(todos_los_eventos)}")
            else:
                print("No se encontró info nueva en esta ejecución.")
            generar_archivo_ics(todos_los_eventos, "partidos.ics")
            print("--- Fin generación de ICS ---")
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
