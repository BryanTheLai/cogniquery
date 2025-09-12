import os
import sys
import asyncio
import site
from datetime import datetime
from typing import Any, Tuple
import yaml
from dotenv import load_dotenv
from jinja2 import Template
from markdown_it import MarkdownIt
from weasyprint import HTML
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.logging import log_entry

load_dotenv()

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
from langchain_mcp_adapters.tools import load_mcp_tools

_this_dir = os.path.dirname(os.path.abspath(__file__))
_system_prompt_path = os.path.join(_this_dir, 'system_prompt.jinja')
with open(_system_prompt_path, 'r', encoding='utf-8') as f:
    _template = Template(f.read())
SYSTEM_PROMPT: str = _template.render()

def _output_dir() -> str:
    base = os.path.abspath(os.path.join(_this_dir))
    out = os.path.join(base, 'output')
    os.makedirs(out, exist_ok=True)
    return out

def _markdown_to_pdf(markdown_text: str, filename_hint: str = "final_report") -> str:
    md = MarkdownIt()
    html = md.render(markdown_text)
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    pdf_name = f"{filename_hint}_{ts}.pdf"
    pdf_path = os.path.join(_output_dir(), pdf_name)
    HTML(string=html).write_pdf(pdf_path)
    return os.path.abspath(pdf_path)

def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=1.0,
        max_retries=2,
        google_api_key=os.getenv('GEMINI_API_KEY')
    )

async def agent_run_to_text(messages: list[dict[str, Any]], mcp_url: str | None = None, system_prompt: str | None = None) -> str:
    url = mcp_url or os.getenv('MCP_URL', 'http://127.0.0.1:8010/mcp')
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Discover available tools and enforce usage at the prompt level
            tool_list = await session.list_tools()
            tool_names = [t.name for t in getattr(tool_list, 'tools', [])]
            tools = await load_mcp_tools(session)
            allowed_note = (
                "You may only call the following tools exposed by the MCP server. "
                "Do not invent tools or call unavailable ones. "
                f"Allowed tools: {', '.join(tool_names)}. "
                "When performing database analysis, use 'sql_executor' for SQL and 'code_interpreter' for charting."
            )
            sys_prompt = (system_prompt or SYSTEM_PROMPT) + "\n\n" + allowed_note
            system_message = {"role": "system", "content": sys_prompt}
            full_messages = [system_message] + messages
            agent = create_react_agent(_get_llm(), tools)
            
            # Collect all AI responses, not just the last one
            all_ai_content = []
            last_text = ""
            
            try:
                async for step in agent.astream({"messages": full_messages}, stream_mode="values", config={"recursion_limit": 100}):
                    serializable_step = {k: [m.model_dump() for m in v] if k == "messages" and isinstance(v, list) else v for k, v in step.items()}
                    if serializable_step.get("messages"):
                        last_message = serializable_step["messages"][-1]
                        log_entry("step", last_message)
                        
                        # Collect content from AI messages
                        if last_message.get("type") == "ai":
                            content = last_message.get("content") or ""
                            if isinstance(content, str) and content.strip():
                                # Skip tool calls and function calls, focus on actual content
                                if not last_message.get("tool_calls") and not last_message.get("additional_kwargs", {}).get("function_call"):
                                    all_ai_content.append(content.strip())
                                    last_text = content.strip()
                                elif content.strip() and not any(keyword in content.lower() for keyword in ["function_call", "tool_call", "arguments"]):
                                    # Include content that's not just tool metadata
                                    all_ai_content.append(content.strip())
                                    last_text = content.strip()
            except Exception as e:
                log_entry("error", str(e))
            
            log_entry("agent_complete", {"status": "completed"})
            
            # Return the most comprehensive content - prefer longer responses that contain analysis
            if all_ai_content:
                # Find the longest meaningful response (likely the final analysis)
                best_content = max(all_ai_content, key=len)
                return best_content if len(best_content) > len(last_text) else last_text
            
            return last_text

def _load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def _persona_system_prompt(agents_cfg: dict[str, Any], key: str) -> str:
    a = agents_cfg.get(key, {})
    role = a.get("role", "")
    goal = a.get("goal", "")
    backstory = a.get("backstory", "")
    return f"{SYSTEM_PROMPT}\n\nRole:\n{role}\n\nGoal:\n{goal}\n\nBackstory:\n{backstory}"

async def run_query_to_markdown(query: str, mcp_url: str | None = None) -> str:
    base = _this_dir
    agents_cfg_path = os.path.join(base, "config", "agents.yaml")
    tasks_cfg_path = os.path.join(base, "config", "tasks.yaml")
    agents_cfg = _load_yaml(agents_cfg_path)
    tasks_cfg = _load_yaml(tasks_cfg_path)

    pe_prompt = _persona_system_prompt(agents_cfg, "prompt_enhancer")
    pe_task = tasks_cfg.get("enhance_prompt_task", {})
    pe_desc = str(pe_task.get("description", "")).replace("{query}", query)
    refined = await agent_run_to_text([
        {"role": "user", "content": pe_desc}
    ], mcp_url=mcp_url, system_prompt=pe_prompt)
    if not refined:
        refined = query

    da_prompt = _persona_system_prompt(agents_cfg, "data_analyst")
    da_task = tasks_cfg.get("analyze_data_task", {})
    da_desc = da_task.get("description", "")
    analysis = await agent_run_to_text([
        {"role": "user", "content": f"Refined question:\n{refined}\n\nTask instructions:\n{da_desc}"}
    ], mcp_url=mcp_url, system_prompt=da_prompt)
    if not analysis:
        analysis = refined

    rg_prompt = _persona_system_prompt(agents_cfg, "report_generator")
    gr_task = tasks_cfg.get("generate_report_task", {})
    gr_desc = gr_task.get("description", "")
    final_markdown = await agent_run_to_text([
        {"role": "user", "content": f"Create the final executive-ready report.\n\nInstructions:\n{gr_desc}\n\nAnalysis:\n{analysis}"}
    ], mcp_url=mcp_url, system_prompt=rg_prompt)
    if not final_markdown:
        final_markdown = analysis

    return final_markdown

async def run_query_and_generate_pdf(query: str, mcp_url: str | None = None) -> Tuple[str, str]:
    final_markdown = await run_query_to_markdown(query, mcp_url=mcp_url)
    pdf_path = _markdown_to_pdf(final_markdown, filename_hint="final_report")
    return final_markdown, pdf_path

if __name__ == "__main__":
    test_query = "What is the time?"
    asyncio.run(run_query_and_generate_pdf(test_query))
