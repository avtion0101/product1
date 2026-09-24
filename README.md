# 软件项目一键生成器

一个面向 Windows 和 macOS 的本地桌面工作流：输入软件名称后，生成 Python/PyQt6 项目、10 个业务模块、自动化测试、运行截图、操作手册、65 页代码文档、申请表信息和待验收压缩包。

## 在 Apple 芯片 Mac 上使用生成器

先安装 Python、Tk、Poppler 和 LibreOffice，并克隆仓库：

```bash
brew install python@3.12 python-tk@3.12 poppler
brew install --cask libreoffice
git clone https://github.com/avtion0101/product1.git
cd product1
chmod +x 一键生成.command
./一键生成.command --preflight
./一键生成.command
```

默认使用本机 Codex 登录：先确保 Codex CLI 已安装并运行 `codex login`。也可在生成器窗口选 Gemini、Grok、OpenAI 或兼容 API。输入新项目名称后执行完整生成流程；结果写入 `生成结果/`，包含项目源码、测试、截图、文档、验收清单和压缩包。macOS 路径已做静态检查，尚未在真实 Mac 上完成全流程实测。

## 验收案例：食品添加剂超量使用检测系统

[食品添加剂超量使用检测系统](食品添加剂超量使用检测系统)是用生成器产出的案例，保留用于检查生成结果的结构与业务效果，不是生成器的唯一输出目标。其演示规则不是法定标准，不能直接用于产品放行。单独运行案例时，进入该目录执行 `./启动软件.command`；Windows 可双击 `启动软件.cmd`。

## 支持的模型来源

- 本机 Codex 登录额度
- Google Gemini API
- xAI Grok API
- OpenAI API
- 其他支持 `chat/completions` 和 JSON Schema 结构化输出的 OpenAI 兼容接口

API Key 只从本次窗口或环境变量读取，不写入配置、日志或交付包。

## 其他启动方式

Windows 双击 `一键生成.cmd`。

建议预留至少 2 GB 磁盘空间。Windows 可使用 Microsoft Word 或 LibreOffice 转换文档；macOS 使用 LibreOffice。

完整配置、API 环境变量和命令行示例见 [使用说明.md](使用说明.md)。自动检查范围及尚未完成的真实 Mac 验证见 [验证说明.md](验证说明.md)。

## 验证状态

- 12 项离线契约、业务表单、跨平台启动、模板回退和模拟 API 测试通过。
- Windows 下的生成逻辑、Word/PDF 转换和代码文档已经验证；新版独立启动入口尚未完成实跑。
- Gemini/Grok客户端完成模拟HTTPS响应测试，未使用真实API额度。
- macOS路径已经实现；目标Mac上的项目运行和生成器真实试单仍待验证。

自动检查不代表委托方最终验收。领域算法、全部截图、申请表字段和最终压缩包仍需人工复核。
