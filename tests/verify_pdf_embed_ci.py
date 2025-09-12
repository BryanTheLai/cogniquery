import os
import json
import asyncio
from typing import Any, Dict

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def _extract_text_content(res: Any) -> str:
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


async def main() -> None:
    base_url = os.getenv("TEST_MCP_URL", os.getenv("MCP_URL", "http://127.0.0.1:8010/mcp"))
    async with streamablehttp_client(base_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            csv = "x,y\n1,2\n2,4\n3,9\n"
            r = await session.call_tool("store_data", {"data": csv, "file_name": "ci_data.csv"})
            handle = json.loads(await _extract_text_content(r))["file_handle"]

            code = (
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "df = pd.read_csv('/tmp/data.csv')\n"
                "plt.figure(figsize=(4,3))\n"
                "plt.plot(df['x'], df['y'], marker='o')\n"
                "plt.title('Embed Check')\n"
                "import os\n"
                "os.makedirs('output', exist_ok=True)\n"
                "plt.savefig('output/chart_embed.png', dpi=120)\n"
                "plt.close()\n"
            )
            ci_res = await session.call_tool("code_interpreter", {"file_handle": handle, "code": code})
            ci = json.loads(await _extract_text_content(ci_res))
            artifacts = ci.get("artifacts") or []
            assert artifacts, f"No artifacts returned from code_interpreter: {ci}"

            md = "# CI Embed Test\n\nBelow should be a chart.\n\n"
            gen = await session.call_tool("generate_pdf_report", {"markdown_content": md, "chart_handles": artifacts})
            gen_payload = json.loads(await _extract_text_content(gen))
            fh = gen_payload.get("file_handle")
            assert fh, "No file_handle returned from generate_pdf_report"

            pdf_resp = await session.call_tool("retrieve_data", {"file_handle": fh})
            pdf_text = await _extract_text_content(pdf_resp)
            embedded = ("/Image" in pdf_text) or ("PNG" in pdf_text) or ("IDAT" in pdf_text)

            print(json.dumps({
                "artifacts_count": len(artifacts),
                "pdf_handle": fh,
                "embedded_detected": embedded
            }))


if __name__ == "__main__":
    asyncio.run(main())
