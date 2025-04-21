import os
import re
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# All your environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_LIST_ID = os.getenv("TRELLO_LIST_ID")
TRELLO_LIST_ID_THIS_WEEK = os.getenv("TRELLO_LIST_ID_THIS_WEEK")
TRELLO_LIST_ID_PAUSE = os.getenv("TRELLO_LIST_ID_PAUSE")
TRELLO_LIST_ID_DONE = os.getenv("TRELLO_LIST_ID_DONE")

slack_client = WebClient(token=SLACK_BOT_TOKEN)

processed_messages_file = "processed_messages.txt"

# Helper functions
def get_cards_from_list(list_id):
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return []

def build_status_message():
    on_deck = get_cards_from_list(TRELLO_LIST_ID)
    this_week = get_cards_from_list(TRELLO_LIST_ID_THIS_WEEK)

    message = "*📋 Status On Deck:*\n"
    message += "\n".join(f"• {card['name']}" for card in on_deck) if on_deck else "No cards."
    message += "\n\n*🟢 Status This Week:*\n"
    message += "\n".join(f"• {card['name']}" for card in this_week) if this_week else "No cards."
    return message

def create_trello_card(name, client, notes, due_date):
    description = f"Client: {client}\n\n{notes}" if notes else f"Client: {client}"
    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID,
        "name": name,
        "desc": description
    }
    if due_date:
        params["due"] = due_date
    response = requests.post(url, params=params)
    if response.status_code == 200:
        card_url = response.json().get("shortUrl")
        print("Card created:", card_url)
    else:
        print("Failed to create card:", response.text)

def move_card_to_list(task_name, list_id):
    for list_id_search in [TRELLO_LIST_ID, TRELLO_LIST_ID_THIS_WEEK, TRELLO_LIST_ID_PAUSE]:
        cards = get_cards_from_list(list_id_search)
        for card in cards:
            if task_name.lower() in card['name'].lower():
                card_id = card['id']
                url = f"https://api.trello.com/1/cards/{card_id}"
                params = {
                    "key": TRELLO_API_KEY, 
                    "token": TRELLO_TOKEN, 
                    "idList": list_id
                    }
                response = requests.put(url, params=params)
                if response.status_code == 200:
                    print(f"Moved card: {task_name} to list ID {list_id}")
                    return
                else:
                    print("Failed to move card:", response.text)
                    return
    print(f"Card not found for task: {task_name}")        

# Slack event route
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(force=True)

    # Slack URL verification
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    if "event" in data:
        event = data["event"]
        text = event.get("text", "").strip().lower()
        event_ts = event.get("ts")

        if message_already_processed(event_ts):
            return jsonify({"status": "duplicate"})

        if text.startswith("status:"):
            channel_id = event.get("channel")
            slack_client.chat_postMessage(channel=channel_id, text=build_status_message())

        elif text.startswith("new:"):
            match = re.match(r"new:\s*(.*?)\s+for\s+(.*?)\s+due\s+(\d{8})", text, re.IGNORECASE)
            if match:
                title = match.group(1)
                client = match.group(2)
                due_raw = match.group(3)
                due = f"{due_raw[:4]}-{due_raw[4:6]}-{due_raw[6:]}"
                create_trello_card(title, client, "", due)
            else:
                slack_client.chat_postMessage(channel=event.get("channel"), text="Could not parse message: '" + text + "'")

        elif text.startswith("start:"):
            move_card_to_list(text[6:].strip(), TRELLO_LIST_ID_THIS_WEEK)

        elif text.startswith("pause:"):
            move_card_to_list(text[6:].strip(), TRELLO_LIST_ID_PAUSE)

        elif text.startswith("done:"):
            move_card_to_list(text[5:].strip(), TRELLO_LIST_ID_DONE)

        mark_message_as_processed(event_ts)

    return jsonify({"status": "ok"})

def message_already_processed(ts):
    if not os.path.exists(processed_messages_file):
        return False
    with open(processed_messages_file, "r") as f:
        return ts in f.read()

def mark_message_as_processed(ts):
    with open(processed_messages_file, "a") as f:
        f.write(ts + "\n")

# Commented out for production
# if __name__ == "__main__":
#     app.run(port=5000)
