import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.pdf_generator import generate_pdf_report
from mcp.base import PdfInput

def test_direct_call():
    """Test PDF generation by calling the function directly"""
    
    # Test with the user's image handle
    handle = "Image_20250910_220812_404.jpeg"
    
    md_content = "# Direct Call Test\n\nThis should embed the image below:\n\n"
    
    input_data = PdfInput(
        markdown_content=md_content,
        chart_handles=[handle]
    )
    
    print(f"🔍 Testing direct call to generate_pdf_report")
    print(f"   Chart handles: {input_data.chart_handles}")
    
    result = generate_pdf_report(input_data)
    
    print(f"   Success: {result.success}")
    print(f"   File handle: {result.file_handle}")
    print(f"   Error: {result.error_message}")
    
    if result.success and result.file_handle:
        # Check the generated PDF size
        from mcp.secure_file_storage import retrieve_data, RetrieveDataInput
        
        pdf_retrieve = retrieve_data(RetrieveDataInput(file_handle=result.file_handle))
        if pdf_retrieve.success:
            pdf_size = len(pdf_retrieve.data)
            print(f"   PDF size: {pdf_size:,} bytes")
            
            if pdf_size > 100000:
                print("   ✅ Large PDF - image likely embedded!")
            else:
                print("   ❌ Small PDF - image not embedded")
        else:
            print(f"   ❌ Failed to retrieve PDF: {pdf_retrieve.error_message}")

if __name__ == "__main__":
    test_direct_call()
