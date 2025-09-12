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

            # Test with the user's actual image
            handle = "Image_20250910_220812_404.jpeg"
            
            # First check the image size
            retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
            retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
            
            if not retrieve_payload.get('success'):
                print(f"❌ Failed to retrieve image: {retrieve_payload.get('error_message')}")
                return
                
            image_size = len(retrieve_payload.get('data', ''))
            print(f"📷 Original image size: {image_size:,} bytes ({image_size/1024/1024:.2f} MB)")
            
            # Generate PDF with image
            md = "# Image Embed Validation\n\nThis PDF should contain the embedded image below:\n\n"
            gen = await session.call_tool("generate_pdf_report", {"markdown_content": md, "chart_handles": [handle]})
            gen_payload = json.loads(await _extract_text_content(gen))
            
            if not gen_payload.get('success'):
                print(f"❌ PDF generation failed: {gen_payload.get('error_message')}")
                return
                
            pdf_handle = gen_payload.get('file_handle')
            print(f"✅ PDF generated: {pdf_handle}")
            
            # Check PDF size
            pdf_res = await session.call_tool("retrieve_data", {"file_handle": pdf_handle})
            pdf_payload = json.loads(await _extract_text_content(pdf_res))
            
            if pdf_payload.get('success'):
                pdf_size = len(pdf_payload.get('data', ''))
                print(f"📄 PDF size: {pdf_size:,} bytes ({pdf_size/1024:.2f} KB)")
                
                # Heuristic: PDF with embedded 1.8MB image should be significantly larger than 8KB
                if pdf_size > 100000:  # 100KB threshold
                    print("✅ PDF size suggests image is likely embedded")
                else:
                    print("❌ PDF size too small - image likely not embedded")
                    
                # Check for base64 image data in PDF content
                pdf_content = pdf_payload.get('data', '')
                if '/Image' in pdf_content or 'data:image' in pdf_content:
                    print("✅ Image markers found in PDF content")
                else:
                    print("❌ No image markers found in PDF content")
                    
                print(f"\n📊 Size comparison:")
                print(f"  Image: {image_size:,} bytes")
                print(f"  PDF:   {pdf_size:,} bytes")
                print(f"  Ratio: {pdf_size/image_size*100:.1f}% of original")
            else:
                print(f"❌ Failed to retrieve PDF: {pdf_payload.get('error_message')}")


if __name__ == "__main__":
    asyncio.run(main())
