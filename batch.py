"""Batch homework UI state machine. Does not use private learning-service APIs."""
import hashlib,json,re,time
from pathlib import Path

CARD = r'''button=>{
const clean=text=>text.replace(/\s+/g,' ').trim().replace(/^(?:非考核点|考核点)\s*/, '').trim();
const titleLike=text=>text&&!/^(?:题目数量|题目数|关联章节|开放时间|截止时间|作业剩余重做次数|剩余重做次数|做作业|开始作业|继续作答|仅查看考核点作业|未完成|待批改|已完成)(?:\s|[:：]|$)/.test(text);
let card=button;
for(let i=0;i<9&&card;i++,card=card.parentElement){
 let t=card.innerText||'',matches=[...t.matchAll(/题目数量\s*[:：]?\s*(\d+)/g)];
 if(matches.length>1)return null; // Never merge neighboring cards into one task.
 if(matches.length!==1)continue;
 let titles=[...card.querySelectorAll('h2,h3,h4,[class*="title"],[class*="name"]')].map(e=>clean(e.innerText)).filter(titleLike);
 let lines=t.split('\n').map(clean).filter(Boolean);
 let title=titles[0]||(titleLike(lines[0])?lines[0]:null);
 if(!title)continue; // Metadata/footer may be a separate child below the header.
 return {title,total:Number(matches[0][1]),closed:/已截止|未开放|已提交|待批改|已完成/.test(t),text:t.slice(0,800)};
}return null;}'''

