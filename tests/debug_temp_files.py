import os
import json
import asyncio
import tempfile
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
            
            # Get the image data
            retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
            retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
            
            if not retrieve_payload.get('success'):
                print(f"❌ Failed to retrieve image: {retrieve_payload.get('error_message')}")
                return
                
            data = retrieve_payload.get('data', '')
            raw_bytes = data.encode('latin1')
            
            # Create temp file manually and test WeasyPrint directly
            temp_fd, temp_path = tempfile.mkstemp(suffix='.jpeg')
            try:
                with os.fdopen(temp_fd, 'wb') as f:
                    f.write(raw_bytes)
                
                print(f"📁 Created temp file: {temp_path}")
                print(f"📏 Temp file size: {os.path.getsize(temp_path):,} bytes")
                
                # Test WeasyPrint with temp file
                from weasyprint import HTML
                
                file_url = f'file:///{temp_path.replace(os.sep, "/")}'
                print(f"🔗 File URL: {file_url}")
                
                html = f'''
                <html>
                <body>
                    <h1>Temp File Test</h1>
                    <p>Testing with temporary file approach:</p>
                    <img src="{file_url}" style="max-width: 100%; height: auto;" />
                    <p>Image should appear above.</p>
                </body>
                </html>
                '''
                
                # Generate PDF directly
                pdf_temp_fd, pdf_temp_path = tempfile.mkstemp(suffix='.pdf')
                os.close(pdf_temp_fd)  # Close immediately, we'll overwrite
                
                HTML(string=html).write_pdf(pdf_temp_path)
                pdf_size = os.path.getsize(pdf_temp_path)
                
                print(f"📄 Direct WeasyPrint PDF size: {pdf_size:,} bytes")
                
                if pdf_size > 100000:
                    print("✅ Large PDF - temp file approach works!")
                else:
                    print("❌ Small PDF - temp file approach failed")
                
                os.unlink(pdf_temp_path)
                
            finally:
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
