import sys,queue,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine
from playwright.sync_api import sync_playwright
folder=Path(__file__).resolve().parent/'tmp'/'test_document_navigation';folder.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True);ctx=b.new_context()
 ctx.route('https://learn.example.test/**',lambda r:r.fulfill(body='<body></body>'))
 def setup(html,route='doc'):
  page=ctx.new_page();page.goto('https://learn.example.test/student/#/courseInfo/learn/courseWare/c/video/'+route);page.set_content(html)
  page.evaluate("""()=>{window.clicks=0;window.acceptAt=1;document.querySelectorAll('.el-menu-item').forEach(e=>e.onclick=()=>{if(!e.innerText.startsWith('视频'))return;clicks++;if(clicks<acceptAt)return;document.querySelectorAll('.is-active,[aria-current]').forEach(x=>{x.classList.remove('is-active');x.removeAttribute('aria-current')});e.classList.add('is-active');let v=document.createElement('video');document.body.append(v);Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'paused',{get:()=>false});});}""")
  e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.running=True;e.scan();return e,page
 def cleanup(e,page):e.pool.shutdown(wait=False);page.close()
 e,page=setup('<li class="el-menu-item" data-id="doc"><span aria-current="page">PPT课件</span></li><li class="el-menu-item" data-id="v">视频 1</li>')
 assert e.courses[0][1]['active'];e.step();assert page.evaluate('clicks')==1;e.scan();e.step();assert e.pending is None
 print('PASS selection marker on child element skips document and confirms video');cleanup(e,page)
 e,page=setup('<li class="el-menu-item" data-id="doc">PPT课件</li><li class="el-menu-item" data-id="v">视频 1</li>')
 assert e.courses[0][1]['active'];e.step();assert page.evaluate('clicks')==1
 print('PASS exact route ID identifies current document without row selection class');cleanup(e,page)
 e,page=setup('<li class="el-menu-item is-active" data-id="doc">课件</li><li class="el-menu-item" data-id="v">视频 1</li>')
 page.evaluate('acceptAt=2');e.step();assert page.evaluate('clicks')==1
 e.scan();e.step();assert page.evaluate('clicks')==1
 e.pending=(e.pending[0],e.pending[1],time.monotonic()-3.1);e.step();assert page.evaluate('clicks')==2
 e.scan();e.step();assert e.pending is None and e.running
 print('PASS ignored first click retries after 3 seconds then confirms once');cleanup(e,page)
 e,page=setup('<li class="el-menu-item is-active" data-id="doc">课件</li><li class="el-menu-item" data-id="v">视频 1</li>')
 page.evaluate('acceptAt=99');e.step()
 for _ in range(3):
  if e.pending:e.pending=(e.pending[0],e.pending[1],time.monotonic()-3.1)
  e.scan();e.step()
 assert page.evaluate('clicks')==3 and not e.running and e.pending is None
 print('PASS permanently ignored clicks stop after exactly 3 attempts');cleanup(e,page)
 html='''<style>.el-submenu:not(.is-opened) ul{display:none}</style><ul><li class="el-menu-item is-active" data-id="doc">课件</li><li class="el-submenu"><div class="el-submenu__title" onclick="this.parentElement.classList.add('is-opened')">下一章</div><ul><li class="el-menu-item" data-id="near">视频 近</li></ul></li><li class="el-menu-item" data-id="far">视频 远</li></ul>'''
 e,page=setup(html);e.step();assert page.evaluate('clicks')==0 and page.locator('.is-opened').count()==1
 e.scan();e.chapter_wait=(e.chapter_wait[0],time.monotonic()-3.1);e.step()
 assert page.locator('[data-id=near]').evaluate("e=>e.classList.contains('is-active')")
 e.scan();e.step();assert e.pending is None
 print('PASS collapsed intermediate chapter expands before farther visible video');cleanup(e,page)
 b.close()
print('5 document navigation regression groups passed; no platform/API requests')
