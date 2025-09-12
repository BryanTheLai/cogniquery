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

            # First, create some test charts using code interpreter
            print("Creating test charts...")
            code = """
import matplotlib.pyplot as plt
import numpy as np

# Create first chart
fig, ax = plt.subplots(figsize=(10, 6))
segments = ['Consumer', 'Corporate', 'Home Office']
regions = ['Southeast Asia', 'North Asia', 'South Asia']
discounts = [17.96, 15.36, 12.37]

bars = ax.bar(range(len(discounts)), discounts, color=['#FF6B6B', '#4ECDC4', '#45B7D1'])
ax.set_xlabel('Customer Segments')
ax.set_ylabel('Average Discount (%)')
ax.set_title('Average Discount by Segment and Region')
ax.set_xticks(range(len(discounts)))
ax.set_xticklabels([f'{s}\\n{r}' for s, r in zip(segments, regions)])

plt.tight_layout()
plt.savefig('output/average_discount_by_segment_region.png', dpi=300, bbox_inches='tight')
plt.close()

# Create second chart
fig, ax = plt.subplots(figsize=(10, 6))
orders = [243, 259, 128]

bars = ax.bar(range(len(orders)), orders, color=['#FF9F43', '#10AC84', '#EE5A24'])
ax.set_xlabel('Customer Segments')
ax.set_ylabel('Total Orders')
ax.set_title('Total Orders by Segment and Region')
ax.set_xticks(range(len(orders)))
ax.set_xticklabels([f'{s}\\n{r}' for s, r in zip(segments, regions)])

plt.tight_layout()
plt.savefig('output/total_orders_by_segment_region.png', dpi=300, bbox_inches='tight')
plt.close()

print("Charts created successfully!")
"""
            
            exec_res = await session.call_tool("code_interpreter", {"code": code})
            exec_payload = json.loads(await _extract_text_content(exec_res))
            
            print(f"Code execution success: {exec_payload.get('success')}")
            print(f"Artifacts created: {exec_payload.get('artifacts', [])}")
            
            if exec_payload.get('success') and exec_payload.get('artifacts'):
                # Now test PDF generation with the original chart handles from agent
                chart_handles = [
                    "output/average_discount_by_segment_region.png",
                    "output/total_orders_by_segment_region.png"
                ]
                
                markdown_content = """# Executive Report

**TLDR (Quantitative):** Consumers in Southeast Asia receive the highest average discounts (17.96%), while Corporate customers in North Asia have the lowest (9.37%). Home Office in South Asia has the lowest total orders (128).

### Key Findings:
*   **Highest Discounts in Southeast Asian Consumer Market:** Consumers in Southeast Asia are currently receiving the most aggressive average discounts (17.96%).
*   **Lowest Discounts for North Asian Corporate Clients:** Corporate customers in North Asia experience the lowest average discounts (9.37%).

### Supporting Evidence:
The analysis reveals distinct patterns in discount rates and order volumes across various customer segments and geographical regions.
"""
                
                print(f"\nTesting PDF generation with resolved chart handles...")
                gen_res = await session.call_tool("generate_pdf_report", {
                    "markdown_content": markdown_content,
                    "chart_handles": chart_handles
                })
                gen_payload = json.loads(await _extract_text_content(gen_res))
                
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
                            print("✅ Large PDF - charts successfully embedded!")
                        else:
                            print("❌ Small PDF - charts not embedded")
                    else:
                        print(f"Failed to retrieve PDF: {pdf_payload.get('error_message')}")
            else:
                print("Failed to create test charts")


if __name__ == "__main__":
    asyncio.run(main())
