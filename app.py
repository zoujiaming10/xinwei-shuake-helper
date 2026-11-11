import ctypes, os, queue, sys, time, tkinter as tk, webbrowser
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from urllib.parse import urlsplit
from engine import Engine, load_settings, save_settings

class App:
    def __init__(self, root, folder):
        self.root=root; self.folder=folder; self.events=queue.Queue(); self.engine=Engine(folder,self.events)
        root.title('芯位学习助手 · Windows 2.5.6'); root.geometry('980x980'); root.minsize(800,900)
        style=ttk.Style(); style.theme_use('vista'); style.configure('TButton',padding=6); style.configure('TLabel',font=('Microsoft YaHei UI',10))
        self.cfg=load_settings(folder); self.vars={}; self.last_courses=None; self.last_pages=None
        shell=ttk.Frame(root,padding=16); shell.pack(fill='both',expand=True)
        ttk.Label(shell,text='芯位学习助手',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w')
        ttk.Label(shell,text='本程序免费使用',font=('Microsoft YaHei UI',12,'bold'),foreground='#16803c').pack(anchor='w',pady=(4,0))
        ttk.Button(shell,text='创建桌面快捷方式',command=self.shortcut).pack(anchor='e')
        ttk.Label(shell,text='独立 Edge 学习窗口 · 检测主页面和内嵌播放器 · 无需安装扩展').pack(anchor='w',pady=(2,12))
        bar=ttk.Frame(shell); bar.pack(fill='x')
        self.url=tk.StringVar(value=self.cfg['url']); ttk.Entry(bar,textvariable=self.url).pack(side='left',fill='x',expand=True)
        ttk.Button(bar,text='打开学习窗口',command=self.open_browser).pack(side='left',padx=6)
        self.pages=ttk.Combobox(shell,state='readonly'); self.pages.pack(fill='x',pady=8); self.pages.bind('<<ComboboxSelected>>',lambda e:self.send('page',self.pages.current()))
        buttons=ttk.Frame(shell); buttons.pack(fill='x')
        for title,op in [('检测播放器/目录','scan'),('开始连播','start'),('停止全部自动操作','stop'),('答当前题','answer'),('开始连续答题','continuous')]: ttk.Button(buttons,text=title,command=lambda op=op:self.send(op)).pack(side='left',padx=(0,6))
        self.auto=tk.BooleanVar(); ttk.Checkbutton(buttons,text='自动答题',variable=self.auto,command=lambda:self.send('auto',self.auto.get())).pack(side='left')
        self.batch=tk.BooleanVar()
        batch_box=ttk.LabelFrame(shell,text='完成全部作业 · 自动答题 / 自动交卷 / 下一份作业',padding=8);batch_box.pack(fill='x',pady=8)
        batch_buttons=ttk.Frame(batch_box);batch_buttons.pack(fill='x');self.batch_buttons={}
        for key,title,op in [('start','开始批量','batch'),('pause','暂停','batch_pause'),('resume','继续','batch_resume'),('stop','停止批量','batch_stop')]:
            b=ttk.Button(batch_buttons,text=title,command=lambda op=op:self.send(op),state='normal' if key=='start' else 'disabled');b.pack(side='left',padx=(0,8));self.batch_buttons[key]=b
        self.batch_status=tk.StringVar(value='先选择“我的作业 → 未完成”列表，再开始；批量模式会实际交卷。')
        ttk.Label(batch_box,textvariable=self.batch_status,wraplength=880).pack(fill='x',pady=4)
        self.batch_progress=ttk.Progressbar(batch_box,maximum=1,value=0);self.batch_progress.pack(fill='x')
        self.batch_count=tk.StringVar(value='本轮已提交 0 份｜当前题目进度 0/0')
        ttk.Label(batch_box,textvariable=self.batch_count,wraplength=880).pack(anchor='w')
        self.state=tk.StringVar(value='先打开学习窗口，登录并进入课程。若新开标签页，请在上方选择检测页面。')
        ttk.Label(shell,textvariable=self.state,wraplength=850,foreground='#2455a0').pack(fill='x',pady=10)
        self.question_state=tk.StringVar(value='答题：进入作业页后点击“答当前题”；找不到题目时会检查其他已打开标签页。')
        ttk.Label(shell,textvariable=self.question_state,wraplength=850,foreground='#2455a0').pack(fill='x',pady=(0,8))
        notebook=ttk.Notebook(shell); notebook.pack(fill='both',expand=True)
        course=ttk.Frame(notebook,padding=8); settings=ttk.Frame(notebook,padding=12); notebook.add(course,text='课程目录'); notebook.add(settings,text='设置')
        self.list=tk.Listbox(course,font=('Microsoft YaHei UI',11),activestyle='none'); self.list.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(course,command=self.list.yview); scroll.pack(side='right',fill='y'); self.list.configure(yscrollcommand=scroll.set)
        self.list.bind('<Double-Button-1>',lambda e:self.send('course',self.list.curselection()[0]) if self.list.curselection() else None)
        platform=ttk.Label(settings,text='DeepSeek API 开放平台 ↗',foreground='#0066cc',cursor='hand2',font=('Microsoft YaHei UI',10,'underline'),takefocus=True)
        platform.grid(row=0,column=0,sticky='w',pady=(0,6))
        for event in ('<Button-1>','<Return>','<space>'):platform.bind(event,lambda e:self.open_api_platform())
        fields=[('key','DeepSeek API Key（仅官方接口）'),('model','模型（图片题使用 deepseek-flash）'),('expected','每题选项数量（无需设置）'),('selector','目录选择器（默认参考原插件）')]
        for row,(key,label) in enumerate(fields,start=1):
            ttk.Label(settings,text=label).grid(row=row,column=0,sticky='w',pady=5)
            self.vars[key]=tk.StringVar(value='自动识别：2–26个选项' if key=='expected' else str(self.cfg.get(key,'')))
            ttk.Entry(settings,textvariable=self.vars[key],show='●' if key=='key' else '',state='readonly' if key=='expected' else 'normal').grid(row=row,column=1,sticky='ew',padx=10)
        settings.columnconfigure(1,weight=1)
        self.vision=tk.BooleanVar(value=self.cfg.get('vision',True))
        ttk.Checkbutton(settings,text='识别图片题（发送本题图片给DeepSeek）',variable=self.vision).grid(row=5,column=0,sticky='w',pady=5)
        self.image_detail=tk.StringVar(value='省Token（可能丢失小字）' if self.cfg.get('image_detail')=='low' else '清晰（文字、公式推荐）')
        ttk.Combobox(settings,textvariable=self.image_detail,values=['清晰（文字、公式推荐）','省Token（可能丢失小字）'],state='readonly').grid(row=5,column=1,sticky='ew',padx=10)
        self.mute=tk.BooleanVar(value=self.cfg['mute'])
        ttk.Label(settings,text='准确度策略').grid(row=6,column=0,sticky='w',pady=5)
        self.accuracy=tk.StringVar(value='谨慎（低信心暂停）' if self.cfg.get('accuracy')=='strict' else '省 Token')
        ttk.Combobox(settings,textvariable=self.accuracy,values=['省 Token','谨慎（低信心暂停）'],state='readonly').grid(row=6,column=1,sticky='ew',padx=10)
        ttk.Label(settings,text='谨慎模式信心阈值（0.5–1，不是正确率）').grid(row=7,column=0,sticky='w',pady=5)
        self.confidence=tk.StringVar(value=str(self.cfg.get('confidence',0.85)))
        ttk.Entry(settings,textvariable=self.confidence).grid(row=7,column=1,sticky='ew',padx=10)
        self.simulate_accuracy=tk.BooleanVar(value=self.cfg.get('simulate_accuracy',False))
        self.target_accuracy=tk.StringVar(value=str(self.cfg.get('target_accuracy',80)))
        ttk.Checkbutton(settings,text='启用目标正确率模拟（会主动改选部分答案）',variable=self.simulate_accuracy).grid(row=8,column=0,sticky='w',pady=5)
        target=ttk.Frame(settings);target.grid(row=8,column=1,sticky='ew',padx=10)
        ttk.Entry(target,textvariable=self.target_accuracy,width=7).pack(side='left');ttk.Label(target,text='% 参考答案采纳率，实际正确率不保证').pack(side='left',padx=6)
        ttk.Checkbutton(settings,text='连播时静音',variable=self.mute).grid(row=9,column=0,sticky='w')
        ttk.Label(settings,text='密钥自动用Windows账户加密保存（输入后约0.7秒）').grid(row=9,column=1,sticky='w')
        self.next_question=tk.BooleanVar(value=self.cfg.get('next_question',True))
        ttk.Checkbutton(settings,text='自动答题成功后，自动下一题并继续回答',variable=self.next_question).grid(row=10,column=0,sticky='w',pady=5)
        delay=ttk.Frame(settings); delay.grid(row=10,column=1,sticky='w',padx=10)
        ttk.Label(delay,text='跳题等待（秒）').pack(side='left')
        self.next_delay=tk.StringVar(value=str(self.cfg.get('next_delay',.4)))
        ttk.Entry(delay,textvariable=self.next_delay,width=6).pack(side='left',padx=5)
        ttk.Button(settings,text='保存并应用设置',command=self.save).grid(row=11,column=0,sticky='w',pady=8)
        ttk.Button(settings,text='删除密钥',command=self.delete_key).grid(row=11,column=1,sticky='w')
        ttk.Label(settings,text='单份模式不自动交卷；开始批量后会实际提交。遇到错误暂停，API没有每日调用限制。',wraplength=800).grid(row=12,column=0,columnspan=2,sticky='w')
        bottom=ttk.Frame(shell); bottom.pack(fill='x',pady=(10,4))
        ttk.Label(bottom,text='运行记录').pack(side='left'); ttk.Button(bottom,text='导出诊断',command=self.diagnostic).pack(side='right')
        self.log=tk.Text(shell,height=6,font=('Microsoft YaHei UI',9),state='disabled'); self.log.pack(fill='x')
        self.key_timer=None;self.last_saved_key=self.cfg.get('key','')
        self.vars['key'].trace_add('write',self.schedule_key_save)
        if self.cfg.get('_key_error'):self.write(self.cfg['_key_error'])
        self.engine.start(); self.root.after(150,self.poll); root.protocol('WM_DELETE_WINDOW',self.close)
    def schedule_key_save(self,*_):
        if self.key_timer:self.root.after_cancel(self.key_timer)
        self.key_timer=self.root.after(700,self.persist_key)
    def open_api_platform(self):
        try:
            if not webbrowser.open('https://platform.deepseek.com/api_keys',new=2):raise OSError('无法打开默认浏览器')
        except Exception:messagebox.showerror('打开失败','请在浏览器打开：https://platform.deepseek.com/api_keys')
    def persist_key(self):
        if self.key_timer:self.root.after_cancel(self.key_timer);self.key_timer=None
        key=self.vars['key'].get().strip()
        if key==self.last_saved_key:return True
        try:
            cfg=dict(self.cfg,key=key);save_settings(self.folder,cfg)
            self.cfg['key']=key;self.last_saved_key=key;self.send('key',key)
            self.write('密钥已加密自动保存' if key else '保存的密钥已删除')
            return True
        except Exception as exc:self.write('密钥自动保存失败：'+str(exc));return False
    def shortcut(self):
        if not getattr(sys,'frozen',False):return messagebox.showinfo('快捷方式','请在打包后的程序中使用此功能')
        try:
            from desktop import create_shortcut
            link=create_shortcut(sys.executable);messagebox.showinfo('已创建','桌面快捷方式已创建：'+str(link)+'\n请勿删除或移动它指向的程序文件。')
        except Exception as exc:messagebox.showerror('快捷方式创建失败',str(exc))
    def send(self,op,data=None): self.engine.commands.put((op,data))
    def open_browser(self):
        url=self.url.get().strip()
        if urlsplit(url).scheme not in ('http','https') or not urlsplit(url).hostname: return messagebox.showerror('网址错误','请输入完整的 http:// 或 https:// 学习网址')
        self.send('open',url)
    def save(self):
        try:
            cfg=dict(self.cfg,url=self.url.get().strip(),mute=self.mute.get())
            cfg.update(next_question=self.next_question.get(),accuracy='strict' if self.accuracy.get().startswith('谨慎') else 'standard',confidence=float(self.confidence.get()))
            cfg.update(simulate_accuracy=self.simulate_accuracy.get(),target_accuracy=int(self.target_accuracy.get()))
            cfg.update(vision=self.vision.get(),image_detail='low' if self.image_detail.get().startswith('省Token') else 'original')
            cfg['next_delay']=float(self.next_delay.get()); assert .2<=cfg['next_delay']<=5,'跳题等待须在0.2–5秒之间'
            assert 0<=cfg['target_accuracy']<=100, '目标参考答案采纳率须在0–100之间'
            assert 0.5<=cfg['confidence']<=1, '信心阈值须在0.5–1之间'
            cfg.update({k:v.get().strip() for k,v in self.vars.items() if k!='expected'}); cfg['expected']=0
            cfg.pop('limit',None);cfg.pop('budget',None)
            assert cfg['model'] and cfg['selector'], '模型和目录选择器不能为空'
            save_settings(self.folder,cfg); self.cfg=cfg;self.last_saved_key=cfg['key']
            if self.key_timer:self.root.after_cancel(self.key_timer);self.key_timer=None
            self.auto.set(False); self.send('settings',cfg); self.write('设置已保存并应用（密钥已使用Windows账户加密）')
        except Exception as exc: messagebox.showerror('设置未保存',str(exc))
    def delete_key(self): self.vars['key'].set(''); self.persist_key(); self.send('stop')
    def diagnostic(self):
        file=filedialog.asksaveasfilename(defaultextension='.json',initialfile='芯位诊断.json',filetypes=[('JSON','*.json')])
        if file: self.send('diagnostic',file)
    def write(self,s):
        self.log.configure(state='normal'); self.log.insert('end',time.strftime('%H:%M:%S ')+s+'\n')
        if int(self.log.index('end-1c').split('.')[0])>150:self.log.delete('1.0','30.0')
        self.log.see('end'); self.log.configure(state='disabled')
    def poll(self):
        try:
            while True:
                kind,data=self.events.get_nowait()
                if kind=='state': self.state.set(data)
                elif kind=='question_state': self.question_state.set(data)
                elif kind=='auto_state': self.auto.set(bool(data))
                elif kind=='batch_state': self.batch.set(bool(data))
                elif kind=='batch_status': self.batch_status.set(data)
                elif kind=='batch_controls':
                    enabled={'idle':{'start'},'running':{'pause','stop'},'paused':{'resume','stop'}}.get(data,{'start'})
                    for key,button in self.batch_buttons.items():button.configure(state='normal' if key in enabled else 'disabled')
                elif kind=='batch_progress':
                    count,total,completed,title=data;self.batch_progress.configure(maximum=max(1,total),value=count)
                    self.batch_count.set(f'本轮已提交 {completed} 份｜当前题目进度 {count}/{total}｜{title}')
                elif kind in ('log','error'):
                    self.write(data)
                    if kind=='error': self.state.set('操作失败：'+data); self.auto.set(False)
                elif kind=='courses' and data!=self.last_courses:
                    self.last_courses=data; self.list.delete(0,'end')
                    for item in data:self.list.insert('end',item)
                elif kind=='pages' and data!=self.last_pages:
                    self.last_pages=data; old=self.pages.current(); self.pages['values']=data
                    if data:self.pages.current(max(0,min(old,len(data)-1)))
                elif kind=='selected_page' and self.pages['values'] and data!=self.pages.current(): self.pages.current(data)
        except queue.Empty:pass
        self.root.after(150,self.poll)
    def close(self):
        self.persist_key()
        self.send('close'); self.root.withdraw(); deadline=time.monotonic()+5
        def wait():
            if not self.engine.is_alive() or time.monotonic()>deadline: self.root.destroy()
            else: self.root.after(100,wait)
        wait()

if __name__=='__main__':
    if '--self-test' in sys.argv:
        import json
        from playwright.sync_api import sync_playwright
        report=Path(sys.argv[sys.argv.index('--self-test')+1])
        try:
            from batch import BatchRunner
            from desktop import create_shortcut
            from engine import protect
            from vision import capture_images
            assert protect(protect('xinwei-self-test'),True)=='xinwei-self-test'
            test_root=tk.Tk(); test_root.withdraw(); test_root.update(); test_root.destroy()
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(); page.set_content('<iframe srcdoc="<video style=width:300px;height:200px></video>"></iframe>')
                page.wait_for_timeout(200)
                assert sum(f.locator('video').count() for f in page.frames)==1
                page.set_content('<svg data-xw-desktop-visual="visual-test" width="120" height="80"><rect width="120" height="80" fill="white"/><text x="5" y="40">x=3</text></svg>')
                images,digest=capture_images(page.main_frame,{'visuals':[{'id':'visual-test','zone':'题干'}]})
                assert images[0]['url'].startswith(('data:image/jpeg;base64,','data:image/png;base64,')) and len(digest)==64
                browser.close()
            report.write_text(json.dumps({'ok':True,'checks':['native-tk','bundled-playwright-driver','edge-launch','iframe-video','windows-key-encryption','shortcut-module','rendered-question-image']}),encoding='utf-8')
        except Exception as exc:
            report.write_text(json.dumps({'ok':False,'error':str(exc)}),encoding='utf-8'); sys.exit(1)
        sys.exit(0)
    # One desktop instance owns the browser profile and persistent budget.
    mutex=ctypes.windll.kernel32.CreateMutexW(None,False,'Local\\XinweiDesktop2')
    if ctypes.windll.kernel32.GetLastError()==183:
        ctypes.windll.user32.MessageBoxW(None,'程序已经运行，请检查任务栏。','芯位学习助手',0); sys.exit(0)
    folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'XinweiDesktop'
    folder.mkdir(parents=True,exist_ok=True)
    root=tk.Tk(); App(root,folder); root.mainloop()
