import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "platform" / "extractor"))
import config
from master_aconex_extractor import ensure_login

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(config.PROFILE_DIR),
        headless=True,
        viewport={'width': 1920, 'height': 1080}
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    ensure_login(page, ctx)

    # 1. Inspect Document Search Sidebar
    print("\n--- NAVIGATING TO DOCUMENT SEARCH ---")
    page.goto(config.URL_DOCUMENTS, timeout=90000)
    time.sleep(8)
    frame = page.frame(name="main")
    if frame:
        doc_dump = frame.evaluate('''() => {
            // Find all elements with text containing "Document type group" or "My Searches"
            const results = [];
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                const text = (el.innerText || '').trim();
                if (text.includes('Document type group') || text === 'My Searches') {
                    results.push({
                        tag: el.tagName,
                        id: el.id,
                        className: el.className,
                        text: text.slice(0, 80),
                        html: el.outerHTML.slice(0, 200),
                        parentTag: el.parentElement ? el.parentElement.tagName : '',
                        parentId: el.parentElement ? el.parentElement.id : '',
                        parentClass: el.parentElement ? el.parentElement.className : ''
                    });
                }
            }
            return results;
        }''')
        print(f"Document sidebar elements found: {len(doc_dump)}")
        for r in doc_dump[:10]:
            print(f"  [{r['tag']}] id='{r['id']}' class='{r['className']}' | parent: [{r['parentTag']}] id='{r['parentId']}' class='{r['parentClass']}'")
            print(f"    text: {r['text']}")
            print(f"    html: {r['html']}\n")

    # 2. Inspect Mail Search Sidebar
    print("\n--- NAVIGATING TO MAIL SEARCH ---")
    page.goto(config.URL_MAILS, timeout=90000)
    time.sleep(8)
    m_frame = page.frame(name="main")
    if m_frame:
        mail_dump = m_frame.evaluate('''() => {
            const results = [];
            const all = Array.from(document.querySelectorAll('*'));
            for (const el of all) {
                const text = (el.innerText || '').trim();
                if (text.includes('DP01 Respond to SCR') || text.includes('DP01 SCR') || text.includes('Letters Airport')) {
                    results.push({
                        tag: el.tagName,
                        id: el.id,
                        className: el.className,
                        text: text.slice(0, 80),
                        html: el.outerHTML.slice(0, 200),
                        parentTag: el.parentElement ? el.parentElement.tagName : '',
                        parentClass: el.parentElement ? el.parentElement.className : ''
                    });
                }
            }
            return results;
        }''')
        print(f"Mail sidebar elements found: {len(mail_dump)}")
        for r in mail_dump[:10]:
            print(f"  [{r['tag']}] id='{r['id']}' class='{r['className']}' | parent: [{r['parentTag']}] class='{r['parentClass']}'")
            print(f"    text: {r['text']}")
            print(f"    html: {r['html']}\n")

    ctx.close()
