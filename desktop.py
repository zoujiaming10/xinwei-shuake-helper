"""Create real Windows shortcuts; all paths are absolute and independent of cwd."""
import base64,os,subprocess,tempfile,re,xml.etree.ElementTree as ET
from pathlib import Path

def create_shortcut(executable,link_path=None):
    target=Path(os.environ.get('XINWEI_DESKTOP_ENTRY') or executable).resolve(strict=True)
    # A shortcut to the decrypted launcher can break on the next extraction and
    # would also point past the protected entry. Never create that shortcut.
    temp_root=Path(tempfile.gettempdir()).resolve()
    if target.is_relative_to(temp_root) or any(p.lower().startswith(('kami_','_mei')) for p in target.parts):
        raise RuntimeError('当前在加密壳临时目录运行，请使用安装包创建的桌面快捷方式，或从稳定目录的兼容启动入口运行后再创建')
    env=os.environ.copy();env['XINWEI_SHORTCUT_TARGET']=str(target)
    env['XINWEI_SHORTCUT_FOLDER']=str(target.parent)
    env['XINWEI_SHORTCUT_PATH']=str(Path(link_path).resolve()) if link_path else ''
    code='''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=[Text.UTF8Encoding]::new();
$linkPath=$env:XINWEI_SHORTCUT_PATH;
if(-not $linkPath){$linkPath=Join-Path ([Environment]::GetFolderPath('Desktop')) '芯位学习助手.lnk'};
$shell=New-Object -ComObject WScript.Shell;$link=$shell.CreateShortcut($linkPath);
$link.TargetPath=$env:XINWEI_SHORTCUT_TARGET;$link.WorkingDirectory=$env:XINWEI_SHORTCUT_FOLDER;
$link.Arguments='';$link.IconLocation=$env:XINWEI_SHORTCUT_TARGET;
$link.Description='芯位学习助手';$link.Save();[Console]::WriteLine($linkPath)'''
    encoded=base64.b64encode(code.encode('utf-16-le')).decode('ascii')
    result=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',encoded],
        env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,timeout=20)
    if result.returncode:
        error=result.stderr.strip()
        if '#< CLIXML' in error:
            try:
                xml=ET.fromstring(error[error.index('<Objs'):]);parts=[]
                for node in xml.iter():
                    if node.tag.rsplit('}',1)[-1]=='S' and node.get('S')=='Error':parts.append(node.text or '')
                error=' '.join(parts) or '系统拒绝创建快捷方式，请使用安装包创建的快捷方式'
                error=re.sub(r'_x([0-9A-Fa-f]{4})_',lambda m:chr(int(m[1],16)),error)
            except (ET.ParseError,ValueError):error='系统拒绝创建快捷方式，请使用安装包创建的快捷方式'
        raise RuntimeError('快捷方式创建失败：'+error[:240])
    return Path(result.stdout.strip())
