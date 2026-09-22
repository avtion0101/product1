"""Cross-platform Tk launcher. Qt is installed only when a generated app must run."""
import argparse
import copy
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / ".packages"))
os.environ.setdefault("PYTHONPATH", str(HERE / ".packages"))
os.environ.setdefault("PYTHONUTF8", "1")
from contracts import read_json
from pipeline import Pipeline, ROOT


def open_path(path):
    path = str(Path(path).resolve())
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def configured_settings(provider=None, model=None, base_url=None):
    settings = read_json(HERE / "settings.json")
    if provider:
        settings["provider"] = provider
    active = settings.get("provider", "codex")
    if active not in settings.get("providers", {}):
        raise ValueError(f"未知模型提供商：{active}")
    if model is not None:
        settings["providers"][active]["model"] = model
    if base_url is not None:
        settings["providers"][active]["base_url"] = base_url
    return settings


def gui(base_settings=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    base_settings = base_settings or configured_settings()
    providers = base_settings["providers"]
    choices = [f"{key} · {value.get('label', key)}" for key, value in providers.items()]
    id_for_choice = {choice: choice.split(" · ", 1)[0] for choice in choices}
    choice_for_id = {value: key for key, value in id_for_choice.items()}

    app = tk.Tk()
    app.title("软件项目一键生成器 · Windows / macOS")
    app.geometry("980x790")
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure("TButton", padding=9)
    style.configure("TLabel", font=("TkDefaultFont", 11))
    main = ttk.Frame(app, padding=20); main.pack(fill="both", expand=True)
    ttk.Label(main, text="输入软件名称，一键生成项目与交付资料",
              font=("TkDefaultFont", 19, "bold")).pack(anchor="w", pady=(0, 14))

    form = ttk.Frame(main); form.pack(fill="x")
    form.columnconfigure(1, weight=1); form.columnconfigure(3, weight=1)
    name = tk.StringVar()
    provider_choice = tk.StringVar(value=choice_for_id[base_settings.get("provider", "codex")])
    model = tk.StringVar()
    base_url = tk.StringVar()
    api_key = tk.StringVar()
    source_root = tk.StringVar(value=base_settings.get("source_root", ""))
    credential_text = tk.StringVar()

    ttk.Label(form, text="软件名称").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
    entry = ttk.Entry(form, textvariable=name, font=("TkDefaultFont", 13))
    entry.grid(row=0, column=1, columnspan=3, sticky="ew", ipady=6, pady=5)
    ttk.Label(form, text="模型来源").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
    provider_box = ttk.Combobox(form, textvariable=provider_choice, values=choices, state="readonly")
    provider_box.grid(row=1, column=1, sticky="ew", pady=5)
    ttk.Label(form, text="模型").grid(row=1, column=2, sticky="w", padx=(16, 8), pady=5)
    model_entry = ttk.Entry(form, textvariable=model)
    model_entry.grid(row=1, column=3, sticky="ew", pady=5)
    ttk.Label(form, text="API地址").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=5)
    base_entry = ttk.Entry(form, textvariable=base_url)
    base_entry.grid(row=2, column=1, columnspan=3, sticky="ew", pady=5)
    ttk.Label(form, text="API Key").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=5)
    key_entry = ttk.Entry(form, textvariable=api_key, show="*")
    key_entry.grid(row=3, column=1, sticky="ew", pady=5)
    ttk.Label(form, textvariable=credential_text).grid(row=3, column=2, columnspan=2, sticky="w", padx=(16, 0), pady=5)
    ttk.Label(form, text="案例目录").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=5)
    ttk.Entry(form, textvariable=source_root).grid(row=4, column=1, columnspan=2, sticky="ew", pady=5)
    ttk.Button(form, text="选择", command=lambda: source_root.set(
        filedialog.askdirectory(title="选择原案例目录") or source_root.get())).grid(row=4, column=3, sticky="e", pady=5)

    ttk.Label(main, text="API Key仅保存在本次进程内，不写入配置、日志或交付包。案例目录不可用时使用内置知识库与模板。",
              foreground="#53657a").pack(anchor="w", pady=(8, 4))
    row = ttk.Frame(main); row.pack(fill="x")
    progress = tk.DoubleVar()
    bar = ttk.Progressbar(main, maximum=100, variable=progress); bar.pack(fill="x", pady=10)
    logs = tk.Text(main, wrap="word", font=("TkFixedFont", 10), state="disabled", height=14)
    logs.pack(fill="both", expand=True)
    ttk.Label(main, text="自动检查不等于委托方验收；领域算法、截图和申请表仍需人工复核。",
              foreground="#53657a").pack(anchor="w", pady=8)
    events = queue.Queue()
    state = {"running": False, "worker": None, "output": None, "cancel": threading.Event()}

    def selected_provider():
        return id_for_choice[provider_choice.get()]

    def update_provider(*_):
        pid = selected_provider()
        config = providers[pid]
        model.set(config.get("model", ""))
        base_url.set(config.get("base_url", ""))
        env_name = config.get("api_key_env", "")
        credential_text.set("使用已保存的ChatGPT登录" if pid == "codex" else f"环境变量：{env_name}")
        state_value = "disabled" if pid == "codex" else "normal"
        key_entry.configure(state=state_value)
        base_entry.configure(state=state_value)
        api_key.set("")

    provider_box.bind("<<ComboboxSelected>>", update_provider)
    update_provider()

    def append(text):
        logs.configure(state="normal"); logs.insert("end", str(text)+"\n"); logs.see("end"); logs.configure(state="disabled")

    def busy(value):
        state["running"] = value
        start.configure(state="disabled" if value else "normal")
        resume.configure(state="disabled" if value else "normal")
        stop.configure(state="normal" if value else "disabled")
        entry.configure(state="disabled" if value else "normal")
        provider_box.configure(state="disabled" if value else "readonly")

    def task_settings():
        settings = copy.deepcopy(base_settings)
        pid = selected_provider()
        settings["provider"] = pid
        settings["source_root"] = source_root.get().strip()
        settings["providers"][pid]["model"] = model.get().strip()
        if pid != "codex":
            settings["providers"][pid]["base_url"] = base_url.get().strip()
            if not settings["providers"][pid]["model"]:
                raise ValueError("请填写模型名称。")
            if not settings["providers"][pid]["base_url"].startswith("https://"):
                raise ValueError("API地址必须使用https://。")
            env_name = settings["providers"][pid]["api_key_env"]
            if api_key.get().strip():
                os.environ[env_name] = api_key.get().strip()
            if not os.environ.get(env_name):
                raise ValueError(f"请输入API Key，或在启动前设置 {env_name}。")
        return settings

    def begin(resume_dir=None):
        if state["running"]:
            return
        if not name.get().strip():
            messagebox.showinfo("软件名称", "请先输入软件名称。"); return
        try:
            settings = task_settings()
        except ValueError as exc:
            messagebox.showwarning("模型配置", str(exc)); return
        logs.configure(state="normal"); logs.delete("1.0", "end"); logs.configure(state="disabled")
        progress.set(0); busy(True); state["cancel"] = threading.Event()
        task_name = name.get().strip()

        def run():
            pipeline = Pipeline(lambda s: events.put(("log", s)), lambda n: events.put(("progress", n)),
                                state["cancel"], settings=settings)
            try:
                output = pipeline.run(task_name, resume_dir)
                events.put(("done", str(output)))
            except Exception as exc:
                events.put(("failed", (str(exc), str(pipeline.run_dir or ""))))

        state["worker"] = threading.Thread(target=run, daemon=True)
        state["worker"].start()

    def choose_resume():
        directory = filedialog.askdirectory(title="选择包含state.json的任务目录", initialdir=ROOT/"生成结果")
        if directory:
            try:
                info = read_json(Path(directory)/"state.json")
                name.set(info["name"])
                snapshot = Path(directory) / "settings_snapshot.json"
                if snapshot.exists():
                    previous = read_json(snapshot)
                    pid = previous.get("provider", "codex")
                    if pid in choice_for_id:
                        provider_choice.set(choice_for_id[pid]); update_provider()
                        model.set(previous.get("providers", {}).get(pid, {}).get("model", model.get()))
                        base_url.set(previous.get("providers", {}).get(pid, {}).get("base_url", base_url.get()))
                begin(directory)
            except Exception as exc:
                messagebox.showerror("无法续跑", str(exc))

    def cancel():
        state["cancel"].set(); append("已请求停止，正在保存进度。")

    def open_output():
        open_path(Path(state["output"]) if state["output"] else ROOT)

    def pump():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "log":
                    append(value)
                elif kind == "progress":
                    progress.set(value)
                elif kind == "done":
                    state["output"] = value; busy(False)
                    append("已生成，待人工验收：" + value)
                    messagebox.showinfo("生成完成", "自动检查通过。请查看验收报告与质量检查目录。")
                elif kind == "failed":
                    busy(False); state["output"] = value[1] or None; append(value[0])
                    messagebox.showwarning("未完成，可以续跑", value[0][-1800:])
        except queue.Empty:
            pass
        app.after(150, pump)

    def close():
        if state["running"]:
            cancel(); append("停止完成后即可关闭窗口。")
        else:
            app.destroy()

    start = ttk.Button(row, text="一键生成", command=begin); start.pack(side="left", padx=(0, 8))
    resume = ttk.Button(row, text="继续上次任务", command=choose_resume); resume.pack(side="left", padx=8)
    stop = ttk.Button(row, text="停止并保存", command=cancel, state="disabled"); stop.pack(side="left", padx=8)
    ttk.Button(row, text="打开结果目录", command=open_output).pack(side="left", padx=8)
    append("就绪。可选择本机Codex、Gemini、Grok、OpenAI或其他OpenAI兼容API。")
    app.protocol("WM_DELETE_WINDOW", close); app.after(150, pump); entry.focus_set(); app.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    parser.add_argument("--resume")
    parser.add_argument("--learn", action="store_true")
    parser.add_argument("--fixture")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--provider", choices=["codex", "gemini", "grok", "openai", "custom"])
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    args = parser.parse_args()
    settings = configured_settings(args.provider, args.model, args.base_url)
    if args.learn:
        from learn import learn
        learn(settings["source_root"], ROOT / "知识库")
        print(ROOT / "知识库")
    elif args.preflight:
        from environment import inspect_environment
        print(json.dumps(inspect_environment(ROOT, settings), ensure_ascii=False, indent=2))
    elif args.name:
        print(Pipeline(settings=settings).run(args.name, args.resume, args.fixture))
    else:
        gui(settings)


if __name__ == "__main__":
    main()
