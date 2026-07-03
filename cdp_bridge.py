"""
CDP Bridge Client — connects Windows Chrome CDP to Linux server
Usage on Windows: python cdp_bridge.py
"""
import asyncio, json, websockets, base64

SERVER_IP = "76.13.18.146"
SERVER_PORT = 5099
import urllib.request
# Auto-detect CDP WebSocket URL
def get_cdp_url():
    try:
        resp = urllib.request.urlopen("http://localhost:9222/json/version", timeout=5)
        data = json.loads(resp.read())
        return data["webSocketDebuggerUrl"]
    except Exception as e:
        print(f"❌ Cannot connect to Chrome CDP: {e}")
        print("   Make sure Chrome is running with --remote-debugging-port=9222")
        exit(1)

CDP_URL = get_cdp_url()
print(f"🔗 CDP URL: {CDP_URL}")

async def cdp_command(ws, cmd):
    """Send CDP command and wait for result"""
    cid = int(asyncio.get_event_loop().time() * 1000)
    cmd["id"] = cid
    await ws.send(json.dumps(cmd))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == cid:
            return resp.get("result", resp)

async def main():
    print("🔵 Connecting to Chrome CDP...")
    async with websockets.connect(CDP_URL, max_size=2**30) as cdp:
        print("✅ Chrome CDP connected!")
        
        # Get targets
        targets = await cdp_command(cdp, {"method": "Target.getTargets"})
        print(f"   Tabs open: {len(targets.get('targetInfos', []))}")
        
        # If no tab, open one
        tabs = [t for t in targets.get('targetInfos', []) if t['type'] == 'page']
        if not tabs:
            result = await cdp_command(cdp, {"method": "Target.createTarget", 
                "params": {"url": "about:blank"}})
            print(f"   Created new tab: {result.get('targetId', '?')}")
            tab_id = result.get('targetId')
        else:
            tab_id = tabs[0]['targetId']
            print(f"   Using tab: {tab_id}")
        
        # Connect to Hermes server
        print(f"\n🔵 Connecting to Hermes at {SERVER_IP}:{SERVER_PORT}...")
        reader, writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)
        print("✅ Connected! Waiting for commands...")
        
        while True:
            line = await reader.readline()
            if not line:
                break
            cmd = json.loads(line.decode())
            action = cmd.get("action", "")
            print(f">>> {action}")
            result = {"ok": True}
            
            if action == "status":
                result.update({"url": "chrome", "title": "CDP Connected"})
                
            elif action == "navigate":
                r = await cdp_command(cdp, {"method": "Page.navigate",
                    "params": {"url": cmd["url"]}, "targetId": tab_id})
                # Wait for page load
                await asyncio.sleep(3)
                result["url"] = cmd["url"]
                
            elif action == "screenshot":
                try:
                    # Need to attach to tab first
                    session_id = None
                    r = await cdp_command(cdp, {"method": "Target.attachToTarget",
                        "params": {"targetId": tab_id, "flatten": True}})
                    session_id = r.get("sessionId")
                    
                    r = await cdp_command(cdp, {"method": "Page.captureScreenshot",
                        "params": {"format": "png"}, "sessionId": session_id})
                    result["image_base64"] = r.get("data", "")
                    
                    await cdp_command(cdp, {"method": "Target.detachFromTarget",
                        "params": {"targetId": tab_id, "sessionId": session_id}})
                except Exception as e:
                    result["error"] = str(e)
                    
            elif action == "click_text":
                # Use JS to click element by text
                js = f"""
                var els = document.querySelectorAll('button, a, span, div');
                for(var e of els) {{
                    if(e.textContent.trim().includes({json.dumps(cmd.get('text',''))})) {{
                        e.click(); return 'clicked';
                    }}
                }}
                return 'not found';
                """
                r = await cdp_command(cdp, {"method": "Runtime.evaluate",
                    "params": {"expression": js}, "targetId": tab_id})
                result["clicked"] = r.get("result", {}).get("value", "?")
                
            elif action == "evaluate":
                r = await cdp_command(cdp, {"method": "Runtime.evaluate",
                    "params": {"expression": cmd.get("js","")}, "targetId": tab_id})
                result["result"] = r.get("result", {})
                
            elif action == "type":
                await cdp_command(cdp, {"method": "Input.insertText",
                    "params": {"text": cmd.get("text","")}, "targetId": tab_id})
                
            elif action == "press":
                key = cmd.get("key", "Enter")
                key_map = {"Enter": 13, "Tab": 9, "Escape": 27}
                kc = key_map.get(key, 13)
                await cdp_command(cdp, {"method": "Input.dispatchKeyEvent",
                    "params": {"type": "keyDown", "windowsVirtualKeyCode": kc}, "targetId": tab_id})
                await cdp_command(cdp, {"method": "Input.dispatchKeyEvent",
                    "params": {"type": "keyUp", "windowsVirtualKeyCode": kc}, "targetId": tab_id})
                
            elif action == "wait":
                await asyncio.sleep(cmd.get("seconds", 3))
                
            elif action == "stop":
                break
            
            writer.write((json.dumps(result) + "\n").encode())
            await writer.drain()

    writer.close()
    print("❌ Disconnected")

asyncio.run(main())
