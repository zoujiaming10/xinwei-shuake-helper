# 芯位刷课助手

可读的 Python/Tkinter 源码，版本 **2.5.6**。没有使用 pyobfus 混淆，没有打卡密通外壳，也不需要卡密通才能从源码启动。

本程序免费使用。DeepSeek API 的调用费用由使用者自行承担。

## 当前状态

这是现有开发源码的公开整理副本，不是新修复版。**课件/PPT 跳过仍有已知问题**：网页高亮课件时，程序可能继续将上一段已结束的视频识别为当前项，导致不能继续跳转。该问题尚未完成真实页面定位和修复。

保留的功能包括课程目录检测、视频连播、DeepSeek 文字及图片题辅助、单份和批量作业流程、Windows 账户加密保存 API Key。模型答案与正确率不作保证。批量作业会自动提交，请在使用前了解界面提示和实际操作范围。

## 环境与启动

已验证的开发环境是 Windows 11、Python 3.14 和已安装的 Microsoft Edge。需安装包含 Tcl/Tk 的 Python。

在项目目录打开 PowerShell：

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

程序使用本机 Edge，不需要下载 Playwright Chromium。若提示程序已运行，请先正常关闭旧版学习助手。

DeepSeek API Key 由使用者在设置页自行填写。程序数据保存在 `%LOCALAPPDATA%\XinweiDesktop`，不在此源码包内。图片识别启用后，会将当前题目的相关图片发送给配置所用的 DeepSeek 官方接口。

## 源码结构

- `app.py`：桌面界面、设置与事件展示。
- `engine.py`：浏览器控制、目录、媒体、题目与 API 流程。
- `batch.py`：批量作业状态机。
- `vision.py`：题目图片读取与校验。
- `desktop.py`：Windows 桌面快捷方式。

## 本地检查

以下测试使用本地模拟页面，不使用真实 API Key，也不提交真实作业；通过不代表已覆盖所有平台页面。

```powershell
.\.venv\Scripts\python.exe tests/test_document_navigation.py
.\.venv\Scripts\python.exe tests/test_auto_open_catalog.py
.\.venv\Scripts\python.exe tests/test_next_overlay.py
```

## 自行构建未加密 EXE

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --windowed --onedir --noupx --name XinweiDesktop app.py
```

输出为 `dist/XinweiDesktop/`。运行时需要保留完整目录。本流程没有混淆或卡密通加密步骤。

## 上传 GitHub

新建仓库后上传本目录中的文件；也可在 GitHub 网页选择 Upload files。不要上传原开发目录、用户数据目录、商业工具或旧发布备份。`.gitignore` 仅用于减少误提交，不能清除已经上传的历史文件。

## 许可与参考

`LICENSE` 原样保留现有项目的 MIT 许可文件。本次只整理文件，未重新决定或审核整个项目的许可归属。

开发过程曾参考 [KanoTis/51xinweiauto](https://github.com/KanoTis/51xinweiauto)；本包不包含其原始用户脚本。参考项目的许可与本项目已有许可声明应分别核对，不能用本包的 MIT 文件替代第三方许可。Python、Tk、Playwright、Pillow 等依赖保留各自许可。

历史功能说明见 `docs/历史版本说明.md`，其中的旧版本号、测试结论及旧设置描述以对应历史版本为准。
