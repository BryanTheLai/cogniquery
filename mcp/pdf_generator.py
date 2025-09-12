# src/cogniquery/mcps/pdf_generator.py
import os
import base64
from weasyprint import HTML, CSS
from markdown_it import MarkdownIt

from .base import FileHandleOutput, PdfInput, RetrieveDataInput
from .secure_file_storage import retrieve_data, store_data, StoreDataInput

def generate_pdf_report(input_data: PdfInput) -> FileHandleOutput:
    """
    Generates a professional PDF report from markdown content and chart images.
    It takes markdown text and a list of file handles for charts, combines them,
    and returns a file handle to the final PDF.
    """
    try:
        md = MarkdownIt()
        # Use raw HTML if provided, otherwise render markdown
        if getattr(input_data, "html_content", None):
            html_content = input_data.html_content
        else:
            html_content = md.render(input_data.markdown_content)
    except Exception as e:
        return FileHandleOutput(success=False, error_message=f"Markdown parsing error: {str(e)}", file_handle="")
    
    # Embed charts into the HTML by replacing placeholders
    chart_counter = 0
    for chart_handle in input_data.chart_handles:
        retrieve_input = RetrieveDataInput(file_handle=chart_handle)
        retrieved_chart = retrieve_data(retrieve_input)
        if retrieved_chart.success:
            try:
                # Determine file extension to get proper MIME type
                file_extension = chart_handle.split('.')[-1].lower()
                if file_extension == 'svg':
                    mime_type = 'image/svg+xml'
                    # For SVG, decode from latin1 back to proper SVG text
                    svg_data = retrieved_chart.data.encode('latin1').decode('utf-8') if hasattr(retrieved_chart.data, 'encode') else retrieved_chart.data
                    img_tag = f'<div class="chart-image">{svg_data}</div>'
                else:
                    # For PNG/JPG images, they're stored as base64
                    mime_type = f'image/{file_extension}'
                    # The data should already be base64 from storage
                    img_tag = f'<img src="data:{mime_type};base64,{retrieved_chart.data}" style="max-width: 100%; height: auto; margin: 20px 0; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" class="chart-image">'
                
                # Replace chart placeholders in the content
                placeholder_patterns = [
                    '<div class="chart-placeholder">',
                    '[Interactive line chart showing',
                    '[Pie chart showing',
                    '[Interactive chart showing',
                    '📊 **Revenue Trend Chart**',
                    '🥧 **Market Share Distribution**',
                    '🗺️ **Global Revenue Distribution Map**',
                    '⚡ **System Performance Dashboard**'
                ]
                
                # Find and replace the FIRST AVAILABLE placeholder (not just when chart_counter == 0)
                placeholder_replaced = False
                for pattern in placeholder_patterns:
                    if pattern in html_content and not placeholder_replaced:
                        # Replace the entire placeholder div with the actual image
                        start_idx = html_content.find(pattern)
                        if pattern == '<div class="chart-placeholder">':
                            end_idx = html_content.find('</div>', start_idx) + 6
                            html_content = html_content[:start_idx] + img_tag + html_content[end_idx:]
                        else:
                            # For text patterns, replace just the text with image
                            end_idx = html_content.find(']', start_idx) + 1
                            if end_idx > start_idx:
                                html_content = html_content[:start_idx] + img_tag + html_content[end_idx:]
                        placeholder_replaced = True
                        break
                
                # If no placeholder found, append at the end of charts section
                if not placeholder_replaced:
                    charts_section = "## Key Findings"
                    charts_idx = html_content.find(charts_section)
                    if charts_idx != -1:
                        insert_point = html_content.find("\n", charts_idx + len(charts_section))
                        html_content = html_content[:insert_point] + f"\n\n{img_tag}\n" + html_content[insert_point:]
                    else:
                        # Fallback: add after first h2
                        h2_idx = html_content.find("<h2>")
                        if h2_idx != -1:
                            next_section = html_content.find("</h2>", h2_idx) + 5
                            html_content = html_content[:next_section] + f"\n{img_tag}\n" + html_content[next_section:]
                
                chart_counter += 1
                
            except Exception as e:
                # If image embedding fails, add a placeholder message
                error_msg = f'<div class="chart-error">Chart {chart_handle} could not be displayed: {str(e)}</div>'
                html_content += error_msg

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
        h1 { font-size: 24px; color: #1a1a1a; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
        h2 { font-size: 20px; color: #2c3e50; border-bottom: 2px solid #e74c3c; padding-bottom: 8px; }
        h3 { font-size: 16px; color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
        
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
            height: 2px;
            background: linear-gradient(to right, #3498db, #e74c3c, #f39c12);
            margin: 2em 0;
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
        # Generate PDF bytes using WeasyPrint
        pdf_bytes = HTML(string=html_content).write_pdf(stylesheets=[css])
        
        # Store the PDF as raw binary data (not base64)
        # We'll store it as a binary string by encoding it properly
        pdf_store_input = StoreDataInput(data=pdf_bytes.decode('latin1'), file_name="final_report.pdf")
        store_output = store_data(pdf_store_input)

        if not store_output.success:
            return FileHandleOutput(success=False, error_message="Failed to store final PDF report.")
            
        return FileHandleOutput(success=True, file_handle=store_output.file_handle)

    except Exception as e:
        return FileHandleOutput(success=False, error_message=f"PDF generation failed: {e}")
