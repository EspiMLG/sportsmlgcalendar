import os
import json
import time
import requests
from bs4 import BeautifulSoup
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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

# Configuración de la API de Google Custom Search
API_KEY = 'TU_API_KEY'
SEARCH_ENGINE_ID = 'TU_ID_DE_MOTOR_DE_BÚSQUEDA'

def consultar_proximo_partido():
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        res = service.cse().list(q="próximo partido del Málaga CF", cx=SEARCH_ENGINE_ID).execute()
        
        # Verifica el contenido de los resultados
        print("Resultados de la búsqueda:", res)
        
        # Extrae el primer resultado
        items = res.get("items", [])
        if not items:
            print("No se encontraron resultados.")
            return None

        # Usamos el snippet para obtener información
        snippet = items[0].get("snippet", "")
        print("Snippet del resultado:", snippet)

        # Aquí se procesa el snippet para extraer la información del partido
        # Este es un ejemplo básico y puede necesitar ajustes dependiendo del formato
        lines = snippet.split("\n")
        if len(lines) >= 2:
            match_info = lines[0]
            date_time = lines[1]
        else:
            print("No se encontró información estructurada en el snippet.")
            return None

        teams = match_info.split(' - ')
        if len(teams) < 2:
            print("Formato inesperado en la información del partido.")
            return None

        oponente = teams[1] if "Málaga CF" in teams[0] else teams[0]
        fecha_hora_inicio = date_time.split(' ')[0] + "T" + date_time.split(' ')[1] + ":00"
        fecha_hora_fin = fecha_hora_inicio.split(':')[0] + ":00:00"  # Asumimos una duración de 2 horas
        localidad = "local" if "Málaga CF" in teams[0] else "visitante"
        descripcion = "Próximo partido del Málaga CF"

        return {
            "oponente": oponente,
            "fecha_hora_inicio": fecha_hora_inicio,
            "fecha_hora_fin": fecha_hora_fin,
            "localidad": localidad,
            "descripcion": descripcion
        }
    except Exception as e:
        print(f"No se pudo extraer la información del próximo partido: {e}")
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
        same_location = existing_event['location'] == event_details['location']
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
            print(f"  - same_start: {same_start}, same_end: {same_end}, same_location: {same_location}, same_description: {same_description}")
            print(f"  - existing_event: {existing_event}")
            print(f"  - new_event: {event}")
            time.sleep(1)  # Espera de 1 segundo para evitar problemas de tasa de solicitudes
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
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"Evento creado: {created_event['summary']} (ID: {created_event['id']})")
        time.sleep(1)  # Espera de 1 segundo para evitar problemas de tasa de solicitudes

def actualizar_proximo_partido():
    # Consultar el próximo partido del Málaga CF
    proximo_partido = consultar_proximo_partido()
    
    if proximo_partido:
        print(f"Próximo partido encontrado: {proximo_partido}")
        
        # Llamar a la función para añadir o actualizar el evento
        add_or_update_event(proximo_partido)
    else:
        print("No se encontró información del próximo partido.")

# Llamada de ejemplo para actualizar el próximo partido
actualizar_proximo_partido()
