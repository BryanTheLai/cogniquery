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

            # Test with the actual chart handles from agent_log.json
            chart_handles = [
                "output/average_discount_by_segment_region.png",
                "output/total_orders_by_segment_region.png"
            ]
            
            print(f"Testing with agent chart handles: {chart_handles}")
            
            # Check if these files exist in secure storage
            for handle in chart_handles:
                retrieve_res = await session.call_tool("retrieve_data", {"file_handle": handle})
                retrieve_payload = json.loads(await _extract_text_content(retrieve_res))
                
                if retrieve_payload.get('success'):
                    data_size = len(retrieve_payload.get('data', ''))
                    print(f"✅ {handle}: {data_size:,} bytes")
                else:
                    print(f"❌ {handle}: {retrieve_payload.get('error_message')}")
            
            # Test PDF generation with real agent content
            markdown_content = """# Executive Report

**TLDR (Quantitative):** Consumers in Southeast Asia receive the highest average discounts (17.96%), while Corporate customers in North Asia have the lowest (9.37%). Home Office in South Asia has the lowest total orders (128).

### Key Findings:
*   **Highest Discounts in Southeast Asian Consumer Market:** Consumers in Southeast Asia are currently receiving the most aggressive average discounts (17.96%).
*   **Lowest Discounts for North Asian Corporate Clients:** Corporate customers in North Asia experience the lowest average discounts (9.37%).

### Supporting Evidence:
The analysis reveals distinct patterns in discount rates and order volumes across various customer segments and geographical regions.
"""
            
            print(f"\nTesting PDF generation with real agent content...")
            gen = await session.call_tool("generate_pdf_report", {
                "markdown_content": markdown_content,
                "chart_handles": chart_handles
            })
            gen_payload = json.loads(await _extract_text_content(gen))
            
            print(f"PDF Success: {gen_payload.get('success')}")
            print(f"PDF Handle: {gen_payload.get('file_handle')}")
            print(f"PDF Error: {gen_payload.get('error_message')}")
            
            if gen_payload.get('success'):
                # Check PDF size
                pdf_res = await session.call_tool("retrieve_data", {"file_handle": gen_payload.get('file_handle')})
                pdf_payload = json.loads(await _extract_text_content(pdf_res))
                
                if pdf_payload.get('success'):
                    pdf_size = len(pdf_payload.get('data', ''))
                    print(f"PDF Size: {pdf_size:,} bytes")
                    
                    if pdf_size > 100000:
                        print("✅ Large PDF - charts likely embedded!")
                    else:
                        print("❌ Small PDF - charts not embedded")


if __name__ == "__main__":
    asyncio.run(main())
