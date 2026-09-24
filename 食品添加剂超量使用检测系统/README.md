# 食品添加剂超量使用检测系统 V1.0

Windows双击启动软件.cmd；macOS（Apple芯片）先安装Python 3.12，首次运行执行 `chmod +x 启动软件.command && ./启动软件.command`。启动器会创建venv，并安装PyQt6与OpenCV。建议macOS 13以上；首次安装需要联网。

演示管理员：admin / Admin123!。注册账号默认为操作员。

业务界面提供表单、表格与任务工作台；JSON仅用于高级导出。执行计算后保存结果，提交后由管理员通过或退回。

本地算法和演示样例不连接真实外部设备。SQLite位于data/app.sqlite。
