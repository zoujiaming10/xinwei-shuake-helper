import sys,queue
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import Engine
from playwright.sync_api import sync_playwright
folder=Path(__file__).resolve().parent/'tmp'/'test_auto_open_catalog';folder.mkdir(parents=True,exist_ok=True)
html='''<div>课件PDF</div><button id="toc">目录</button><aside id="drawer" style="display:none"><h3>目录</h3><ul><li data-id="doc" class="el-menu-item is-active">课件</li><li data-id="video" class="el-menu-item">视频14 分21秒</li></ul></aside><script>
window.toggles=0;window.navigations=0;document.querySelector('#toc').onclick=()=>{toggles++;let d=document.querySelector('#drawer');d.style.display=d.style.display==='none'?'block':'none'};
document.querySelector('[data-id=video]').onclick=()=>{navigations++;document.querySelector('.is-active').classList.remove('is-active');document.querySelector('[data-id=video]').classList.add('is-active');const v=document.createElement('video');document.body.append(v);Object.defineProperty(v,'readyState',{get:()=>2});Object.defineProperty(v,'paused',{get:()=>false});};</script>'''
with sync_playwright() as p:
 b=p.chromium.launch(channel='msedge',headless=True);ctx=b.new_context();ctx.route('https://learn.example.test/**',lambda r:r.fulfill(content_type='text/html; charset=utf-8',body=html))
 page=ctx.new_page();page.goto('https://learn.example.test/student/#/courseInfo/learn/courseWare/course/video/doc');e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.command('start',None)
 e.scan();assert page.evaluate('toggles')==1
 e.scan();assert len(e.courses)==2;e.step();assert page.evaluate('navigations')==1
 e.scan();e.step();assert e.pending is None
 for _ in range(3):e.scan();e.step()
 assert page.evaluate('toggles')==1 and page.evaluate('navigations')==1
 print('PASS screenshot: closed drawer -> automatic open -> detect plain 课件 -> skip to video; no repeated toggle')
 page.locator('#toc').click();e.scan();assert page.evaluate('toggles')==3
 print('PASS manually collapsed drawer reopens while continuous playback needs the directory')
 e.pool.shutdown(wait=False);page.close()
 page=ctx.new_page();page.goto('https://learn.example.test/student/#/courseInfo/learn/courseWare/c/video/d')
 page.evaluate("()=>{document.querySelector('#toc').onclick=()=>{window.toggles++;setTimeout(()=>document.querySelector('#drawer').style.display='block',600)}}")
 e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.running=True
 for _ in range(4):e.scan()
 assert page.evaluate('toggles')==1;page.wait_for_timeout(650);e.scan();assert len(e.courses)==2
 print('PASS delayed drawer mount waits without reopening/closing it');e.pool.shutdown(wait=False);page.close()
 page=ctx.new_page();page.goto('https://learn.example.test/homework');e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.running=True;e.scan();assert page.evaluate('toggles')==0
 print('PASS homework page never auto-clicks unrelated catalog buttons');e.pool.shutdown(wait=False);page.close()
 page=ctx.new_page();page.goto('https://learn.example.test/student/#/courseInfo/learn/courseWare/c/video/d')
 page.evaluate("()=>{const old=document.querySelector('#toc'),div=document.createElement('div');div.id='toc';div.innerHTML='<i></i><span>目录</span>';div.onclick=old.onclick;old.replaceWith(div)}")
 e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.running=True;e.scan();assert page.evaluate('toggles')==1;e.scan();assert len(e.courses)==2
 print('PASS styled div/span catalog entry opens');e.pool.shutdown(wait=False);page.close()
 page=ctx.new_page();page.goto('https://learn.example.test/student/#/courseInfo/learn/courseWare/c/video/d')
 page.evaluate("()=>{let second=document.querySelector('#toc').cloneNode(true);second.removeAttribute('id');document.body.append(second)}")
 e=Engine(folder,queue.Queue());e.ctx=ctx;e.page=page;e.running=True;e.scan();assert page.evaluate('toggles')==0
 print('PASS ambiguous catalog entries are not clicked');e.pool.shutdown(wait=False);b.close()
print('6 auto-catalog regression groups passed')
