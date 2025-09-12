import base64
import tempfile
import os
from weasyprint import HTML, CSS

def test_weasyprint_data_uri():
    """Test WeasyPrint with different sized data URIs to find limits"""
    
    # Create test images of different sizes
    test_cases = [
        ("small", b"small test data" * 100),  # ~1.3KB
        ("medium", b"medium test data" * 10000),  # ~150KB  
        ("large", b"large test data" * 100000),  # ~1.5MB (similar to user's image)
    ]
    
    for name, data in test_cases:
        b64_data = base64.b64encode(data).decode('ascii')
        
        html = f'''
        <html>
        <head><title>Test {name}</title></head>
        <body>
            <h1>WeasyPrint Data URI Test - {name.upper()}</h1>
            <p>Data size: {len(data):,} bytes</p>
            <p>Base64 size: {len(b64_data):,} chars</p>
            <img src="data:image/png;base64,{b64_data}" style="max-width: 100px; height: 50px; background: red;" />
            <p>Image should appear above (red background if broken)</p>
        </body>
        </html>
        '''
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                HTML(string=html).write_pdf(tmp.name)
                pdf_size = os.path.getsize(tmp.name)
                print(f"✅ {name}: Data={len(data):,}B, PDF={pdf_size:,}B")
                os.unlink(tmp.name)
        except Exception as e:
            print(f"❌ {name}: Failed - {e}")

def test_actual_jpeg():
    """Test with actual JPEG header to see if format matters"""
    # Minimal valid JPEG header + some data
    jpeg_data = bytes.fromhex('ffd8ffe000104a46494600010101004800480000ffdb004300') + b"fake jpeg data" * 1000
    b64_data = base64.b64encode(jpeg_data).decode('ascii')
    
    html = f'''
    <html>
    <body>
        <h1>JPEG Test</h1>
        <p>JPEG size: {len(jpeg_data):,} bytes</p>
        <img src="data:image/jpeg;base64,{b64_data}" style="max-width: 200px;" />
    </body>
    </html>
    '''
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            HTML(string=html).write_pdf(tmp.name)
            pdf_size = os.path.getsize(tmp.name)
            print(f"✅ JPEG test: Data={len(jpeg_data):,}B, PDF={pdf_size:,}B")
            os.unlink(tmp.name)
    except Exception as e:
        print(f"❌ JPEG test failed: {e}")

if __name__ == "__main__":
    print("🔍 Testing WeasyPrint data URI limits...")
    test_weasyprint_data_uri()
    print("\n🔍 Testing with JPEG format...")
    test_actual_jpeg()
