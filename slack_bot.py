# slack_bot.py

import os
import sys
import site
import threading
import asyncio
import re
from typing import Any
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from simple_agent import run_query_to_markdown

# Ensure installed 'mcp' package is used rather than local './mcp' folder
_repo_root = os.path.dirname(os.path.abspath(__file__))
try:
    if _repo_root in sys.path:
        sys.path.remove(_repo_root)
    site_paths: list[str] = []
    try:
        site_paths.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        user_site = site.getusersitepackages()
        if isinstance(user_site, str):
            site_paths.append(user_site)
    except Exception:
        pass
    for p in reversed([sp for sp in site_paths if sp in sys.path]):
        sys.path.remove(p)
        sys.path.insert(0, p)
except Exception:
    pass

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# Load environment variables from .env file
load_dotenv()

# --- Slack App Initialization ---
# Initialize with your bot token and app token
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

def _md_to_slack(text: str) -> str:
    t = text
    t = re.sub(r'^(#{1,6})\s*(.+)$', lambda m: f"*{m.group(2).strip()}*", t, flags=re.MULTILINE)
    t = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', t)
    t = t.replace('---', '')
    return t

def run_cogniquery_and_reply(query: str, channel_id: str, client: Any) -> None:
    """
    Run the agent with the user's query and send the result back to the Slack channel.
    """
    try:
        print(f"🚀 Received query: '{query}' - Activating agent")

        final_markdown = asyncio.run(run_query_to_markdown(query))
        print("✅ Final markdown generated, posting summary and generating PDF...")
        slack_text = _md_to_slack(final_markdown)

        mcp_url = os.getenv("MCP_URL", "http://127.0.0.1:8010/mcp")

        async def _extract_text_content(res: Any) -> str:
            try:
                items = getattr(res, "content", None)
                if items is None and isinstance(res, dict):
                    items = res.get("content")
                if items:
                    texts = []
                    for it in items:
                        t = getattr(it, "text", None)
                        if t is None and isinstance(it, dict):
                            t = it.get("text")
                        if t:
                            texts.append(t)
                    if texts:
                        return "\n".join(texts)
                return str(res)
            except Exception:
                return str(res)

        async def _post_summary(text: str) -> None:
            async with streamablehttp_client(mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    try:
                        await session.call_tool("slack_post", {"channel": channel_id, "text": text})
                    except Exception as e:
                        print(f"⚠️ slack_post via MCP failed: {e}")

        async def _generate_pdf_and_upload(markdown_text: str) -> None:
            async with streamablehttp_client(mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    try:
                        import json as _json
                        # Discover recent chart handles saved by code_interpreter in secure storage
                        try:
                            storage_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.tmp_secure_storage')
                            candidates: list[tuple[float, str]] = []
                            for ext in ('.png', '.jpg', '.jpeg'):
                                for name in os.listdir(storage_dir):
                                    if name.lower().endswith(ext):
                                        full = os.path.join(storage_dir, name)
                                        try:
                                            candidates.append((os.path.getmtime(full), name))
                                        except Exception:
                                            pass
                            candidates.sort(reverse=True)
                            chart_handles = [n for _, n in candidates[:10]]
                        except Exception:
                            chart_handles = []
                        gen_res = await session.call_tool(
                            "generate_pdf_report",
                            {"markdown_content": markdown_text, "chart_handles": chart_handles}
                        )
                        txt = await _extract_text_content(gen_res)
                        handle = None
                        try:
                            payload = _json.loads(txt)
                            handle = payload.get("file_handle")
                        except Exception:
                            handle = None
                        if not handle:
                            print("⚠️ No file_handle returned for PDF; skipping upload")
                            return
                        await session.call_tool(
                            "slack_upload",
                            {
                                "channel": channel_id,
                                "filename": "final_report.pdf",
                                "file_handle": handle,
                                "initial_comment": "Here is your report (PDF).",
                                "title": "CogniQuery Report",
                            },
                        )
                    except Exception as e:
                        print(f"⚠️ PDF generate/upload via MCP failed: {e}")

        async def _orchestrate() -> None:
            await asyncio.gather(
                _post_summary(slack_text),
                _generate_pdf_and_upload(final_markdown),
            )

        asyncio.run(_orchestrate())
        print(f"📨 Posted summary and uploaded PDF to channel {channel_id} via MCP")

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