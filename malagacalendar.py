import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Credenciales desde las variables de entorno
credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

# Credenciales de servicio para acceder a la API de Google Calendar
credentials = Credentials.from_service_account_info(
    json.loads(credentials_json),
    scopes=['https://www.googleapis.com/auth/calendar']
)

# Conectar con la API de Google Calendar
service = build('calendar', 'v3', credentials=credentials)

# ID del calendario donde añadir los eventos
calendar_id = '482b569e5fd8fd1c9d2d19b3e2d06b4587d8f3490af5cf17d7b2a289e0f4516f@group.calendar.google.com'

def obtener_proximos_partidos():
    options = Options()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        # Realizar la solicitud HTTP
        driver.get("https://www.malagacf.com/partidos")
        
        # Extraer el contenido de la página después de que el JavaScript se haya ejecutado
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        # Encontrar los elementos que contienen la información de los partidos
        partidos = soup.find_all('article', class_='MkFootballMatchCard')

        eventos = []
        for partido in partidos:
            equipos = partido.find_all('span', class_='MkFootballMatchCard__teamName')
            equipo_local = equipos[0].text.strip() if len(equipos) > 0 else 'Desconocido'
            equipo_visitante = equipos[1].text.strip() if len(equipos) > 1 else 'Desconocido'
            hora = partido.find('div', class_='MkFootballMatchCard__time').text.strip() if partido.find('div', class_='MkFootballMatchCard__time') else 'Desconocido'
            fecha = partido.find('div', class_='MkFootballMatchCard__date').text.strip() if partido.find('div', class_='MkFootballMatchCard__date') else 'Desconocido'
            
            if hora=='-- : --' : hora = '12 : 00'

            fecha_hora_inicio = f"{fecha}T{hora}:00"
            fecha_hora_fin = f"{fecha}T{int(hora.split(':')[0]) + 2:02}:00:00"  # Asumimos 2 horas de duración

            localidad = "local" if "Málaga CF" in equipo_local else "visitante"
            descripcion = "Próximo partido del Málaga CF" 

            eventos.append({
                "oponente": equipo_visitante if "Málaga CF" in equipo_local else equipo_local,
                "fecha_hora_inicio": fecha_hora_inicio,
                "fecha_hora_fin": fecha_hora_fin,
                "localidad": localidad,
                "descripcion": descripcion
            })

        return eventos
    except Exception as e:
        print(f"No se pudo extraer la información de los partidos: {e}")
        return None

def add_or_update_event(event_details):
    summary_local = f"Málaga CF vs {event_details['oponente']}"
    summary_visitante = f"{event_details['oponente']} vs Málaga CF"

    # Consultar si hay eventos existentes por resumen (nombre del partido)
    events_local = service.events().list(calendarId=calendar_id, q=summary_local).execute().get('items', [])
    events_visitante = service.events().list(calendarId=calendar_id, q=summary_visitante).execute().get('items', [])

    existing_event = None
    if events_local:
        existing_event = next((event for event in events_local if event['start']['dateTime'] == event_details['fecha_hora_inicio']), None)
    elif events_visitante:
        existing_event = next((event for event in events_visitante if event['start']['dateTime'] == event_details['fecha_hora_inicio']), None)

    if existing_event:
        # Comparar el evento existente con el nuevo evento
        same_start = existing_event['start']['dateTime'] == event_details['fecha_hora_inicio']
        same_end = existing_event['end']['dateTime'] == event_details['fecha_hora_fin']
        same_location = existing_event.get('location', '') == ('Estadio La Rosaleda' if event_details['localidad'] == 'local' else 'Estadio Visitante')
        same_description = existing_event['description'] == event_details['descripcion']

        if same_start and same_end and same_location and same_description:
            print(f"El evento {event_details['oponente']} ya existe y coincide con los datos más recientes. No se modifica.")
        else:
            # Si los datos no coinciden, actualizar el evento
            event_id = existing_event['id']
            event = {
                'summary': summary_local if event_details['localidad'] == 'local' else summary_visitante,
                'location': 'Estadio La Rosaleda' if event_details['localidad'] == 'local' else 'Estadio Visitante',
                'description': event_details.get('descripcion', ''),
                'start': {
                    'dateTime': event_details['fecha_hora_inicio'],
                    'timeZone': 'Europe/Madrid',
                },
                'end': {
                    'dateTime': event_details['fecha_hora_fin'],
                    'timeZone': 'Europe/Madrid',
                },
            }
            updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            print(f"Evento actualizado: {updated_event['summary']} (ID: {updated_event['id']})")
    else:
        # Si no hay eventos existentes, añadir uno nuevo
        event = {
            'summary': summary_local if event_details['localidad'] == 'local' else summary_visitante,
            'location': 'Estadio La Rosaleda' if event_details['localidad'] == 'local' else 'Estadio Visitante',
            'description': event_details.get('descripcion', ''),
            'start': {
                'dateTime': event_details['fecha_hora_inicio'],
                'timeZone': 'Europe/Madrid',
            },
            'end': {
                'dateTime': event_details['fecha_hora_fin'],
                'timeZone': 'Europe/Madrid',
            },
        }
        print("Event data:", event)  # Imprime el objeto de evento
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"Evento creado: {created_event['summary']} (ID: {created_event['id']})")
        time.sleep(1)  # Espera de 1 segundo para evitar problemas de tasa de solicitudes

def actualizar_proximos_partidos():
    # Obtener la lista de próximos partidos
    proximos_partidos = obtener_proximos_partidos()
    
    if proximos_partidos:
        print(f"Próximos partidos encontrados: {proximos_partidos}")
        
        # Añadir o actualizar eventos en el calendario para cada partido
        for partido in proximos_partidos:
            add_or_update_event(partido)
    else:
        print("No se encontró información de los próximos partidos.")

# Llamada de ejemplo para actualizar los próximos partidos
actualizar_proximos_partidos()
