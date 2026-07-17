import json
import re

# Read motorcycle quiz json data
with open(r"c:\Users\WS293\OneDrive\桌面\Antigravity\無人機測驗題庫WEBAPP\motorcycle_quiz_data.json", "r", encoding="utf-8") as f:
    quiz_data = json.load(f)
    
quiz_json_str = json.dumps(quiz_data, ensure_ascii=False, indent=4)

# Read index.html
html_path = r"c:\Users\WS293\OneDrive\桌面\Antigravity\無人機測驗題庫WEBAPP\index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

# We want to inject: const motorcycleDatabase = [ ... ];
# Right before "const database = ["
inject_marker = "const database = ["
replacement = f"const motorcycleDatabase = {quiz_json_str};\n\n{inject_marker}"

# Clean up previous motorcycleDatabase definition if exists
if "const motorcycleDatabase = [" in html_content:
    # Remove old definition
    html_content = re.sub(r'const motorcycleDatabase = [\s\S]+?;\n\nconst database = \[', 'const database = [', html_content)

if inject_marker in html_content:
    # Inject new database definition
    html_content = html_content.replace(inject_marker, replacement)
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Successfully injected motorcycleDatabase into index.html!")
else:
    print("Error: Could not find const database definition in index.html!")
