"""Read only visual elements belonging to the current question, never the desktop."""
import base64, hashlib, io, time
from urllib.parse import urlsplit

VISUAL_HELPERS = r'''
const xwVisible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';
const xwHash=s=>{let h=2166136261;for(let i=0;i<s.length;i++)h=Math.imul(h^s.charCodeAt(i),16777619);return (h>>>0).toString(16)+':'+s.length};
const xwVisuals=(root,options=[])=>{
 if(!root)return [];
 if(!window.__xwDesktopVisuals)window.__xwDesktopVisuals={ids:new WeakMap(),n:0};let state=window.__xwDesktopVisuals;
 return [...root.querySelectorAll('img,canvas,svg,[style*="background-image"]')].filter(e=>xwVisible(e)&&!e.closest('[contenteditable="true"],.w-e-toolbar,.ql-toolbar,[role="toolbar"],.el-radio__input,.el-checkbox__input')&&!e.parentElement?.closest('svg')&&!e.matches('input')).map(e=>{
  if(!state.ids.has(e))state.ids.set(e,'visual-'+(++state.n));let id=state.ids.get(e);e.setAttribute('data-xw-desktop-visual',id);
  let tag=e.tagName.toLowerCase(),content='',ready=true,broken=false;
  if(tag==='img'){let src=e.currentSrc||e.getAttribute('src')||e.getAttribute('srcset')||'';content=src+'|'+e.alt;ready=e.complete&&e.naturalWidth>0;broken=!!src&&e.complete&&!e.naturalWidth&&e.loading!=='lazy'}
  else if(tag==='canvas'){try{content=e.toDataURL()}catch(_){content='tainted:'+e.width+':'+e.height}}
  else if(tag==='svg'){let copy=e.cloneNode(true);copy.removeAttribute('data-xw-desktop-visual');content=copy.outerHTML+'|'+[e,...e.querySelectorAll('*')].map(n=>{let s=getComputedStyle(n);return [s.fill,s.stroke,s.strokeWidth,s.color,s.fontFamily,s.fontSize,s.fontWeight,s.opacity,s.visibility,s.transform,s.clipPath].join(';')}).join('|')}
  else {
   content=getComputedStyle(e).backgroundImage;
   let urls=[...content.matchAll(/url\(["']?(.*?)["']?\)/g)].map(m=>m[1]);
   if(!state.backgrounds)state.backgrounds=new Map();
   for(let url of urls){if(!state.backgrounds.has(url)){let image=new Image();image.src=url;state.backgrounds.set(url,image)}let image=state.backgrounds.get(url);ready=ready&&image.complete&&image.naturalWidth>0;broken=broken||(image.complete&&!image.naturalWidth)}
  }
  const option=options.findIndex(o=>o.contains(e));
  return {id,tag,zone:option<0?'题干':'选项 '+String.fromCharCode(65+option),signature:xwHash(tag+'|'+content),ready,broken,natural_width:tag==='img'?e.naturalWidth:null,natural_height:tag==='img'?e.naturalHeight:null};
 });
};
'''

# Extract a parent question's title and visuals for cross-origin rich text editors.
EXTERNAL_TITLE = '()=>{' + VISUAL_HELPERS + r'''
let titles=[...document.querySelectorAll('.topic-title-box,.topic-title')].filter(xwVisible);
titles=titles.filter(e=>!titles.some(other=>other!==e&&other.contains(e)));
if(titles.length!==1)return null;
let title=titles[0],scope=title.closest('.question-box,.question,.content-area')||title;
let visuals=xwVisuals(scope).map(v=>({...v,parent:true}));
return {title:title.innerText.trim()||(visuals.length?'请根据题干图片作答':''),visuals};
}'''


