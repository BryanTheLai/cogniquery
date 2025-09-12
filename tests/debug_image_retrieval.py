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
            
            # Test retrieval directly
            retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
            retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
            
            print(f"Retrieve success: {retrieve_payload.get('success')}")
            print(f"Error message: {retrieve_payload.get('error_message')}")
            
            if retrieve_payload.get('success'):
                data = retrieve_payload.get('data', '')
                print(f"Data length: {len(data)}")
                print(f"First 50 chars: {repr(data[:50])}")
                
                # Check if it looks like binary data encoded as latin1
                if data and len(data) > 10:
                    try:
                        # Try to decode back to bytes
                        binary_data = data.encode('latin1')
                        print(f"Binary data length: {len(binary_data)}")
                        print(f"First 20 bytes: {binary_data[:20].hex()}")
                        
                        # Check for JPEG signature
                        if binary_data.startswith(b'\xff\xd8\xff'):
                            print("✓ Valid JPEG signature detected")
                        else:
                            print("✗ No JPEG signature found")
                    except Exception as e:
                        print(f"Error converting to binary: {e}")


if __name__ == "__main__":
    asyncio.run(main())
