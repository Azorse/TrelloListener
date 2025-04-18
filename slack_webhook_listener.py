
import os
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_LIST_ID = os.getenv("TRELLO_LIST_ID")
TRELLO_LIST_ID_THIS_WEEK = os.getenv("TRELLO_LIST_ID_THIS_WEEK")

slack_client = WebClient(token=SLACK_BOT_TOKEN)

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

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.get_json(force=True)

    # Slack URL verification
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    if "event" in data:
        event = data["event"]
        text = event.get("text", "").strip().lower()
        if text.startswith("status:"):
            channel_id = event.get("channel")
            try:
                slack_client.chat_postMessage(
                    channel=channel_id,
                    text=build_status_message()
                )
            except SlackApiError as e:
                print(f"Slack API error: {e.response['error']}")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
