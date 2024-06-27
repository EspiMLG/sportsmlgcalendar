import os
import datetime
import json
import time
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Credenciales desde las variables de entorno
credentials_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

# Credenciales de servicio para acceder a la API
credentials = Credentials.from_service_account_info(
    json.loads(credentials_json),
    scopes=['https://www.googleapis.com/auth/calendar']
)

# Conectar con la API de Google Calendar
service = build('calendar', 'v3', credentials=credentials)

# ID del calendario donde añadir los eventos
calendar_id = '482b569e5fd8fd1c9d2d19b3e2d06b4587d8f3490af5cf17d7b2a289e0f4516f@group.calendar.google.com'

# Lista de partidos (aquí irían las consultas a la fuente de datos de los partidos)
partidos = [
    {"equipo": "Racing de Ferrol", "fecha": "2024-08-18", "localidad": "visitante"},
    {"equipo": "Mirandés", "fecha": "2024-08-25", "localidad": "local"},
    {"equipo": "Albacete", "fecha": "2024-09-01", "localidad": "local"},
    {"equipo": "Córdoba", "fecha": "2024-09-08", "localidad": "visitante"},
    {"equipo": "Huesca", "fecha": "2024-09-15", "localidad": "local"},
    {"equipo": "Granada", "fecha": "2024-09-22", "localidad": "visitante"},
    {"equipo": "Elche", "fecha": "2024-09-29", "localidad": "local"},
    {"equipo": "Dépor", "fecha": "2024-10-06", "localidad": "visitante"},
    {"equipo": "Cádiz", "fecha": "2024-10-13", "localidad": "visitante"},
    {"equipo": "Oviedo", "fecha": "2024-10-20", "localidad": "local"},
    {"equipo": "Tenerife", "fecha": "2024-10-23", "localidad": "visitante"},
    {"equipo": "Eibar", "fecha": "2024-10-27", "localidad": "local"},
    {"equipo": "Levante", "fecha": "2024-11-03", "localidad": "visitante"},
    {"equipo": "Cartagena", "fecha": "2024-11-10", "localidad": "local"},
    {"equipo": "Zaragoza", "fecha": "2024-11-17", "localidad": "visitante"},
    {"equipo": "Racing", "fecha": "2024-11-24", "localidad": "local"},
    {"equipo": "Castellón", "fecha": "2024-12-01", "localidad": "visitante"},
    {"equipo": "Almería", "fecha": "2024-12-08", "localidad": "local"},
    {"equipo": "Burgos", "fecha": "2024-12-15", "localidad": "visitante"},
    {"equipo": "Eldense", "fecha": "2024-12-18", "localidad": "local"},
    {"equipo": "Sporting", "fecha": "2024-12-22", "localidad": "visitante"},
    {"equipo": "Dépor", "fecha": "2025-01-11", "localidad": "local"},
    {"equipo": "Mirandés", "fecha": "2025-01-19", "localidad": "visitante"},
    {"equipo": "Zaragoza", "fecha": "2025-01-26", "localidad": "local"},
    {"equipo": "Racing", "fecha": "2025-02-02", "localidad": "visitante"},
    {"equipo": "Levante", "fecha": "2025-02-09", "localidad": "local"},
    {"equipo": "Cartagena", "fecha": "2025-02-16", "localidad": "visitante"},
    {"equipo": "Tenerife", "fecha": "2025-02-23", "localidad": "local"},
    {"equipo": "Almería", "fecha": "2025-03-02", "localidad": "visitante"},
    {"equipo": "Cádiz", "fecha": "2025-03-09", "localidad": "local"},
    {"equipo": "Albacete", "fecha": "2025-03-16", "localidad": "visitante"},
    {"equipo": "Racing de Ferrol", "fecha": "2025-03-23", "localidad": "local"},
    {"equipo": "Oviedo", "fecha": "2025-03-30", "localidad": "visitante"},
    {"equipo": "Córdoba", "fecha": "2025-04-06", "localidad": "local"},
    {"equipo": "Huesca", "fecha": "2025-04-13", "localidad": "visitante"},
    {"equipo": "Eibar", "fecha": "2025-04-20", "localidad": "visitante"},
    {"equipo": "Castellón", "fecha": "2025-04-27", "localidad": "local"},
    {"equipo": "Granada", "fecha": "2025-05-04", "localidad": "local"},
    {"equipo": "Eldense", "fecha": "2025-05-11", "localidad": "visitante"},
    {"equipo": "Sporting", "fecha": "2025-05-18", "localidad": "local"},
    {"equipo": "Elche", "fecha": "2025-05-25", "localidad": "visitante"},
    {"equipo": "Burgos", "fecha": "2025-06-01", "localidad": "local"}
]

