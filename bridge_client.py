"""
Browser Bridge Client — runs on Windows, connects to server
Usage: python bridge_client.py
"""
import asyncio, json, base64, sys
from playwright.async_api import async_playwright

SERVER_IP = "76.13.18.146"
SERVER_PORT = 5099

async def main():
    print("🔵 Starting browser...")
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)  # VISIBLE!
    page = await browser.new_page()
    await page.set_viewport_size({"width": 1280, "height": 800})
    print("✅ Browser started! Connecting to server...")
    
    reader, writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)
    print(f"✅ Connected to {SERVER_IP}:{SERVER_PORT}!")
    print("⏳ Waiting for commands from Hermes...")
    
    while True:
        try:
            line = await reader.readline()
            if not line:
                print("❌ Server disconnected")
                break
            cmd = json.loads(line.decode())
            action = cmd.get("action", "")
            print(f">>> Command: {action}")
            
            result = {"ok": True}
            
            if action == "screenshot":
                b = await page.screenshot(full_page=False)
                result["image_base64"] = base64.b64encode(b).decode()
                
            elif action == "navigate":
                await page.goto(cmd["url"], wait_until="domcontentloaded", timeout=30000)
                result["url"] = page.url
                result["title"] = await page.title()
                
            elif action == "click_text":
                text = cmd.get("text", "")
                el = page.get_by_text(text, exact=False)
                if await el.count() > 0:
                    await el.first.click()
                    result["clicked"] = text
                else:
                    result["error"] = f"Text '{text}' not found"
                    
            elif action == "click_selector":
                sel = cmd.get("selector", "")
                el = page.locator(sel)
                if await el.count() > 0:
                    await el.first.click()
                    result["clicked"] = sel
                else:
                    result["error"] = f"Selector '{sel}' not found"
                    
            elif action == "type":
                await page.keyboard.type(cmd.get("text", ""), delay=20)
                
            elif action == "fill":
                sel = cmd.get("selector", "input")
                await page.locator(sel).first.fill(cmd.get("text", ""))
                
            elif action == "press":
                await page.keyboard.press(cmd.get("key", "Enter"))
                
            elif action == "evaluate":
                result["result"] = await page.evaluate(cmd.get("js", ""))
                
            elif action == "scroll":
                await page.evaluate(f"window.scrollBy(0, {cmd.get('pixels', 300)})")
                
            elif action == "wait":
                await asyncio.sleep(cmd.get("seconds", 3))
                
            elif action == "status":
                result.update({
                    "url": page.url, 
                    "title": await page.title(),
                    "text": (await page.evaluate("document.body.innerText"))[:2000]
                })
                
            elif action == "stop":
                await browser.close()
                await pw.stop()
                result["closed"] = True
                writer.write((json.dumps(result) + "\n").encode())
                await writer.drain()
                break
            else:
                result = {"error": f"Unknown: {action}"}
            
            writer.write((json.dumps(result) + "\n").encode())
            await writer.drain()
            
        except Exception as e:
            print(f"Error: {e}")
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except:
                break
    
    await browser.close()
    await pw.stop()
    print("Browser closed")

if __name__ == "__main__":
    asyncio.run(main())
