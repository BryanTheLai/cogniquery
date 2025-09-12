import asyncio
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def extract_text_content(res) -> str:
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

async def main():
    base_url = os.getenv("TEST_MCP_URL", "http://127.0.0.1:8010/mcp")
    print(f"Connecting to {base_url}")

    async with streamablehttp_client(base_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Simple CSV
            csv_data = "x,y\n1,2\n2,3\n3,5\n4,7\n5,11\n"
            print("Storing CSV via store_data ...")
            store_res = await session.call_tool("store_data", {"data": csv_data, "file_name": "ci_test.csv"})
            store_txt = await extract_text_content(store_res)
            print("store_data response:", store_txt)
            try:
                store_payload = json.loads(store_txt)
            except Exception:
                print("ERROR: Could not parse store_data response JSON")
                return
            if not store_payload.get("success"):
                print("ERROR: store_data failed:", store_payload)
                return
            fh = store_payload.get("file_handle")
            if not fh:
                print("ERROR: No file_handle returned from store_data")
                return

            code = (
                "import pandas as pd\n"
                "import matplotlib.pyplot as plt\n"
                "df = pd.read_csv('/tmp/data.csv')\n"
                "fig, ax = plt.subplots(figsize=(6,4))\n"
                "ax.plot(df['x'], df['y'], marker='o')\n"
                "ax.set_title('Smoke Test Chart')\n"
                "ax.set_xlabel('x')\n"
                "ax.set_ylabel('y')\n"
                "plt.savefig('output/chart_1.png', dpi=150, bbox_inches='tight')\n"
                "plt.close()\n"
                "print('Chart saved as chart_1.png')\n"
            )

            print("Calling code_interpreter ...")
            ci_res = await session.call_tool("code_interpreter", {"code": code, "file_handle": fh})
            ci_txt = await extract_text_content(ci_res)
            print("code_interpreter response:\n", ci_txt)

if __name__ == "__main__":
    asyncio.run(main())
