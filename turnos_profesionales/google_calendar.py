import os
from django.conf import settings
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

class GoogleCalendarManager:
    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        token_path = os.path.join(settings.GOOGLE_CREDENTIALS_DIR, "token.json")
        client_secret_path = os.path.join(settings.GOOGLE_CREDENTIALS_DIR, "client_secret.json")
        
        if not os.path.exists(client_secret_path):
            raise FileNotFoundError(
                f"❌ Archivo client_secret.json no encontrado en {settings.GOOGLE_CREDENTIALS_DIR}.\n"
                "Descargalo desde Google Cloud Console > Credenciales."
            )
        
        try:
            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                    creds = flow.run_local_server(port=9090)

                with open(token_path, "w") as token:
                    token.write(creds.to_json())
        except RefreshError:
            if os.path.exists(token_path):
                os.remove(token_path)
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=9090)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def create_event(self, summary, start_time, end_time, timezone, attendees=None, description=None, location=None):
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': timezone,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 24 horas antes
                    {'method': 'popup', 'minutes': 60},       # 1 hora antes
                ],
            },
        }

        if attendees:
            event["attendees"] = [{"email": email} for email in attendees if email]
        
        if description:
            event["description"] = description
        
        if location:
            event["location"] = location

        try:
            created_event = self.service.events().insert(
                calendarId="primary", 
                body=event,
                sendUpdates="all"
            ).execute()
            print(f"✅ Evento creado: {created_event.get('htmlLink')}")
            return created_event
        except HttpError as error:
            print(f"❌ Error: {error}")
            return None

    def delete_event(self, event_id):
        if not event_id:
            return False
        try:
            self.service.events().delete(
                calendarId='primary', 
                eventId=event_id,
                sendUpdates="all"
            ).execute()
            print(f"✅ Evento eliminado: {event_id}")
            return True
        except HttpError:
            return False