import os
import json
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

            handle = "Image_20250910_220812_404.jpeg"
            
            print("🔍 Testing with debug output enabled")
            md = "# Server Log Test\n\nThis should show debug messages in server console.\n\n"
            
            gen = await session.call_tool("generate_pdf_report", {
                "markdown_content": md, 
                "chart_handles": [handle]
            })
            result = json.loads(await _extract_text_content(gen))
            
            print(f"PDF generated: {result.get('success')} - {result.get('file_handle')}")
            
            if result.get('success'):
                # Check the PDF size
                pdf_res = await session.call_tool("retrieve_data", {"file_handle": result.get('file_handle')})
                pdf_payload = json.loads(await _extract_text_content(pdf_res))
                
                if pdf_payload.get('success'):
                    pdf_size = len(pdf_payload.get('data', ''))
                    print(f"PDF size: {pdf_size:,} bytes")
                    
                    # Check if HTML contains our image
                    pdf_content = pdf_payload.get('data', '')
                    if 'data:image/jpeg;base64,' in pdf_content:
                        print("✅ Found base64 image data in PDF!")
                        # Count how many base64 images
                        count = pdf_content.count('data:image/jpeg;base64,')
                        print(f"   Found {count} base64 image(s)")
                    else:
                        print("❌ No base64 image data found")
                        
                    if 'DEBUG: Image' in pdf_content:
                        print("✅ Found debug message in PDF")
                    else:
                        print("❌ No debug message found")


if __name__ == "__main__":
    asyncio.run(main())
