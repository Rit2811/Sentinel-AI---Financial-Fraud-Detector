import markdown
import os
import subprocess

md_path = r'c:\Users\siddh\OneDrive\Desktop\sentinal-ai\docs\EVALUATOR_PRESENTATION_GUIDE.md'
html_path = r'c:\Users\siddh\OneDrive\Desktop\sentinal-ai\docs\presentation_guide.html'
pdf_path = r'c:\Users\siddh\OneDrive\Desktop\sentinal-ai\docs\Sentinel_AI_Evaluator_Presentation_Guide.pdf'

with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace mermaid fenced block with a styled placeholder note for clean PDF rendering
text = text.replace('```mermaid', '```text\n[Architecture Workflow Diagram]')

body_html = markdown.markdown(text, extensions=['tables', 'fenced_code'])

styled_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sentinel AI — Evaluator Presentation & Live Simulation Guide</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

  @page {{
    size: A4;
    margin: 18mm 16mm 18mm 16mm;
    @bottom-right {{
      content: counter(page);
      font-size: 9pt;
      font-family: 'Inter', sans-serif;
      color: #64748b;
    }}
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #ffffff;
    line-height: 1.6;
    font-size: 10.5pt;
    margin: 0;
    padding: 0;
  }}

  h1 {{
    font-size: 22pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 3px solid #3b82f6;
    padding-bottom: 8px;
    margin-top: 0;
    margin-bottom: 12px;
  }}

  h2 {{
    font-size: 15pt;
    font-weight: 700;
    color: #1e3a8a;
    border-bottom: 1.5px solid #e2e8f0;
    padding-bottom: 6px;
    margin-top: 24px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }}

  h3 {{
    font-size: 12pt;
    font-weight: 600;
    color: #0f172a;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }}

  p, li {{
    color: #334155;
    margin-top: 4px;
    margin-bottom: 8px;
  }}

  blockquote {{
    margin: 12px 0;
    padding: 10px 16px;
    background: #f0fdf4;
    border-left: 4px solid #10b981;
    color: #065f46;
    font-style: italic;
    border-radius: 4px;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0;
    font-size: 9pt;
    page-break-inside: avoid;
  }}

  th {{
    background: #0f172a;
    color: #ffffff;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #0f172a;
  }}

  td {{
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    vertical-align: top;
  }}

  tr:nth-child(even) {{
    background: #f8fafc;
  }}

  code {{
    font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
    font-size: 9pt;
    background: #f1f5f9;
    color: #0f172a;
    padding: 2px 5px;
    border-radius: 3px;
    border: 1px solid #e2e8f0;
  }}

  pre {{
    background: #0f172a;
    color: #f8fafc;
    padding: 12px 14px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 8.5pt;
    line-height: 1.45;
    margin: 10px 0;
    page-break-inside: avoid;
  }}

  pre code {{
    background: transparent;
    color: #38bdf8;
    padding: 0;
    border: none;
  }}

  ul, ol {{
    padding-left: 20px;
    margin-top: 4px;
    margin-bottom: 8px;
  }}

  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 20px 0;
  }}

  strong {{
    color: #0f172a;
  }}

  .header-badge {{
    display: inline-block;
    padding: 3px 8px;
    background: #eff6ff;
    color: #2563eb;
    border-radius: 4px;
    font-size: 8.5pt;
    font-weight: 600;
    margin-right: 6px;
    margin-bottom: 8px;
    border: 1px solid #bfdbfe;
  }}
</style>
</head>
<body>
<div style="margin-bottom: 16px;">
  <span class="header-badge">OFFICIAL EVALUATOR RUNBOOK</span>
  <span class="header-badge">PATENT CLAIMS 1–6</span>
  <span class="header-badge">DOCKER MICROSERVICES</span>
  <span class="header-badge">SUB-15MS INFERENCE</span>
</div>
{body_html}
</body>
</html>
"""

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(styled_html)

print("HTML generated successfully at:", html_path)
