import asyncio
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


async def _extract_text_content(res: Any) -> str:
    try:
        items = getattr(res, "content", None)
        if items is None and isinstance(res, dict):
            items = res.get("content")
        if items:
            texts: List[str] = []
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


async def _call_tool(session: ClientSession, name: str, args: Dict[str, Any]) -> str:
    res = await session.call_tool(name, args)
    return await _extract_text_content(res)


async def run_all_tools() -> None:
    base_url = os.getenv("TEST_MCP_URL", os.getenv("MCP_URL", "http://127.0.0.1:8010/mcp"))
    print(f"Connecting to MCP at: {base_url}")

    results: List[Tuple[str, str]] = []

    async with streamablehttp_client(base_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = [t.name for t in getattr(tools, "tools", [])]
            print("Available tools:", tool_names)

            # echo
            try:
                out = await _call_tool(session, "echo", {"text": "hello"})
                results.append(("echo", out.strip()))
            except Exception as e:
                results.append(("echo", f"error: {e}"))

            # schema_explorer (best-effort)
            try:
                out = await _call_tool(session, "schema_explorer", {})
                results.append(("schema_explorer", out[:200] + ("..." if len(out) > 200 else "")))
            except Exception as e:
                results.append(("schema_explorer", f"error: {e}"))

            # store_data / retrieve_data (text)
            handle_text: str = ""
            try:
                payload_text = await _call_tool(session, "store_data", {"data": "sample text", "file_name": "sample.txt"})
                j = json.loads(payload_text)
                handle_text = j.get("file_handle", "")
                results.append(("store_data(text)", payload_text))
                if handle_text:
                    r = await _call_tool(session, "retrieve_data", {"file_handle": handle_text})
                    results.append(("retrieve_data(text)", r[:80] + ("..." if len(r) > 80 else "")))
            except Exception as e:
                results.append(("store/retrieve(text)", f"error: {e}"))

            # sql_executor (simple SELECT 1) best-effort
            sql_handle: str = ""
            try:
                sql_out = await _call_tool(session, "sql_executor", {"sql_query": "SELECT 1 AS one"})
                results.append(("sql_executor", sql_out))
                try:
                    j = json.loads(sql_out)
                    sql_handle = j.get("file_handle", "")
                except Exception:
                    pass
            except Exception as e:
                results.append(("sql_executor", f"error: {e}"))

            # code_interpreter with synthetic CSV -> generate a chart artifact
            artifact_handles: List[str] = []
            try:
                csv_data = "x,y\n1,2\n3,4\n5,7\n"
                store_csv = await _call_tool(session, "store_data", {"data": csv_data, "file_name": "data.csv"})
                j = json.loads(store_csv)
                fh = j.get("file_handle", "")
                code = (
                    "import pandas as pd\n"
                    "import matplotlib.pyplot as plt\n"
                    "df = pd.read_csv('/tmp/data.csv')\n"
                    "plt.figure(figsize=(4,3))\n"
                    "plt.plot(df['x'], df['y'], marker='o')\n"
                    "plt.title('Test Chart')\n"
                    "import os\n"
                    "os.makedirs('output', exist_ok=True)\n"
                    "plt.savefig('output/test_chart.png', dpi=120)\n"
                    "print('done')\n"
                )
                ci_out = await _call_tool(session, "code_interpreter", {"file_handle": fh, "code": code})
                results.append(("code_interpreter", ci_out[:200] + ("..." if len(ci_out) > 200 else "")))
                try:
                    j2 = json.loads(ci_out)
                    if isinstance(j2, dict) and j2.get("artifacts"):
                        artifact_handles = [str(a) for a in j2["artifacts"]]
                except Exception:
                    pass
            except Exception as e:
                results.append(("code_interpreter", f"error: {e}"))

            # generate_pdf_report using markdown and any artifact handles
            pdf_handle: str = ""
            try:
                md = "# Smoke Report\n\nThis is a test.\n\n## Chart\n\n"
                gen_out = await _call_tool(
                    session,
                    "generate_pdf_report",
                    {
                        "markdown_content": md,
                        "chart_handles": json.dumps(artifact_handles),
                    },
                )
                results.append(("generate_pdf_report", gen_out))
                try:
                    j = json.loads(gen_out)
                    pdf_handle = j.get("file_handle", "")
                except Exception:
                    pass
            except Exception as e:
                results.append(("generate_pdf_report", f"error: {e}"))

            # retrieve_data(pdf) just to ensure we can read it back
            try:
                if pdf_handle:
                    rpdf = await _call_tool(session, "retrieve_data", {"file_handle": pdf_handle})
                    results.append(("retrieve_data(pdf)", rpdf[:80] + ("..." if len(rpdf) > 80 else "")))
            except Exception as e:
                results.append(("retrieve_data(pdf)", f"error: {e}"))

            # web_search (best-effort)
            try:
                ws = await _call_tool(session, "web_search", {"query": "OpenAI"})
                results.append(("web_search", ws[:120] + ("..." if len(ws) > 120 else "")))
            except Exception as e:
                results.append(("web_search", f"error: {e}"))

            # scrape_website (best-effort)
            try:
                sw = await _call_tool(session, "scrape_website", {"url": "https://example.com"})
                results.append(("scrape_website", sw[:120] + ("..." if len(sw) > 120 else "")))
            except Exception as e:
                results.append(("scrape_website", f"error: {e}"))

            # Slack tools (optional based on env)
            channel = os.getenv("TEST_SLACK_CHANNEL", "")
            if channel:
                try:
                    sp = await _call_tool(session, "slack_post", {"channel": channel, "text": "MCP smoke test message"})
                    results.append(("slack_post", sp))
                except Exception as e:
                    results.append(("slack_post", f"error: {e}"))

                # upload tiny 1x1 PNG as base64
                try:
                    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
                    up = await _call_tool(session, "slack_upload", {"channel": channel, "filename": "pixel.png", "data_base64": png_b64, "initial_comment": "MCP smoke upload (base64)"})
                    results.append(("slack_upload(base64)", up))
                except Exception as e:
                    results.append(("slack_upload(base64)", f"error: {e}"))

                # upload the generated PDF via file_handle
                try:
                    if pdf_handle:
                        up2 = await _call_tool(session, "slack_upload", {"channel": channel, "filename": "smoke_report.pdf", "file_handle": pdf_handle, "initial_comment": "MCP smoke upload (file_handle)"})
                        results.append(("slack_upload(file_handle)", up2))
                except Exception as e:
                    results.append(("slack_upload(file_handle)", f"error: {e}"))
            else:
                results.append(("slack_post/upload", "skipped: TEST_SLACK_CHANNEL not set"))

    print("\n=== MCP Smoke Results ===")
    for name, res in results:
        print(f"- {name}: {res}")


if __name__ == "__main__":
    asyncio.run(run_all_tools())
