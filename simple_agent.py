from langgraph.prebuilt import create_react_agent
from dotenv import load_dotenv
import os
import asyncio
from jinja2 import Template
from typing import Any
from utils.logging import log_entry

load_dotenv()
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from langchain_mcp_adapters.tools import load_mcp_tools
# LLM setup
from langchain_google_genai import ChatGoogleGenerativeAI

# Configuration
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=1.0,
    max_retries=2,
    google_api_key=os.getenv('GEMINI_API_KEY')
)

_this_dir = os.path.dirname(os.path.abspath(__file__))
_system_prompt_path = os.path.join(_this_dir, 'system_prompt.jinja')
with open(_system_prompt_path, 'r', encoding='utf-8') as f:
    template = Template(f.read())
SYSTEM_PROMPT = template.render()


async def agent_runner(messages: list[dict[str, Any]]) -> None:
    """Run the LangChain agent with MCP tools."""
    
    async with streamablehttp_client(
        "http://127.0.0.1:8010/mcp",
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            system_message = {"role": "system", "content": SYSTEM_PROMPT}
            full_messages = [system_message] + messages
            agent = create_react_agent(llm, tools)
            try:
                async for step in agent.astream({"messages": full_messages}, stream_mode="values", config={"recursion_limit": 100}):
                    serializable_step = {k: [m.model_dump() for m in v] if k == "messages" and isinstance(v, list) else v for k, v in step.items()}
                    # Only log the last message to avoid duplicates
                    last_message = serializable_step["messages"][-1] if serializable_step.get("messages") else serializable_step
                    log_entry("step", last_message)

                # Log completion when agent has finished
                log_entry("agent_complete", {"status": "completed", "message": "Agent has finished execution"})

            except Exception as e:
                log_entry("error", str(e))










# Example usage (for testing)
if __name__ == "__main__":
    test_message = [{
        "role": "user",
        "content": "Whats the time?"
    }]

    asyncio.run(agent_runner(test_message))