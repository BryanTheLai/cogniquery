import os
import json
import base64
import asyncio
from typing import Any

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

            png_b64 = (
                "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAQCAYAAABAfUp8AAAAIElEQVR4nO3OsQkAIBDDwLz/0aKZQzBxVwzXl6gL" 
                "gV0HqQh4r0iVJQAAAP//AwC7M9YtAAAAAElFTkSuQmCC"
            )
            png_bytes = base64.b64decode(png_b64)
            latin1_str = png_bytes.decode('latin1')
            r = await session.call_tool("store_data", {"data": latin1_str, "file_name": "embed_chart.png"})
            payload = json.loads(await _extract_text_content(r))
            handle = payload["file_handle"]

            md = "# Embed Test\n\nBelow should be an image.\n\n"

            gen = await session.call_tool("generate_pdf_report", {"markdown_content": md, "chart_handles": [handle]})
            gen_payload = json.loads(await _extract_text_content(gen))
            fh = gen_payload.get("file_handle")
            assert fh, "No file_handle returned from generate_pdf_report"

            pdf_resp = await session.call_tool("retrieve_data", {"file_handle": fh})
            pdf_text = await _extract_text_content(pdf_resp)

            # Heuristic check: embedded PNG bytes should include PNG signature or /Image in PDF
            success = ("/Image" in pdf_text) or ("PNG" in pdf_text) or ("IDAT" in pdf_text)
            print(json.dumps({
                "generate_success": bool(fh),
                "embedded_heuristic": success,
                "file_handle": fh,
            }))


if __name__ == "__main__":
    asyncio.run(main())