# Función para añadir o actualizar un evento en Google Calendar
def add_or_update_event(partido):
    summary = f"Málaga CF vs {partido['equipo']}" if partido["localidad"] == "local" else f"{partido['equipo']} vs Málaga CF"
    start_date = datetime.datetime.strptime(partido["fecha"], "%Y-%m-%d").strftime("%Y-%m-%dT12:00:00")
    end_date = (datetime.datetime.strptime(partido["fecha"], "%Y-%m-%d") + datetime.timedelta(hours=2)).strftime("%Y-%m-%dT14:00:00")
    
    location = "Estadio La Rosaleda" if partido["localidad"] == "local" else "Estadio Visitante"
    
    event = {
        'summary': summary,
        'location': location,
        'description': f"Partido de la jornada {partidos.index(partido) + 1}",
        'start': {
            'dateTime': start_date,
            'timeZone': 'Europe/Madrid',
        },
        'end': {
            'dateTime': end_date,
            'timeZone': 'Europe/Madrid',
        },
    }
    
    # Buscar evento existente por resumen y fecha
    time_min = datetime.datetime.strptime(partido["fecha"], "%Y-%m-%d").strftime("%Y-%m-%dT00:00:00Z")
    time_max = datetime.datetime.strptime(partido["fecha"], "%Y-%m-%d").strftime("%Y-%m-%dT23:59:59Z")
    
    events_result = service.events().list(
        calendarId=calendar_id,
        q=summary,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True
    ).execute()
    events = events_result.get('items', [])
    
    if events:
        existing_event = events[0]
        
        # Comparar el evento existente con el nuevo evento
        same_start = existing_event['start']['dateTime'] == event['start']['dateTime']
        same_end = existing_event['end']['dateTime'] == event['end']['dateTime']
        same_location = existing_event['location'] == event['location']
        same_description = existing_event['description'] == event['description']

        if same_start and same_end and same_location and same_description:
            print(f"El evento {event['summary']} ya existe y coincide con los datos más recientes. No se modifica.")
        else:
            # Si los datos no coinciden, actualizar el evento
            event_id = existing_event['id']
            updated_event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event).execute()
            print(f"Evento actualizado: {updated_event['summary']} (ID: {updated_event['id']})")
            print(f"  - same_start: {same_start}, same_end: {same_end}, same_location: {same_location}, same_description: {same_description}")
            print(f"  - existing_event: {existing_event}")
            print(f"  - new_event: {event}")
            time.sleep(1)  # Espera de 1 segundo para evitar problemas de tasa de solicitudes
    else:
        # Si no hay eventos existentes, añadir uno nuevo
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"Evento creado: {created_event['summary']} (ID: {created_event['id']})")
        time.sleep(1)  # Espera de 1 segundo para evitar problemas de tasa de solicitudes

# Procesar todos los partidos
for partido in partidos:
    print(f"Procesando el partido: {partido['equipo']} en fecha {partido['fecha']} como {partido['localidad']}")
    add_or_update_event(partido)

print("Todos los eventos han sido procesados.")
