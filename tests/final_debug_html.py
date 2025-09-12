import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.pdf_generator import generate_pdf_report
from mcp.base import PdfInput
from mcp.secure_file_storage import STORAGE_DIR

def test_html_generation():
    """Debug the HTML generation to see what's actually being passed to WeasyPrint"""
    
    handle = "Image_20250910_220812_404.jpeg"
    
    # Check if file exists
    file_path = STORAGE_DIR / handle
    print(f"Image file exists: {file_path.exists()}")
    if file_path.exists():
        print(f"Image file size: {file_path.stat().st_size:,} bytes")
    
    # Create a simple test that should work
    md_content = "# HTML Debug Test\n\nThis should show an image:\n\n"
    
    # Monkey patch to capture HTML before WeasyPrint processes it
    original_html_init = None
    captured_html = None
    
    def capture_html(self, string=None, **kwargs):
        nonlocal captured_html
        if string:
            captured_html = string
            print(f"\n=== CAPTURED HTML ===")
            print(f"HTML length: {len(string)}")
            if "img src=" in string:
                print("✅ Found img tag in HTML")
                # Find and print the img tag
                start = string.find("<img")
                if start != -1:
                    end = string.find(">", start) + 1
                    img_tag = string[start:end]
                    print(f"Image tag: {img_tag[:200]}...")
            else:
                print("❌ No img tag found in HTML")
            print("===================\n")
        return original_html_init(string=string, **kwargs)
    
    # Patch WeasyPrint HTML class
    from weasyprint import HTML
    original_html_init = HTML.__init__
    HTML.__init__ = capture_html
    
    try:
        input_data = PdfInput(
            markdown_content=md_content,
            chart_handles=[handle]
        )
        
        result = generate_pdf_report(input_data)
        print(f"PDF generation success: {result.success}")
        print(f"Error: {result.error_message}")
        
    finally:
        # Restore original method
        HTML.__init__ = original_html_init

if __name__ == "__main__":
    test_html_generation()
