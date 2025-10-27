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
    html_body = md.render(markdown_text)
    
    # Professional CSS styling for executive reports
    css = """
        @page {
            size: A4;
            margin: 2cm;
        }
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }
        h1 {
            font-size: 24pt;
            font-weight: bold;
            color: #1a1a1a;
            margin-top: 0;
            margin-bottom: 0.5em;
            padding-bottom: 0.3em;
            border-bottom: 3px solid #2E86AB;
        }
        h2 {
            font-size: 18pt;
            font-weight: bold;
            color: #2E86AB;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            page-break-after: avoid;
        }
        h3 {
            font-size: 14pt;
            font-weight: bold;
            color: #444;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }
        p {
            margin-bottom: 0.8em;
            text-align: justify;
        }
        strong {
            font-weight: bold;
            color: #1a1a1a;
        }
        em {
            font-style: italic;
            color: #666;
        }
        ul, ol {
            margin-left: 1.5em;
            margin-bottom: 1em;
        }
        li {
            margin-bottom: 0.5em;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            font-size: 10pt;
        }
        th {
            background-color: #2E86AB;
            color: white;
            font-weight: bold;
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
        }
        td {
            padding: 10px 12px;
            border: 1px solid #ddd;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        tr:hover {
            background-color: #f0f0f0;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 1.5em auto;
            page-break-inside: avoid;
        }
        hr {
            border: none;
            border-top: 2px solid #ddd;
            margin: 1.5em 0;
        }
        code {
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 9pt;
        }
        pre {
            background-color: #f4f4f4;
            padding: 1em;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 9pt;
        }
        blockquote {
            border-left: 4px solid #2E86AB;
            padding-left: 1em;
            margin-left: 0;
            color: #666;
            font-style: italic;
        }
    """
    
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>{css}</style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """
    
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    pdf_name = f"{filename_hint}_{ts}.pdf"
    pdf_path = os.path.join(_output_dir(), pdf_name)
    HTML(string=full_html).write_pdf(pdf_path)
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
                            
                            # Extract text from content (handles both string and array formats)
                            text_content = ""
                            if isinstance(content, str):
                                text_content = content
                            elif isinstance(content, list):
                                # Extract text from array of content blocks
                                for item in content:
                                    if isinstance(item, dict):
                                        if item.get("type") == "text" and "text" in item:
                                            text_content += item["text"]
                            
                            if text_content.strip():
                                # Skip tool calls and function calls, focus on actual content
                                if not last_message.get("tool_calls") and not last_message.get("additional_kwargs", {}).get("function_call"):
                                    all_ai_content.append(text_content.strip())
                                    last_text = text_content.strip()
                                elif not any(keyword in text_content.lower() for keyword in ["function_call", "tool_call", "arguments"]):
                                    # Include content that's not just tool metadata
                                    all_ai_content.append(text_content.strip())
                                    last_text = text_content.strip()
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

async def run_query_to_markdown(query: str, mcp_url: str | None = None) -> Tuple[str, str]:
    """
    Run the full analysis workflow and return (markdown_report, analysis_with_charts).
    The analysis contains the data insights and chart references.
    """
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

    return final_markdown, analysis

async def run_query_and_generate_pdf(query: str, mcp_url: str | None = None) -> Tuple[str, str]:
    final_markdown, analysis = await run_query_to_markdown(query, mcp_url=mcp_url)
    pdf_path = _markdown_to_pdf(final_markdown, filename_hint="final_report")
    return final_markdown, pdf_path

if __name__ == "__main__":
    test_query = "What is the time?"
    asyncio.run(run_query_and_generate_pdf(test_query))
