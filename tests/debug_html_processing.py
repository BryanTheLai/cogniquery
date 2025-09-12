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
            
            print("🔍 Testing different HTML structures for image placement")
            
            # Test 1: Simple markdown with no placeholders - should trigger fallback insertion
            print("\n📝 Test 1: Simple markdown (should use fallback insertion)")
            md1 = "# Test Report\n\nThis is a simple test.\n\n## Results\n\nSome content here."
            gen1 = await session.call_tool("generate_pdf_report", {
                "markdown_content": md1, 
                "chart_handles": [handle]
            })
            result1 = json.loads(await _extract_text_content(gen1))
            print(f"   Result: {result1.get('success')} - {result1.get('file_handle')}")
            
            # Test 2: Markdown with placeholder pattern
            print("\n📝 Test 2: Markdown with placeholder pattern")
            md2 = "# Test Report\n\n[Interactive chart showing data trends]\n\n## Analysis\n\nMore content."
            gen2 = await session.call_tool("generate_pdf_report", {
                "markdown_content": md2, 
                "chart_handles": [handle]
            })
            result2 = json.loads(await _extract_text_content(gen2))
            print(f"   Result: {result2.get('success')} - {result2.get('file_handle')}")
            
            # Test 3: Direct HTML with explicit image tag
            print("\n📝 Test 3: Direct HTML with image")
            # Get the image data first
            retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
            retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
            
            if retrieve_payload.get('success'):
                data = retrieve_payload.get('data', '')
                import base64
                raw_bytes = data.encode('latin1')
                b64_data = base64.b64encode(raw_bytes).decode('ascii')
                
                html3 = f'''
                <h1>Direct HTML Test</h1>
                <p>Testing direct image embedding:</p>
                <img src="data:image/jpeg;base64,{b64_data}" style="max-width: 100%; height: auto;" />
                <p>End of test.</p>
                '''
                
                gen3 = await session.call_tool("generate_pdf_report", {
                    "markdown_content": "",
                    "html_content": html3,
                    "chart_handles": []  # No chart handles since we're embedding directly
                })
                result3 = json.loads(await _extract_text_content(gen3))
                print(f"   Result: {result3.get('success')} - {result3.get('file_handle')}")
                
                # Check the size of this PDF
                if result3.get('success'):
                    pdf_res = await session.call_tool("retrieve_data", {"file_handle": result3.get('file_handle')})
                    pdf_payload = json.loads(await _extract_text_content(pdf_res))
                    if pdf_payload.get('success'):
                        pdf_size = len(pdf_payload.get('data', ''))
                        print(f"   PDF size: {pdf_size:,} bytes")
                        if pdf_size > 100000:
                            print("   ✅ Large PDF - image likely embedded!")
                        else:
                            print("   ❌ Small PDF - image not embedded")


if __name__ == "__main__":
    asyncio.run(main())
