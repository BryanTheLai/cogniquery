import os
import sys
import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def _env(name: str, default: str) -> str:
    val = os.getenv(name)
    return val if isinstance(val, str) and val.strip() else default


async def _extract_text(res: Any) -> str:
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


async def smoke() -> int:
    mcp_url: str = _env("MCP_URL", "http://127.0.0.1:8010/mcp")
    print(f"Using MCP server: {mcp_url}")

    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_list = await session.list_tools()
            tool_names = [t.name for t in getattr(tools_list, "tools", [])]
            print(f"Tools available: {tool_names}")
            needed = {"sql_executor", "code_interpreter", "generate_pdf_report", "retrieve_data"}
            missing = needed - set(tool_names)
            if missing:
                print(f"ERROR: Missing required tools: {sorted(missing)}")
                return 2

            # 1) Try a tiny SQL query
            sql_query = "SELECT 1 AS a, 2 AS b"
            print(f"Running sql_executor: {sql_query}")
            sql_res = await session.call_tool("sql_executor", {"sql_query": sql_query})
            sql_text = await _extract_text(sql_res)
            print(f"sql_executor raw: {sql_text}")

            fh: Optional[str] = None
            try:
                payload = json.loads(sql_text)
                if payload.get("success"):
                    fh = payload.get("file_handle")
                    print(f"sql_executor file_handle: {fh}")
                else:
                    print(f"sql_executor failed: {payload.get('error_message')}")
            except Exception as e:
                print(f"Failed to parse sql_executor output: {e}")

            # Fallback: if SQL not configured, synthesize a tiny CSV via store_data
            if not fh:
                if "store_data" not in tool_names:
                    print("ERROR: No file_handle and store_data tool not available for fallback")
                    return 3
                csv_data = "a,b\n1,2\n3,4\n"
                print("sql_executor unavailable; using store_data fallback with tiny CSV")
                store_res = await session.call_tool("store_data", {"data": csv_data, "file_name": "smoke.csv"})
                store_text = await _extract_text(store_res)
                print(f"store_data raw: {store_text}")
                try:
                    sp = json.loads(store_text)
                    if sp.get("success"):
                        fh = sp.get("file_handle")
                    else:
                        print(f"store_data failed: {sp.get('error_message')}")
                        return 4
                except Exception as e:
                    print(f"Failed to parse store_data output: {e}")
                    return 5

            assert fh, "No file_handle available"

            # 2) Run code_interpreter to create a chart
            code = (
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "df = pd.read_csv('/tmp/data.csv')\n"
                "fig, ax = plt.subplots(figsize=(6,4))\n"
                "ax.plot(df.columns, [1]*len(df.columns), marker='o', color='#2E86AB')\n"
                "ax.set_title('Smoke Test Chart', fontsize=14)\n"
                "plt.savefig('output/chart_1.png', dpi=150, bbox_inches='tight')\n"
                "plt.close()\n"
            )
            print("Running code_interpreter to generate chart...")
            ci_res = await session.call_tool("code_interpreter", {"code": code, "file_handle": fh})
            ci_text = await _extract_text(ci_res)
            print(f"code_interpreter raw: {ci_text[:500]}...")
            # We won't parse stdout/stderr deeply here; the PDF step will validate charts exist

            # 3) Generate PDF with embedded charts
            markdown = "# Smoke Report\n\nThis is a smoke test. Below should be a chart."
            print("Generating PDF report...")
            # Let generator auto-discover recent charts
            pdf_res = await session.call_tool("generate_pdf_report", {"markdown_content": markdown})
            pdf_text = await _extract_text(pdf_res)
            print(f"generate_pdf_report raw: {pdf_text}")
            pdf_handle: Optional[str] = None
            try:
                pp = json.loads(pdf_text)
                if pp.get("success"):
                    pdf_handle = pp.get("file_handle")
                    print(f"PDF file_handle: {pdf_handle}")
                else:
                    print(f"generate_pdf_report failed: {pp.get('error_message')}")
                    return 6
            except Exception as e:
                print(f"Failed to parse PDF output: {e}")
                return 7

            # 4) Retrieve the PDF to verify
            print("Retrieving PDF bytes...")
            ret_res = await session.call_tool("retrieve_data", {"file_handle": pdf_handle})
            ret_text = await _extract_text(ret_res)
            try:
                rp = json.loads(ret_text)
                if not rp.get("success"):
                    print(f"retrieve_data failed: {rp.get('error_message')}")
                    return 8
                data_latin: str = rp.get("data") or ""
                size = len(data_latin)
                print(f"PDF retrieved (latin1 length): {size} bytes")
                if size < 1000:
                    print("ERROR: PDF seems too small; embedding may have failed")
                    return 9
            except Exception as e:
                print(f"Failed to parse retrieve_data output: {e}")
                return 10

            print("Smoke workflow succeeded.")
            return 0


if __name__ == "__main__":
    rc = asyncio.run(smoke())
    sys.exit(rc)
