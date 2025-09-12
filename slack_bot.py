# slack_bot.py

import os
import threading
import asyncio
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from simple_agent import agent_runner


# Load environment variables from .env file
load_dotenv()

# --- Slack App Initialization ---
# Initialize with your bot token and app token
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

def run_cogniquery_and_reply(query: str, channel_id: str, client):
    """
    Run the agent with the user's query and send the result back to the Slack channel.
    """
    try:
        print(f"🚀 Received query: '{query}' - Activating agent")

        # Format query as messages for the agent
        messages = [{"role": "user", "content": query}]

        # Run the agent
        asyncio.run(agent_runner(messages))

        # Send response
        client.chat_postMessage(
            channel=channel_id,
            text=f"Agent processed: '{query}' - Analysis complete."
        )
        print(f"📨 Sent response to channel {channel_id}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        error_message = f"I'm sorry, I encountered an error while processing your request: `{str(e)}`"
        client.chat_postMessage(channel=channel_id, text=error_message)


@app.event("app_mention")
def handle_app_mention_events(body: dict, say, client):
    """
    This listener triggers when the bot is @mentioned in a channel.
    """
    print(f"🎯 Received app_mention event: {body}")
    
    event = body["event"]
    channel_id = event["channel"]
    user_id = event["user"]
    
    # Extract the bot's own user ID from the event
    bot_user_id = body.get("authorizations", [{}])[0].get("user_id")
    if not bot_user_id:
        # Fallback method to get bot user ID
        try:
            auth_response = client.auth_test()
            bot_user_id = auth_response["user_id"]
        except Exception as e:
            print(f"❌ Could not get bot user ID: {e}")
            bot_user_id = None

    # Remove the bot's user ID from the message text to get the clean query
    query = event["text"]
    if bot_user_id:
        query = query.replace(f"<@{bot_user_id}>", "").strip()
    
    print(f"🤖 Received mention in channel {channel_id} from user {user_id}")
    print(f"📝 Raw message: {event['text']}")
    print(f"🔍 Extracted query: '{query}'")

    if not query:
        say("Hi! Please provide a question about your data after mentioning me. For example: `@CogniQuery Bot What are our top selling products?`")
        return

    # Acknowledge the request immediately
    acknowledge_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚀 *Got it!* Activating agent for:\n\n*\"{query}\"*"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "⏱️ Processing with AI agent • 📊 Data analysis in progress • 📄 Results will be sent shortly"
                }
            ]
        }
    ]
    
    say(
        text=f"Analyzing: '{query}'...",  # Fallback text
        blocks=acknowledge_blocks
    )

    # Run the intensive crew process in a separate thread
    thread = threading.Thread(
        target=run_cogniquery_and_reply,
        args=(query, channel_id, client)
    )
    thread.start()

# Add a simple test event handler to verify the bot is receiving events
@app.event("message")
def handle_message_events(body, logger):
    """
    This is just for debugging - to see if we're receiving any events at all
    """
    print(f"📨 Received message event (for debugging): {body.get('event', {}).get('text', 'No text')}")

# Add error handling
@app.error
def global_error_handler(error, body, logger):
    print(f"❌ Global error occurred: {error}")
    print(f"Body: {body}")

if __name__ == "__main__":
    print("⚡️ CogniQuery Slack Bot is starting...")
    print("📡 Attempting to connect to Slack via Socket Mode...")
    
    try:
        # Use SocketModeHandler for easy local development without exposing a public URL
        handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
        print("✅ Socket Mode handler created successfully")
        print("🚀 Bot is now running and listening for events...")
        handler.start()
    except Exception as e:
        print(f"❌ Failed to start bot: {e}")
        import traceback
        traceback.print_exc()