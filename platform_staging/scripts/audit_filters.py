import re

with open('platform/backend/static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

with open('platform/backend/static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

pattern = re.compile(r'<(select|input)[^>]*id=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
matches = pattern.findall(html)

filter_elements = []
for tag, el_id in matches:
    if any(k in el_id.lower() for k in ['filter', 'search', 'date', 'select', 'status', 'pkg', 'proj']):
        filter_elements.append((tag, el_id))

print(f"{'Element ID':<30} | {'HTML Handler':<25} | {'Found in app.js?'}")
print("-" * 75)

for tag, el_id in sorted(set(filter_elements)):
    # Check if element has an inline onchange or oninput in HTML
    el_match = re.search(r'id=["\']' + re.escape(el_id) + r'["\'][^>]*', html)
    handler = "None"
    if el_match:
        tag_str = el_match.group(0)
        h_match = re.search(r'(on(?:change|input|click)=["\'][^"\']+["\'])', tag_str)
        if h_match:
            handler = h_match.group(1)
        else:
            # check before id
            pre_match = re.search(r'<[^>]*' + re.escape(el_id) + r'[^>]*>', html)
            if pre_match:
                h2 = re.search(r'(on(?:change|input|click)=["\'][^"\']+["\'])', pre_match.group(0))
                if h2:
                    handler = h2.group(1)
    
    # Check if referenced in app.js
    in_js = el_id in js
    print(f"{el_id:<30} | {handler:<25} | {'YES' if in_js else 'NO'}")
