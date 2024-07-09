import os
import requests
import json
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Environment variables
VAPI_URL = os.getenv('VAPI_URL')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Function to fetch call logs from the Vapi API
def fetch_call_logs(url, assistant_id, bearer_token):
    headers = {"Authorization": f"Bearer {bearer_token}"}
    querystring = {"assistantId": assistant_id}
    response = requests.request("GET", url, headers=headers, params=querystring)
    calls = json.loads(response.text)
    return calls

# Function to calculate the duration of a call
def calculate_duration(start_time, end_time):
    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    duration = (end - start).total_seconds()
    return duration

# Function to filter calls that last longer than a specified duration
def filter_relevant_calls(calls, min_duration=20):
    relevant_calls = []
    for call in calls:
        if 'startedAt' in call and 'endedAt' in call:
            try:
                duration = calculate_duration(call['startedAt'], call['endedAt'])
                if duration > min_duration:
                    phone_number = call.get('customer', {}).get('number', 'N/A')
                    analysis = call.get('analysis', {})
                    relevant_calls.append([
                        call['id'],
                        phone_number,
                        duration,
                        call['startedAt'],
                        call['endedAt'],
                        analysis.get('summary', 'N/A'),
                        analysis.get('successEvaluation', 'N/A'),
                        call['transcript']
                    ])
            except ValueError as e:
                print(f"Error calculating duration for call {call['id']}: {str(e)}")
    return relevant_calls

# Function to update the Google Sheet with call data
def update_google_sheet(service_account_file, spreadsheet_id, range_name, data):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    result = sheet.values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body={'values': data}).execute()

    return result

# Main function to fetch call logs, filter them, and update the Google Sheet
def main():
    calls = fetch_call_logs(VAPI_URL, ASSISTANT_ID, BEARER_TOKEN)
    relevant_calls = filter_relevant_calls(calls)

    # Google Sheets Export
    RANGE_NAME = 'Sheet1!A1:H'  # Adjust based on your needs

    # Prepare the data
    values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + relevant_calls

    result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, values)
    print(f"{result.get('updatedCells')} cells updated.")

if __name__ == "__main__":
    main()
