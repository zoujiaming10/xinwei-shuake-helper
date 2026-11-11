import sys,queue,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine
from playwright.sync_api import sync_playwright

folder=Path(__file__).resolve().parent/'tmp'/'test_next_overlay';folder.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    ctx=browser.new_context();ctx.route('https://learn.example.test/**',lambda r:r.fulfill(body='<body></body>',content_type='text/html'))
    def case(html,ended=True):
        e=Engine(folder,queue.Queue());page=ctx.new_page();page.goto('https://learn.example.test/course')
        page.set_content('<video style="width:300px;height:180px"></video>'+html)
        page.evaluate('''ended=>{window.clicks=0;window.testEnded=ended;let v=document.querySelector('video');Object.defineProperty(v,'ended',{get:()=>window.testEnded});Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'paused',{get:()=>false});document.querySelectorAll('button,[role="button"],.fake-button').forEach(e=>e.onclick=()=>window.clicks++);}''',ended)
        e.ctx=ctx;e.page=page;e.running=True;e.scan();return e,page
    def close(e,page):e.pool.shutdown(wait=False);page.close()
    e,page=case('<div id="videoLayer">下一章节：<button>重新观看本节</button><button>观看下一章节</button></div>')
    assert len(e.courses)==0;e.step();assert page.evaluate('clicks')==1 and e.pending
    e.scan();e.step();assert page.evaluate('clicks')==1
    print('PASS screenshot scenario: ended video + zero directory clicks next once')
    page.evaluate("()=>{window.testEnded=false;document.querySelector('video').dispatchEvent(new Event('loadedmetadata'));}")
    e.scan();e.step();assert e.pending is None and e.running
    print('PASS reused video element confirms new metadata rather than old ended state')
    close(e,page)
    e,page=case('<button>观看下一章节</button>',False);e.step();assert page.evaluate('clicks')==0
    print('PASS unfinished video never clicks next');close(e,page)
    e,page=case('<div class="fake-button"><span>观看下一章节</span></div>');e.step();assert page.evaluate('clicks')==1
    print('PASS styled div/span next action');close(e,page)
    e,page=case('<button disabled>观看下一章节</button><button style="display:none">观看下一章节</button>');e.step();assert not e.pending
    print('PASS disabled and hidden actions not clicked');close(e,page)
    e,page=case('<button>观看下一章节</button><button>观看下一章节</button>');e.step();assert not e.running and page.evaluate('clicks')==0
    print('PASS ambiguous duplicates stop without guessing');close(e,page)
    e,page=case('<button>观看下一章节</button>');e.step();target,old,_=e.pending;e.pending=(target,old,time.monotonic()-21);page.locator('video').evaluate('e=>e.remove()');e.scan();e.step();assert not e.running and not e.pending
    print('PASS timeout works even while video element disappears');close(e,page)
    ctx.close();browser.close()
print('7 overlay regression checks passed')
