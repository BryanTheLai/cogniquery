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
            
            print("🔍 Step 1: Test image retrieval")
            retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
            retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
            
            if retrieve_payload.get('success'):
                data = retrieve_payload.get('data', '')
                print(f"✅ Image retrieved: {len(data)} bytes")
                
                # Test base64 encoding manually
                try:
                    if isinstance(data, str):
                        raw_bytes = data.encode('latin1')
                        import base64
                        b64_data = base64.b64encode(raw_bytes).decode('ascii')
                        print(f"✅ Base64 encoding successful: {len(b64_data)} chars")
                        print(f"   First 50 chars: {b64_data[:50]}")
                    else:
                        print(f"❌ Data is not string: {type(data)}")
                except Exception as e:
                    print(f"❌ Base64 encoding failed: {e}")
            else:
                print(f"❌ Image retrieval failed: {retrieve_payload.get('error_message')}")
                return
            
            print("\n🔍 Step 2: Test PDF generation with detailed HTML")
            # Create HTML with explicit image tag to see if it gets processed
            html_content = f'''
            <h1>Debug Test</h1>
            <p>Testing image embedding:</p>
            <img src="data:image/jpeg;base64,{b64_data[:100]}..." style="max-width: 100%;" />
            <p>Image handle: {handle}</p>
            '''
            
            gen = await session.call_tool("generate_pdf_report", {
                "markdown_content": "# Debug Test\n\nTesting image embedding.\n\n",
                "html_content": html_content,
                "chart_handles": [handle]
            })
            gen_payload = json.loads(await _extract_text_content(gen))
            
            if gen_payload.get('success'):
                pdf_handle = gen_payload.get('file_handle')
                print(f"✅ PDF generated: {pdf_handle}")
                
                # Check PDF content
                pdf_res = await session.call_tool("retrieve_data", {"file_handle": pdf_handle})
                pdf_payload = json.loads(await _extract_text_content(pdf_res))
                
                if pdf_payload.get('success'):
                    pdf_content = pdf_payload.get('data', '')
                    pdf_size = len(pdf_content)
                    print(f"📄 PDF size: {pdf_size} bytes")
                    
                    # Look for image-related content in PDF
                    if 'data:image' in pdf_content:
                        print("✅ Found data:image in PDF")
                    elif '/Image' in pdf_content:
                        print("✅ Found /Image in PDF")
                    elif b64_data[:20] in pdf_content:
                        print("✅ Found base64 data in PDF")
                    else:
                        print("❌ No image data found in PDF")
                        
                    # Check for error messages
                    if 'could not be encoded' in pdf_content:
                        print("❌ Found encoding error in PDF")
                    if 'could not be displayed' in pdf_content:
                        print("❌ Found display error in PDF")
                        
                else:
                    print(f"❌ PDF retrieval failed: {pdf_payload.get('error_message')}")
            else:
                print(f"❌ PDF generation failed: {gen_payload.get('error_message')}")


if __name__ == "__main__":
    asyncio.run(main())
