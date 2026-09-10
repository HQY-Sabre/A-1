import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import subprocess
import json
import os
import sys
from queue import Queue, Empty
from collections import defaultdict


class BotController:
    def __init__(self, root):
        self.root = root
        self.root.title("QQ机器人控制面板")
        self.root.geometry("1200x700")


        self.root.minsize(800, 500)

        self.bot_process = None
        self.is_running = False
        self.log_queue = Queue()

        self.ai_dir = os.path.abspath("./ai")
        self.log_file = r"D:\Python_data\pythonProject\chat_logs.json"
        self.ai_config_file = r"D:\Python_data\pythonProject\ai\plugins\hello_reply.py"

        self.user_messages = defaultdict(list)
        self.qq_list = []
        self.last_log_mtime = 0

        self.create_ui()
        self.load_chat_logs()
        self.start_log_refresher()
        self.start_auto_refresh_chat_logs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def create_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        left_container = ttk.Frame(main_paned)
        main_paned.add(left_container, weight=7)

        top_frame = ttk.Frame(left_container)
        top_frame.pack(fill=tk.X, padx=5, pady=5)

        self.start_btn = ttk.Button(top_frame, text="启动机器人", command=self.start_bot)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(top_frame, text="停止机器人", command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(top_frame, text="状态：未启动", foreground="red")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        left_paned = ttk.PanedWindow(left_container, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        chat_frame = ttk.LabelFrame(left_paned, text="聊天记录")
        left_paned.add(chat_frame, weight=7)

        self.msg_text = scrolledtext.ScrolledText(chat_frame, font=("微软雅黑", 10), wrap=tk.WORD)
        self.msg_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.msg_text.config(state=tk.DISABLED)

        search_frame = ttk.LabelFrame(left_paned, text="聊天记录搜索")
        left_paned.add(search_frame, weight=3)

        search_input_frame = ttk.Frame(search_frame)
        search_input_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(search_input_frame, text="关键词：").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_input_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(search_input_frame, text="搜索", command=self.search_message).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_input_frame, text="清空", command=self.clear_msg_display).pack(side=tk.LEFT, padx=5)

        self.search_result_text = scrolledtext.ScrolledText(search_frame, font=("微软雅黑", 10), wrap=tk.WORD, height=8)
        self.search_result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.search_result_text.config(state=tk.DISABLED)

        log_frame = ttk.LabelFrame(main_paned, text="运行日志")
        main_paned.add(log_frame, weight=3)

        self.log_text = scrolledtext.ScrolledText(log_frame, font=("微软雅黑", 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
        ttk.Button(log_frame, text="清空运行日志", command=self.clear_log_display).pack(fill=tk.X, padx=5, pady=5)

    def load_chat_logs(self):
        self.user_messages.clear()
        self.qq_list.clear()
        if not os.path.exists(self.log_file):
            self.msg_text.config(state=tk.NORMAL)
            self.msg_text.delete(1.0, tk.END)
            self.msg_text.insert(tk.END, "暂无聊天记录")
            self.msg_text.config(state=tk.DISABLED)
            return
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
            for log in logs:
                qq = str(log.get("user_id", "未知QQ"))
                name = log.get("user_name", "未知用户")
                time = log.get("time", "")
                msg = log.get("message", "")
                self.user_messages[qq].append({"time": time, "name": name, "message": msg})
            self.qq_list = list(self.user_messages.keys())
            self.msg_text.config(state=tk.NORMAL)
            self.msg_text.delete(1.0, tk.END)
            all_messages = []
            for qq, msgs in self.user_messages.items():
                all_messages.extend(msgs)
            all_messages.sort(key=lambda x: x["time"])
            for msg in all_messages:
                line = f"[{msg['time']}] {msg['name']}：{msg['message']}\n"
                self.msg_text.insert(tk.END, line)
            self.msg_text.config(state=tk.DISABLED)
            self.msg_text.see(tk.END)
        except Exception as e:
            self.add_log(f"❌ 加载失败：{e}")

    def get_qq_by_name(self, name):
        for qq, msgs in self.user_messages.items():
            if msgs and msgs[0]["name"] == name:
                return qq
        return "未知QQ"

    def search_message(self):
        keyword = self.search_entry.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入关键词")
            return
        all_messages = []
        for qq, msgs in self.user_messages.items():
            all_messages.extend(msgs)
        matched = [m for m in all_messages if keyword in m["message"]]
        self.search_result_text.config(state=tk.NORMAL)
        self.search_result_text.delete(1.0, tk.END)
        if not matched:
            self.search_result_text.insert(tk.END, f"未找到「{keyword}」")
        else:
            self.search_result_text.insert(tk.END, f"找到 {len(matched)} 条\n")
            for m in matched:
                self.search_result_text.insert(tk.END, f"[{m['time']}] {m['name']}：{m['message']}\n")
        self.search_result_text.config(state=tk.DISABLED)

    def clear_msg_display(self):
        self.msg_text.config(state=tk.NORMAL)
        self.msg_text.delete(1.0, tk.END)
        self.msg_text.config(state=tk.DISABLED)
        self.search_result_text.config(state=tk.NORMAL)
        self.search_result_text.delete(1.0, tk.END)
        self.search_result_text.config(state=tk.DISABLED)
        self.search_entry.delete(0, tk.END)

    def start_auto_refresh_chat_logs(self):
        def auto_refresh():
            while True:
                try:
                    if os.path.exists(self.log_file):
                        t = os.path.getmtime(self.log_file)
                        if t != self.last_log_mtime:
                            self.last_log_mtime = t
                            self.root.after(0, self.load_chat_logs)
                except Exception:
                    pass
                threading.Event().wait(2)
        threading.Thread(target=auto_refresh, daemon=True).start()

    def add_log(self, text):
        self.log_queue.put(text)

    def start_log_refresher(self):
        def refresh():
            while True:
                try:
                    msg = self.log_queue.get(timeout=0.1)
                    self.log_text.config(state=tk.NORMAL)
                    self.log_text.insert(tk.END, msg + "\n")
                    self.log_text.see(tk.END)
                    self.log_text.config(state=tk.DISABLED)
                except Empty:
                    continue
        threading.Thread(target=refresh, daemon=True).start()

    def clear_log_display(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_bot(self):
        if self.is_running:
            messagebox.showinfo("提示", "已运行")
            return
        def run():
            try:
                self.bot_process = subprocess.Popen(
                    ["nb", "run"], cwd=self.ai_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8"
                )
                for line in iter(self.bot_process.stdout.readline, ""):
                    if self.is_running:
                        self.add_log(line.strip())
                self.bot_process.wait()
            except Exception as e:
                self.add_log(f"启动失败：{e}")
            finally:
                self.is_running = False
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
                self.root.after(0, lambda: self.status_label.config(text="状态：未启动", foreground="red"))
        self.is_running = True
        threading.Thread(target=run, daemon=True).start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="状态：运行中", foreground="green")
        self.add_log("✅ 启动中")

    def stop_bot(self):
        if not self.is_running:
            messagebox.showinfo("提示", "未运行")
            return
        self.add_log("🛑 停止中")
        self.is_running = False
        try:
            if sys.platform == "win32":
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(self.bot_process.pid)])
            else:
                self.bot_process.terminate()
        except Exception:
            pass
        self.bot_process = None
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="状态：已停止", foreground="red")
        self.add_log("✅ 已停止")

    def on_window_close(self):
        if self.is_running:
            self.stop_bot()
        self.root.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    root = tk.Tk()
    app = BotController(root)
    root.mainloop()