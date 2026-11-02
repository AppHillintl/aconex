import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

extractor_dir = Path(r"c:\Users\bimst\Downloads\ACONEX\platform\extractor")
sys.path.insert(0, str(extractor_dir))
import config

print("=" * 70)
print("ACONEX BROWSER AUTHENTICATION")
print("=" * 70)
print("1. Opening Chrome on your screen...")
print("2. Entering password automatically...")
print("3. If Two-Step Verification (2FA) appears, approve it on your phone")
print("   or enter the passcode and check 'Trust device for 7 days'.")
print("=" * 70)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(config.PROFILE_DIR),
        headless=False,
        viewport={"width": 1400, "height": 900}
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(config.URL_DOCUMENTS, timeout=60000)
    
    # Wait up to 25s for password field to appear
    print("Waiting for password field...")
    try:
        pwd_inp = page.wait_for_selector("input[type='password']", timeout=25000)
        if pwd_inp and pwd_inp.is_visible():
            print("Password field detected. Filling password and clicking Sign In...")
            pwd_inp.fill(config.ACONEX_PASSWORD)
            time.sleep(1)
            btn = page.wait_for_selector("button:has-text('Sign In'), input[value='Sign In']", timeout=5000)
            if btn:
                btn.click()
                print("Sign In clicked!")
    except Exception as e:
        print("Note / Already on next step:", e)
        
    print("\n>>> Please complete 2FA or click Trust on the screen if prompted <<<")
    print("Waiting for Aconex to open (timeout: 180s)...")
    
    authenticated = False
    for s in range(180):
        time.sleep(1)
        cur_url = page.url
        title = page.title()
        # Ensure we are genuinely on mea.aconex.com and NOT an oraclecloud login URL containing mea.aconex.com as parameter
        if cur_url.startswith("https://mea.aconex.com") and "authentication/index.html" not in cur_url:
            print(f"\n[OK] Authenticated successfully on Aconex Hub! URL: {cur_url}")
            authenticated = True
            time.sleep(4)
            break
            
    if authenticated:
        print("\n" + "=" * 70)
        print("SUCCESS! Aconex session is fully authenticated and saved.")
        print("=" * 70)
    else:
        print("\n[WARNING] Did not reach Aconex within 180 seconds. Current URL:", page.url)
        
    ctx.close()