def capture_images(frame, question):
    """Prefer original image pixels; fall back to a browser-rendered crop."""
    from PIL import Image
    assets=question.get('visuals',[])
    if len(assets)>32:raise ValueError('本题图片超过32张，请手动处理，未请求API')
    images=[];digest=hashlib.sha256();size=0;fetch_until=time.monotonic()+3
    for asset in assets:
        source=frame.parent_frame if asset.get('parent') else frame
        if source is None:raise ValueError('图片所属题目页面已关闭')
        loc=source.locator(f'[data-xw-desktop-visual="{asset["id"]}"]')
        if loc.count()!=1:raise ValueError('题目图片已变化，请重新检测本题')
        box=loc.bounding_box()
        if not box or min(box['width'],box['height'])<1 or max(box['width'],box['height'])>8192 or box['width']*box['height']>12_000_000:
            raise ValueError('题目图片尺寸异常，请手动处理，未请求API')
        raw=None;origin='网页显示图'
        if asset.get('tag')=='img':
            # Canvas draws at naturalWidth/naturalHeight, so CSS thumbnails do
            # not destroy small formula details. Cross-origin images may taint it.
            data=loc.evaluate('''e=>{try{let w=e.naturalWidth,h=e.naturalHeight;if(!w||!h||w*h>12000000||Math.max(w,h)>8192)return null;let c=document.createElement('canvas');c.width=w;c.height=h;c.getContext('2d').drawImage(e,0,0);return c.toDataURL('image/png')}catch(_){return null}}''')
            if data:raw=base64.b64decode(data.split(',',1)[1]);origin='原始分辨率'
            elif time.monotonic()<fetch_until:
                # Uses the browser's matching cookies only, never the API Key.
                url=loc.evaluate('e=>e.currentSrc||e.src')
                if urlsplit(url).scheme in ('http','https'):
                    response=None
                    try:
                        response=source.page.context.request.get(url,timeout=max(100,int((fetch_until-time.monotonic())*1000)),max_redirects=0)
                        if response.ok and int(response.headers.get('content-length','0'))<=12*1024*1024:
                            candidate=response.body()
                            if len(candidate)<=12*1024*1024:
                                with Image.open(io.BytesIO(candidate)) as check:
                                    if check.width*check.height<=12_000_000 and max(check.size)<=8192:raw=candidate;origin='原始分辨率'
                    except Exception:pass
                    finally:
                        if response is not None:response.dispose()
        if raw is None:raw=loc.screenshot(type='png',animations='disabled',caret='hide',scale='css',timeout=3000)
        guard_style=loc.evaluate('e=>{let s=getComputedStyle(e);return [s.filter,s.transform,s.opacity,s.clipPath,s.objectFit,s.objectPosition].join("|")}')
        with Image.open(io.BytesIO(raw)) as original:
            original.load()
            # White background preserves transparent SVG/formula legibility in JPEG.
            rgba=original.convert('RGBA');rgb=Image.new('RGB',rgba.size,'white');rgb.paste(rgba,mask=rgba.getchannel('A'))
            rgb.thumbnail((1600,1600),Image.Resampling.LANCZOS)
            output=io.BytesIO();rgb.save(output,format='PNG');data=output.getvalue();mime='image/png'
            if len(data)>1024*1024:
                output=io.BytesIO();rgb.save(output,format='JPEG',quality=92);data=output.getvalue();mime='image/jpeg'
        size+=len(data)
        if size>12*1024*1024:raise ValueError('本题图片总大小超过12MB，请手动处理，未请求API')
        digest.update(asset['zone'].encode('utf-8'));digest.update(hashlib.sha256(data).digest())
        images.append({'zone':asset['zone'],'url':'data:'+mime+';base64,'+base64.b64encode(data).decode('ascii'),'pixel_guard':asset.get('tag')!='svg','guard_style':guard_style,'origin':origin,'width':rgb.width,'height':rgb.height})
    return images,digest.hexdigest()

def image_guard(images):
    # SVG geometry/text/styles are compared in question_key. Subpixel screenshot
    # rasterization may vary after scrolling, so JPEG byte equality is unsuitable.
    digest=hashlib.sha256()
    for image in images:
        if image.get('pixel_guard',True):digest.update((image['zone']+'|'+image['url']+'|'+image.get('guard_style','')).encode('utf-8'))
    return digest.hexdigest()
