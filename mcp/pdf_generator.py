# src/cogniquery/mcps/pdf_generator.py
import os
import base64
import tempfile
import time
from weasyprint import HTML, CSS
from markdown_it import MarkdownIt

from .base import FileHandleOutput, PdfInput, RetrieveDataInput
from .secure_file_storage import retrieve_data, store_data, StoreDataInput
from .secure_file_storage import STORAGE_DIR  # for auto-discovery
from pathlib import Path
import json

def generate_pdf_report(input_data: PdfInput) -> FileHandleOutput:
    """
    Generates a professional PDF report from markdown content and chart images.
    It takes markdown text and a list of file handles for charts, combines them,
    and returns a file handle to the final PDF.
    """
    try:
        # Enable table support for markdown rendering
        md = MarkdownIt().enable('table')
        # Use raw HTML if provided, otherwise render markdown
        if getattr(input_data, "html_content", None):
            html_content = input_data.html_content
        else:
            html_content = md.render(input_data.markdown_content)
    except Exception as e:
        return FileHandleOutput(success=False, error_message=f"Markdown parsing error: {str(e)}", file_handle="")
    
    # Normalize chart_handles: accept list or JSON-encoded string
    try:
        if isinstance(input_data.chart_handles, str):
            try:
                parsed = json.loads(input_data.chart_handles)
                if isinstance(parsed, list):
                    input_data.chart_handles = parsed
                else:
                    input_data.chart_handles = []
            except Exception:
                parts = [p.strip() for p in input_data.chart_handles.split(',') if p.strip()]
                input_data.chart_handles = parts
    except Exception:
        input_data.chart_handles = []

    # If no chart handles provided, auto-discover recent chart images stored locally
    if not getattr(input_data, "chart_handles", None):
        try:
            p: Path = STORAGE_DIR  # type: ignore
            candidates = []
            for ext in (".png", ".jpg", ".jpeg"):
                for f in p.glob(f"*{ext}"):
                    candidates.append((f.stat().st_mtime, f.name))
            candidates.sort(reverse=True)
            input_data.chart_handles = [name for _, name in candidates[:10]]
        except Exception:
            input_data.chart_handles = []

    # Build a mapping of chart filenames to absolute file paths
    # This allows us to replace inline image references in the HTML
    import re
    chart_path_mapping = {}
    
    for chart_handle in input_data.chart_handles:
        # Extract the base filename (without UUID prefix if present)
        # e.g., "abc123_my_chart.png" -> look for "my_chart.png" references
        chart_filename = chart_handle
        
        # Also check if this is a UUID-prefixed filename
        # Pattern: "uuid_originalname.png"
        parts = chart_handle.split('_', 1)
        if len(parts) == 2:
            possible_original = parts[1]  # e.g., "quarterly_profit_margin_trend.png"
            chart_path_mapping[possible_original] = chart_handle
        
        # Also map the full handle
        chart_path_mapping[chart_filename] = chart_handle
    
    # Replace inline image references in HTML with absolute file paths
    # The markdown renderer creates <img src="filename.png" alt="..." />
    # We need to replace src="filename.png" with src="file:///absolute/path/filename.png"
    
    def replace_img_src(match):
        full_match = match.group(0)
        src_content = match.group(1)
        
        # Extract just the filename (remove any path prefix)
        filename = src_content.split('/')[-1]
        
        # Check if we have a mapping for this filename
        chart_handle = None
        if filename in chart_path_mapping:
            chart_handle = chart_path_mapping[filename]
        else:
            # Try to find a partial match
            for mapped_name, handle in chart_path_mapping.items():
                if filename in handle or handle.endswith(filename):
                    chart_handle = handle
                    break
        
        if chart_handle:
            # Resolve to absolute file path
            chart_path = STORAGE_DIR / chart_handle
            if chart_path.exists():
                abs_path = str(chart_path.resolve()).replace('\\', '/')
                return f'<img src="file:///{abs_path}" class="chart-image" style="max-width: 100%; height: auto; margin: 20px auto; border-radius: 8px; display: block;" '
            else:
                return f'<div class="chart-error">Chart {filename} not found in storage</div><img '
        else:
            # Chart not found in our mapping - leave original reference
            return full_match
    
    # Replace all <img src="..."> tags
    html_content = re.sub(r'<img src="([^"]+)"', replace_img_src, html_content)

    # Enhanced CSS for professional styling
    css = CSS(string='''
        @page { 
            size: A4; 
            margin: 0.75in;
            counter-increment: page;
            @bottom-right {
                content: "Page " counter(page);
                font-family: Arial, sans-serif;
                font-size: 10px;
                color: #666;
            }
        }
        
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11px;
            line-height: 1.4;
            color: #333;
            margin: 0;
            padding: 0;
        }
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 { 
            color: #2c3e50; 
            font-weight: 600;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            page-break-after: avoid;
        }
        h1 { 
            font-size: 18px; 
            color: #0f4c81; 
            text-align: center;
            border-bottom: none;
            padding-bottom: 10px;
            margin-bottom: 0.3em;
            font-weight: 700;
        }
        h2 { 
            font-size: 14px; 
            color: #0f4c81; 
            border-bottom: 2px solid #333; 
            padding-bottom: 8px;
            margin-top: 1.8em;
            font-weight: 700;
        }
        h3 { 
            font-size: 14px; 
            color: #34495e; 
            font-weight: 600;
            margin-top: 1.2em;
        }
        
        /* Tables */
        table { 
            border-collapse: collapse; 
            width: 100%; 
            margin: 1em 0;
            font-size: 10px;
            page-break-inside: avoid;
        }
        
        th, td { 
            border: 1px solid #ddd; 
            padding: 8px; 
            text-align: left;
            vertical-align: top;
        }
        
        th { 
            background-color: #3498db; 
            color: white;
            font-weight: bold;
            text-align: center;
        }
        
        /* Alternate row colors */
        tbody tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        tbody tr:nth-child(odd) {
            background-color: white;
        }
        
        /* Data table specific styling */
        .data-table th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 9px;
            letter-spacing: 0.5px;
        }
        
        /* Images */
        img { 
            page-break-inside: avoid; 
            max-width: 100%; 
            height: auto;
            display: block;
            margin: 1em auto;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 4px;
        }
        
        /* Chart images */
        .chart-image {
            width: 100%;
            max-width: 600px;
            height: auto;
            margin: 20px auto;
            display: block;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            page-break-inside: avoid;
        }
        
        .chart-error {
            width: 100%;
            padding: 20px;
            background-color: #fee;
            border: 2px solid #f88;
            border-radius: 8px;
            color: #d00;
            text-align: center;
            margin: 20px 0;
            font-style: italic;
        }
        
        /* Chart placeholders */
        .chart-placeholder { 
            width: 100%; 
            height: 250px; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border: 2px dashed #3498db; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            margin: 1.5em 0;
            font-size: 14px;
            color: #2c3e50;
            border-radius: 8px;
            font-weight: 500;
            page-break-inside: avoid;
        }
        
        /* KPI Grid */
        .kpi-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 20px 0;
            page-break-inside: avoid;
        }
        
        .kpi-card {
            flex: 1;
            min-width: 120px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        .kpi-value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .kpi-label {
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        
        .kpi-change {
            font-size: 11px;
            font-weight: 600;
        }
        
        .kpi-change.positive {
            color: #2ecc71;
        }
        
        /* Header styling */
        .header {
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            margin: -0.75in -0.75in 30px -0.75in;
            page-break-after: avoid;
        }
        
        .logo-placeholder {
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 10px;
            letter-spacing: 2px;
        }
        
        .report-title {
            font-size: 22px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .report-subtitle {
            font-size: 14px;
            opacity: 0.9;
        }
        
        /* Footer styling */
        .footer {
            margin-top: 40px;
            padding: 20px;
            background-color: #ecf0f1;
            border-top: 3px solid #3498db;
            font-size: 10px;
            color: #7f8c8d;
            text-align: center;
            page-break-inside: avoid;
        }
        
        .footer-content {
            line-height: 1.6;
        }
        
        /* Paragraphs and lists */
        p { 
            margin: 0.5em 0; 
            text-align: justify;
        }
        
        ul, ol { 
            margin: 0.5em 0; 
            padding-left: 20px;
        }
        
        li {
            margin: 0.3em 0;
        }
        
        /* Horizontal rules */
        hr {
            border: none;
            height: 1px;
            background-color: #333;
            margin: 1.5em 0;
        }
        
        /* Italic text for timestamps */
        em {
            color: #666;
            font-style: italic;
            font-size: 11px;
        }
        
        /* Center text for timestamps */
        p > em:only-child {
            display: block;
            text-align: center;
            margin: 0.5em 0 1.5em 0;
        }
        
        /* Code blocks */
        pre, code {
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 10px;
            border-left: 4px solid #3498db;
            margin: 1em 0;
            page-break-inside: avoid;
        }
        
        /* Blockquotes */
        blockquote {
            border-left: 4px solid #3498db;
            margin: 1em 0;
            padding-left: 15px;
            font-style: italic;
            color: #555;
        }
        
        /* Links */
        a {
            color: #3498db;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        /* Strong emphasis */
        strong, b {
            font-weight: 600;
            color: #2c3e50;
        }
        
        /* Page breaks */
        .page-break {
            page-break-before: always;
        }
        
        /* Avoid orphans and widows */
        h1, h2, h3, h4, h5, h6 {
            page-break-after: avoid;
        }
        
        p, li {
            orphans: 2;
            widows: 2;
        }
    ''')

    try:
        # Generate the PDF using WeasyPrint
        pdf_bytes = HTML(string=html_content).write_pdf(stylesheets=[css])
        
        # Store the PDF and return the file handle (convert bytes to latin1 string for storage)
        pdf_data_str = pdf_bytes.decode('latin1')
        pdf_store_input = StoreDataInput(data=pdf_data_str, file_name="final_report.pdf")
        pdf_result = store_data(pdf_store_input)
        
        return FileHandleOutput(
            success=pdf_result.success, 
            file_handle=pdf_result.file_handle, 
            error_message=pdf_result.error_message
        )
    except Exception as e:
        return FileHandleOutput(success=False, error_message=f"PDF generation error: {str(e)}", file_handle="")
    finally:
        # Clean up temporary chart files from secure storage
        try:
            for file_path in STORAGE_DIR.glob("temp_chart_*.png"):
                if file_path.stat().st_mtime < (time.time() - 300):  # Clean files older than 5 minutes
                    file_path.unlink()
            for file_path in STORAGE_DIR.glob("temp_chart_*.jpg"):
                if file_path.stat().st_mtime < (time.time() - 300):
                    file_path.unlink()
            for file_path in STORAGE_DIR.glob("temp_chart_*.jpeg"):
                if file_path.stat().st_mtime < (time.time() - 300):
                    file_path.unlink()
        except Exception:
            pass  # Ignore cleanup errors
