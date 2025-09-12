# CogniQuery

AI-powered data analysis via Slack. Query databases, generate charts, create reports.

## Installation

```bash
pip install -r requirements.txt
```

Install weasyprint for PDF generation.

## Configuration

Set environment variables in `.env`:

```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
GEMINI_API_KEY=your-gemini-key
DATABASE_URL=postgresql://user:pass@host:port/db
```

## Usage

### Start MCP Server

```bash
# HTTP mode
python server.py http --host 127.0.0.1 --port 8010
```

### Start Slack Bot

```bash
python slack_bot.py
```

### Query Data

Mention bot in Slack: `@CogniQuery What are top sales by region?`

Bot analyzes database, creates charts, posts results.

## Features

- PostgreSQL database queries
- Automatic chart generation (matplotlib)
- PDF report creation
- Slack message/file uploads
- Schema exploration
- SQL execution
- Code interpretation for advanced analysis

## Requirements

- Python 3.8+
- PostgreSQL database
- Slack workspace with bot
- Gemini API key
- MCP-compatible tools

## Architecture

- **MCP Server**: Provides Slack integration tools
- **LangChain Agent**: Uses Gemini LLM for analysis
- **Slack Bot**: Handles mentions and responses
- **Tools**: Schema explorer, SQL executor, code interpreter, PDF generator






What if i want to use mcp though?
Why mcp doesnt work?

Take your time, think exterley deeply and like a senior engineer. Take your time. Make sure it will work.
Think from first principles and from the agents perspective,what the agent has, can do, how the image should be put in pdf, how to make it work, possible, how t3o deal with all of this,. think through and self critique, until you figure out a solution,

Also the result is this, i think u hardcoded it or something.

pdf should be based on agent and query, not hardcoded.

@agent_log.json @simple_agent.py @pdf_generator.py @server.py @slack_bot.py 
Fix
