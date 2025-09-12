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

            # The user-provided handle (file name only, no path)
            handle = "Image_20250910_220812_404.jpeg"
            md = "# Image Embed Test\n\nBelow is the provided image.\n\n"
            gen = await session.call_tool("generate_pdf_report", {"markdown_content": md, "chart_handles": [handle]})
            payload = json.loads(await _extract_text_content(gen))
            print(json.dumps(payload))


if __name__ == "__main__":
    asyncio.run(main())
