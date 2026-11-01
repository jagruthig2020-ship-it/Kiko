from pathlib import Path
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1365,'height':850})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.evaluate('''
      window.fetch = async (url, opts={}) => {
        if (String(url).includes('/api/status')) return new Response(JSON.stringify({phase:'idle',task:'',model_ready:true,hotkey:true,revision:0,progress:{completions:0}}),{status:200,headers:{'Content-Type':'application/json'}});
        if (String(url).includes('/api/start')) return new Response(JSON.stringify({ok:true,message:'Opening Windows Settings. KIKO will point automatically'}),{status:200,headers:{'Content-Type':'application/json'}});
        return new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}});
      };
    ''')
    page.set_content((Path(__file__).resolve().parents[1]/'index.html').read_text(encoding='utf-8'),wait_until='domcontentloaded')
    page.locator('#task').fill('Turn on Bluetooth')
    page.locator('#start').click()
    page.wait_for_timeout(550)
    assert 'KIKO will point automatically' in page.locator('#result').inner_text()
    assert page.locator('#task').input_value()=='Turn on Bluetooth'
    page.locator('[data-lang="te"]').click()
    assert 'మీరు ఏం' in page.locator('#questionTitle').inner_text()
    page.locator('#task').fill('Bluetooth ఆన్ చేయాలి')
    page.locator('#start').click()
    page.wait_for_timeout(550)
    assert 'KIKO will point automatically' in page.locator('#result').inner_text()
    page.screenshot(path=str(Path(__file__).resolve().parent/'desktop_preview.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_timeout(150)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'), 'Horizontal overflow mobile'
    page.screenshot(path=str(Path(__file__).resolve().parent/'mobile_preview.png'),full_page=True)
    assert not errors,errors
    browser.close()
    print('Browser smoke checks passed: auto-guidance text, English/Telugu, layout, no JS errors')
