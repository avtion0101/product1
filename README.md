# 软件项目一键生成器

一个面向 Windows 和 macOS 的本地桌面工作流：输入软件名称后，生成 Python/PyQt6 项目、10 个业务模块、自动化测试、运行截图、操作手册、65 页代码文档、申请表信息和待验收压缩包。

## 支持的模型来源

- 本机 Codex 登录额度
- Google Gemini API
- xAI Grok API
- OpenAI API
- 其他支持 `chat/completions` 和 JSON Schema 结构化输出的 OpenAI 兼容接口

API Key 只从本次窗口或环境变量读取，不写入配置、日志或交付包。

## 快速开始

Windows 双击 `一键生成.cmd`。

macOS 首次运行：

```bash
brew install python poppler
brew install --cask libreoffice
chmod +x 一键生成.command
./一键生成.command
```

建议预留至少 2 GB 磁盘空间。Windows 可使用 Microsoft Word 或 LibreOffice 转换文档；macOS 使用 LibreOffice。

完整配置、API 环境变量和命令行示例见 [使用说明.md](使用说明.md)。自动检查范围及尚未完成的真实 Mac 验证见 [验证说明.md](验证说明.md)。

## 验证状态

- 11 项离线契约、跨平台启动、模板回退和模拟 API 测试通过。
- Windows Codex、Word/PDF转换、65页代码文档和102页视觉检查已经验证。
- Gemini/Grok客户端完成模拟HTTPS响应测试，未使用真实API额度。
- macOS路径已经实现，但仍需在目标Mac上执行预检和至少一个真实试单。

自动检查不代表委托方最终验收。领域算法、全部截图、申请表字段和最终压缩包仍需人工复核。

