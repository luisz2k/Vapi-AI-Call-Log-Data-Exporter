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
INBOUND_ASSISTANT_ID = os.getenv('INBOUND_ASSISTANT_ID')
BEARER_TOKEN = os.getenv('BEARER_TOKEN')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')

# Function to fetch call logs from the Vapi API
# Instead of using page numbers, the Vapi API uses cursor-based pagination. 
# We implement this by using the createdAtLt parameter and set it to the createdAt timestamp of the last
# call in the current batch of requests
def fetch_call_logs(url, assistant_id, bearer_token):
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    params = {
        "assistantId": assistant_id,
        "limit": 100  # Maximum allowed per request
    }
    all_calls = []
    
    while True:
        # Make a GET request to the API with a limit of 100 calls (the max allowed per request)
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()

        # Add the fetched calls to our list
        all_calls.extend(data)
        
        # Check if we've reached the end of the available data
        # If we receive fewer calls than the limit, it means we're on the last page so we exit the loop
        if len(data) < params["limit"]:
            break
        
        # Prepare for the next page by updating the createdAtLt parameter
        # This is how we implement cursor-based pagination
        # We use the createdAt timestamp of the last call in the current batch
        # as the starting point for the next request
        params["createdAtLt"] = data[-1]["createdAt"]
    
    print(f"Total calls fetched: {len(all_calls)}")
    return all_calls

# Function to calculate the duration of a call
def calculate_duration(start_time, end_time):
    start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    duration = (end - start).total_seconds()
    return duration

# Function to filter calls that last longer than a specified duration
def filter_calls(calls, min_duration=20):
    filtered_calls = []
    for call in calls:
        if 'startedAt' in call and 'endedAt' in call:
            try:
                duration = calculate_duration(call['startedAt'], call['endedAt'])
                if duration > min_duration:
                    phone_number = call.get('customer', {}).get('number', 'N/A')
                    analysis = call.get('analysis', {})
                    filtered_calls.append([
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
    return filtered_calls

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
    outbound_calls = fetch_call_logs(VAPI_URL, ASSISTANT_ID, BEARER_TOKEN)
    filtered_outbound_calls = filter_calls(outbound_calls)

    inbound_calls = fetch_call_logs(VAPI_URL, INBOUND_ASSISTANT_ID, BEARER_TOKEN)
    filtered_inbound_calls = filter_calls(inbound_calls)

    # Google Sheets Export
    RANGE_NAME = 'Sheet1!A1:H'  # Adjust based on your needs
    RANGE_NAME2 = 'Sheet2!A1:H'

    # Prepare the data
    values = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_outbound_calls
    values2 = [['ID', 'Phone Number', 'Duration (seconds)', 'Start Time', 'End Time', 'Summary', 'Success Evaluation', 'Transcript']] + filtered_inbound_calls

    result = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, values)
    result2 = update_google_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME2, values2)
    print(f"{result.get('updatedCells')} outbound cells updated.")
    print(f"{result2.get('updatedCells')} inbound cells updated.")

if __name__ == "__main__":
    main()