class BatchRunner:
    def __init__(self,engine):
        self.e=engine;self.active=False;self.state='idle';self.list_page=None;self.item=None;self.answered=set();self.done=set();self.scanned=set();self.confirmed=False
        self.paused=False;self.completed=0
    def can_answer(self):return not self.paused and (not self.active or self.state=='answer')
    def stop(self):
        self.active=False;self.paused=False;self.state='idle';self.e.auto=False;self.e.answer_transition=None
        self.e.emit('batch_state',False);self.e.emit('auto_state',False)
        self.e.emit('batch_controls','idle')
    def pause(self,message='已手动暂停批量作业'):
        if not self.active:return
        self.paused=True;self.active=False;self.saved_transition=self.e.answer_transition
        self.e.auto=False;self.e.answer_transition=None;self.e.generation+=1
        self.e.emit('auto_state',False);self.e.emit('batch_state',False);self.e.emit('batch_controls','paused')
        self.report(message+'；保留进度，可点击“继续”')
    def resume(self):
        if not self.paused:return self.e.log('没有可继续的批量任务，请先从列表开始')
        if self.e.future:return self.e.log('当前API请求尚未结束，请稍后再点击继续')
        if self.state in ('answer','submit','settling'):
            if not getattr(self,'work_page',None) or self.work_page.is_closed():return self.e.log('原作业页已关闭，不能继续；请停止后从列表重新开始')
            identity=lambda url: re.search(r'(?:[?&])homeworkPaperId=([^&#]+)',url).group(1) if re.search(r'(?:[?&])homeworkPaperId=([^&#]+)',url) else url.split('?')[0]
            if identity(self.work_page.url)!=identity(self.work_url):return self.e.log('作业页面已变化，不能恢复旧任务；请停止后重新开始')
            self.e.page=self.work_page
        self.paused=False;self.active=True;self.at=time.monotonic();self.next_poll=0
        self.dialog_error=None
        self.e.question_seen=None;self.e.handled.clear();self.e.auto=self.state=='answer'
        old=getattr(self,'saved_transition',None)
        if self.state=='answer' and old and old.get('clicked'):
            old.update(epoch=self.e.generation,at=time.monotonic());self.e.answer_transition=old
        self.e.emit('auto_state',self.e.auto);self.e.emit('batch_controls','running');self.e.emit('batch_state',True)
        self.report('已继续批量任务：'+(self.item['title'] if self.item else '作业列表'))
    def fail(self,message):
        if self.active:return self.pause('批量作业已暂停：'+message)
        self.stop();self.e.auto=False;self.e.generation+=1;self.e.answer_transition=None
        self.e.emit('auto_state',False);self.report('批量作业未启动：'+message)
    def report(self,message):self.e.emit('batch_status',message);self.e.log(message)
    def items(self,page):
        items=[];button_count=0
        for frame in page.frames:
            buttons=frame.get_by_text('做作业',exact=True).filter(visible=True)
            button_count+=buttons.count()
            for i in range(buttons.count()):
                button=buttons.nth(i)
                if not button.is_enabled():continue
                info=button.evaluate(CARD)
                if info and not info['closed'] and info['total']>0:
                    info['key']=hashlib.sha256((self.list_url+'|'+info['title']+'|'+str(info['total'])).encode()).hexdigest()
                    info['button']=button;items.append(info)
        if len({item['key'] for item in items})!=len(items):raise ValueError('存在同名同题数作业，无法唯一识别')
        self.last_scan={'buttons':button_count,'recognized':len(items)}
        return items
    def start(self):
        if self.active or self.paused:return self.e.log('已有批量任务，请使用暂停/继续，或停止后重新开始')
        if self.e.future:return self.fail('当前API请求尚未结束，请等待后再启动')
        if not self.e.ctx or not self.e.page or self.e.page.is_closed():return self.fail('请先打开本课程“我的作业 → 未完成”列表')
        self.list_page=self.e.page;self.list_url=self.list_page.url
        if not self.list_page.get_by_text('我的作业',exact=True).filter(visible=True).count():return self.fail('请在上方选择截图中的“我的作业”列表标签页')
        incomplete=self.list_page.get_by_text('未完成',exact=True).filter(visible=True)
        if incomplete.count()!=1:return self.fail('无法唯一定位“未完成”分类')
        incomplete.click(timeout=2500)
        self.active=True;self.state='list';self.at=time.monotonic();self.next_poll=0;self.scanned=set();self.scan_seen=set();self.done=set();self.completed=0
        self.e.auto=False;self.e.running=False;self.e.generation+=1;self.e.answer_transition=None
        self.e.emit('batch_state',True);self.e.emit('auto_state',False)
        self.e.emit('batch_controls','running')
        self.e.emit('batch_progress',(0,0,0,'等待作业'))
        self.report('批量模式已开启：自动答题、自动交卷、切换下一份未完成作业；API调用没有每日上限')
    def record(self,q):
        if self.active and self.state=='answer':
            from engine import question_key
            key=json.dumps([q['id'],question_key(q)],ensure_ascii=False)
            self.answered.add(key)
            self.e.emit('batch_progress',(len(self.answered),self.item['total'],self.completed,self.item['title']))
            self.e.emit('batch_status',f'当前作业：{self.item["title"]}｜已确认 {len(self.answered)}/{self.item["total"]} 题｜本轮提交 {self.completed} 份')
    def at_last_question(self):return self.active and self.state=='answer' and len(self.answered)==self.item['total']
    def submit(self):
        if not self.at_last_question():return self.fail(f'题数未核对完整：已确认{len(self.answered)}题，作业共{self.item["total"]}题，不交卷')
        self.e.auto=False;self.e.emit('auto_state',False)
        buttons=self.e.page.get_by_role('button',name=re.compile(r'^\s*提交作业\s*$')).filter(visible=True)
        if buttons.count()!=1 or not buttons.first.is_enabled():return self.fail('未找到唯一可用的“提交作业”按钮')
        self.success_before=bool(re.search(r'提交成功|交卷成功|作业已提交|已成功提交',self.e.page.locator('body').inner_text()))
        self.state='submit';self.at=time.monotonic();self.confirmed=False;self.dialog_error=None
        buttons.first.click(timeout=3000);self.report('全部题目已填写，已点击提交作业；等待提交确认')
    def dialog(self,dialog):
        if not self.active or self.state!='submit':dialog.dismiss();return
        message=dialog.message
        if re.search(r'未答|漏答|未完成|未填写',message) or not re.search(r'提交|交卷',message):
            dialog.dismiss();self.dialog_error='提交弹窗存在未答提示或未知内容，请手动检查';return
        dialog.accept();self.confirmed=True
    def first_question(self,page,total):
        headings=page.get_by_text('作业答题卡',exact=True).filter(visible=True)
        if headings.count()==1:
            scope=headings.first
            for _ in range(6):
                scope=scope.locator('..')
                one=scope.get_by_text('1',exact=True).filter(visible=True)
                if one.count()==1:
                    one.click(timeout=2500);return True
        found=self.e.get_question()
        return bool(total==1 and found or found and (found[1].get('position')==1 or re.match(r'^\s*1[.、．]',found[1]['title'])))
    def tick(self):
        if not self.active or time.monotonic()<getattr(self,'next_poll',0):return
        self.next_poll=time.monotonic()+.25
        try:
            if self.state=='list':
                if time.monotonic()-self.at<.8:return
                if self.list_page.is_closed():return self.fail('作业列表页已关闭')
                self.e.page=self.list_page
                items=self.items(self.list_page);self.scan_seen.update(i['key'] for i in items);pending=[i for i in items if i['key'] not in self.done]
                if pending:
                    self.item=pending[0];self.answered=set();self.before_pages=set(self.e.ctx.pages)
                    self.e.emit('batch_progress',(0,self.item['total'],self.completed,self.item['title']))
                    self.list_page.on('dialog',self.dialog) if not getattr(self,'bound_list',False) else None;self.bound_list=True
                    self.state='opening';self.at=time.monotonic();self.item['button'].click(timeout=3000)
                    self.report('正在打开：'+self.item['title']);return
                # Known list scaffold is required; an empty loading screen is not completion.
                body=self.list_page.locator('body').inner_text(timeout=2000)
                if not items and not re.search(r'共\s*0\s*条|暂无作业|暂无数据|没有作业',body):
                    if time.monotonic()-self.at>15:return self.fail(f'检测到{self.last_scan["buttons"]}个“做作业”按钮，但未识别出有效卡片或空列表；请导出诊断')
                    return
                next_page=self.list_page.locator('.el-pagination .btn-next').filter(visible=True)
                if not next_page.count():next_page=self.list_page.get_by_role('button',name='下一页',exact=True).filter(visible=True)
                enabled=next_page.count()==1 and next_page.first.is_enabled() and not next_page.first.evaluate('e=>!!e.closest(\'[disabled],[aria-disabled="true"],.is-disabled\')')
                if enabled:
                    signature=tuple(i['key'] for i in items)
                    if signature in self.scanned:return self.fail('作业分页未变化，已停止防止循环')
                    self.scanned.add(signature);next_page.first.click(timeout=2500);self.at=time.monotonic();return
                count=re.search(r'共\s*(\d+)\s*条',body)
                if count and int(count[1])>len(self.scan_seen):return self.fail('列表显示仍有更多作业，但未识别到可用分页；未宣告全部完成')
                self.e.auto=False;self.e.emit('auto_state',False);self.stop()
                self.report(f'当前课程的“未完成”列表已处理完毕，本轮确认提交 {self.completed} 份');return
            if self.state=='opening':
                new_pages=[p for p in self.e.ctx.pages if p not in self.before_pages and not p.is_closed()]
                if len(new_pages)>1:return self.fail('打开了多个页面，无法确定作业页')
                page=new_pages[0] if new_pages else self.list_page;self.e.page=page
                self.work_page=page;self.work_url=page.url
                found=self.e.get_question()
                if not found:
                    if time.monotonic()-self.at>20:return self.fail('20秒内未识别到作业题目')
                    return
                if not self.first_question(page,self.item['total']):return self.fail('无法确认从第1题开始，不执行自动交卷')
                if page is not self.list_page:page.on('dialog',self.dialog)
                self.state='settling';self.at=time.monotonic();return
            if self.state=='settling':
                if time.monotonic()-self.at<.8:return
                if not self.e.get_question():return self.fail('第1题未加载')
                self.state='answer';self.e.question_seen=None;self.e.handled.clear();self.e.auto=True
                self.e.cfg['next_question']=True;self.e.emit('auto_state',True)
                self.report('开始自动完成：'+self.item['title']);return
            if self.state=='submit':
                if self.dialog_error:return self.fail(self.dialog_error)
                page=self.e.page;body=page.locator('body').inner_text(timeout=2000)
                success=bool(re.search(r'提交成功|交卷成功|作业已提交|已成功提交',body))
                if not success:self.success_before=False
                if success and not self.success_before:
                    self.done.add(self.item['key']);self.completed+=1
                    self.e.emit('batch_progress',(len(self.answered),self.item['total'],self.completed,self.item['title']))
                    from engine import atomic_json
                    atomic_json(self.e.folder/'batch-last-run.json',{'confirmed_submissions':list(self.done),'count':self.completed})
                    self.report('已确认提交：'+self.item['title'])
                    if page is not self.list_page:page.close()
                    self.e.page=self.list_page;self.list_page.goto(self.list_url,wait_until='domcontentloaded',timeout=20000)
                    incomplete=self.list_page.get_by_text('未完成',exact=True).filter(visible=True)
                    if incomplete.count()==1:incomplete.click(timeout=2500)
                    self.state='list';self.at=time.monotonic();self.scanned=set();self.scan_seen=set();return
                dialogs=page.locator('.el-message-box,.el-dialog,[role="dialog"],[role="alertdialog"]').filter(visible=True)
                # One visible dialog may match both an outer role wrapper and an
                # inner Element panel. Count innermost panels, not nested matches.
                indices=dialogs.evaluate_all('(nodes)=>nodes.map((node,i)=>({node,i})).filter(x=>!nodes.some(other=>other!==x.node&&x.node.contains(other))).map(x=>x.i)')
                if indices:
                    if len(indices)!=1:return self.fail('存在多个独立弹窗，请先处理无关弹窗再点击继续')
                    dialog=dialogs.nth(indices[0]);text=dialog.inner_text()
                    if re.search(r'未答|漏答|未完成|未填写',text):return self.fail('平台提示仍有未答内容，未继续提交')
                    if not re.search(r'提交|交卷',text):return self.fail('出现未知确认弹窗')
                    if not self.confirmed:
                        buttons=dialog.get_by_role('button',name=re.compile(r'^\s*(确定|确认|提交|提交作业|交卷|确定提交|确认提交|确认交卷)\s*$')).filter(visible=True)
                        if buttons.count()!=1:return self.fail('无法唯一确定提交确认按钮')
                        buttons.first.click(timeout=2500);self.confirmed=True
                if time.monotonic()-self.at>20:return self.fail('未确认提交成功，已停止；不会重复交卷')
        except Exception as exc:self.fail(str(exc)[:240])
