#!/usr/bin/env python3
import os
import subprocess
import time
import shutil
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox

# Настройки нашей инфраструктуры
HOME = os.path.expanduser("~")
BASE_DIR = os.path.join(HOME, "tg_work", "accounts")
TG_BIN = os.path.join(HOME, "tg_work", "bin", "Telegram")
PREFS_FILE = os.path.join(HOME, "tg_work", "last_selected.txt")
PRIO_FILE = os.path.join(HOME, "tg_work", "priorities.txt")

# Переменные среды (наши фиксы для XFCE и графики)
os.environ["NO_AT_BRIDGE"] = "1"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
os.environ["GALLIUM_DRIVER"] = "llvmpipe"

class TgLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("Управление сессиями Telegram")
        
        # Центрируем окно на экране и делаем его шире
        window_width = 800
        window_height = 650
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        pos_x = int((screen_width / 2) - (window_width / 2))
        pos_y = int((screen_height / 2) - (window_height / 2))
        self.root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")

        # Наводим красоту: тема clam и настройка зебры для таблицы
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", font=("Arial", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))
        
        # Убираем рамки вокруг таблицы, чтобы смотрелось чище
        style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])

        self.accounts = []
        self.checked_accs = set()
        self.priorities = {}
        self.load_data()

        # --- ВЕРХНИЙ БЛОК: Поиск ---
        search_frame = tk.Frame(root)
        search_frame.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(search_frame, text="⌕ Фильтр:", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 12))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        self.search_entry.focus()

        # --- СРЕДНИЙ БЛОК: Таблица ---
        table_frame = tk.Frame(root)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15)
        
        self.tree = ttk.Treeview(table_frame, columns=("check", "name", "priority"), show="headings", selectmode="browse")
        self.tree.heading("check", text="✔")
        self.tree.heading("name", text="Кодовое имя (Аккаунт)")
        self.tree.heading("priority", text="Приоритет")
        
        self.tree.column("check", width=50, anchor=tk.CENTER)
        self.tree.column("name", width=500, anchor=tk.W)
        self.tree.column("priority", width=150, anchor=tk.CENTER)

        # Теги для зебры
        self.tree.tag_configure('evenrow', background='#f9f9f9')
        self.tree.tag_configure('oddrow', background='#ffffff')

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.tree.bind("<ButtonRelease-1>", self.on_click)

        # --- НИЖНИЙ БЛОК: Кнопки ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill=tk.X, padx=10, pady=15)

        tk.Button(btn_frame, text="▶ Запуск", bg="#28a745", fg="white", font=("Arial", 11, "bold"), relief=tk.FLAT, command=self.launch).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)
        ttk.Button(btn_frame, text="⚡ Быстрый старт", command=self.quick_start).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)
        ttk.Button(btn_frame, text="★ Приоритет", command=self.change_priority).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)
        ttk.Button(btn_frame, text="+ Добавить", command=self.add_acc).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)
        ttk.Button(btn_frame, text="✎ Переименовать", command=self.rename_acc).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)
        ttk.Button(btn_frame, text="✖ Удалить", command=self.delete_acc).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X, ipady=4)

        self.populate_tree()

    def load_data(self):
        try:
            self.accounts = [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
        except FileNotFoundError:
            os.makedirs(BASE_DIR, exist_ok=True)
            self.accounts = []

        with open(PRIO_FILE, "a+") as f:
            f.seek(0)
            for line in f:
                parts = line.strip().split('|')
                if len(parts) == 2 and parts[1].isdigit():
                    self.priorities[parts[0]] = int(parts[1])

        self.checked_accs = set()
        with open(PREFS_FILE, "a+") as f:
            f.seek(0)
            for line in f:
                val = line.strip()
                if val in self.accounts:
                    self.checked_accs.add(val)

    def save_checked(self):
        with open(PREFS_FILE, "w") as f:
            for acc in self.checked_accs:
                f.write(acc + "\n")

    def save_priorities(self):
        with open(PRIO_FILE, "w") as f:
            for acc, p in self.priorities.items():
                f.write(f"{acc}|{p}\n")

    def get_prio(self, acc):
        return self.priorities.get(acc, 1000)

    def update_list(self, *args):
        self.populate_tree()

    def populate_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        search_text = self.search_var.get().lower()
        sorted_accs = sorted(self.accounts, key=lambda x: (self.get_prio(x), x.lower()))

        row_count = 0
        for acc in sorted_accs:
            if search_text in acc.lower():
                chk = "☑" if acc in self.checked_accs else "☐"
                tag = 'evenrow' if row_count % 2 == 0 else 'oddrow'
                self.tree.insert("", tk.END, iid=acc, values=(chk, acc, self.get_prio(acc)), tags=(tag,))
                row_count += 1

    def on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            if column == "#1" and item:
                if item in self.checked_accs:
                    self.checked_accs.remove(item)
                    self.tree.set(item, "check", "☐")
                else:
                    self.checked_accs.add(item)
                    self.tree.set(item, "check", "☑")
                self.save_checked()

    def launch(self):
        if not self.checked_accs:
            return
        to_launch = sorted(list(self.checked_accs), key=lambda x: self.get_prio(x))
        for acc in to_launch:
            workdir = os.path.join(BASE_DIR, acc)
            subprocess.Popen([TG_BIN, "-many", "-workdir", workdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
        self.root.destroy()

    def quick_start(self):
        item = self.tree.focus()
        if item:
            subprocess.Popen([TG_BIN, "-many", "-workdir", os.path.join(BASE_DIR, item)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.root.destroy()

    def change_priority(self):
        item = self.tree.focus()
        if item:
            curr = self.get_prio(item)
            new_p = simpledialog.askinteger("Приоритет", f"Установи приоритет для '{item}'\n(1000 - стандарт, чем меньше число - тем быстрее запуск):", initialvalue=curr)
            if new_p is not None:
                self.priorities[item] = new_p
                self.save_priorities()
                self.populate_tree()

    def add_acc(self):
        new_name = simpledialog.askstring("Добавить", "Введи имя нового аккаунта:")
        if new_name:
            workdir = os.path.join(BASE_DIR, new_name)
            os.makedirs(workdir, exist_ok=True)
            subprocess.Popen([TG_BIN, "-many", "-workdir", workdir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.load_data()
            self.populate_tree()

    def rename_acc(self):
        item = self.tree.focus()
        if item:
            new_name = simpledialog.askstring("Переименовать", f"Введи новое имя для '{item}':", initialvalue=item)
            if new_name and new_name != item:
                os.rename(os.path.join(BASE_DIR, item), os.path.join(BASE_DIR, new_name))
                if item in self.checked_accs:
                    self.checked_accs.remove(item)
                    self.checked_accs.add(new_name)
                    self.save_checked()
                if item in self.priorities:
                    self.priorities[new_name] = self.priorities.pop(item)
                    self.save_priorities()
                self.load_data()
                self.populate_tree()

    def delete_acc(self):
        item = self.tree.focus()
        if item:
            if messagebox.askyesno("Удаление", f"Удалить аккаунт '{item}' навсегда?\n\nВнимание: Вся папка tdata и файлы сессии будут безвозвратно стерты!"):
                target_dir = os.path.join(BASE_DIR, item)
                
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                
                if item in self.checked_accs:
                    self.checked_accs.remove(item)
                    self.save_checked()
                if item in self.priorities:
                    self.priorities.pop(item)
                    self.save_priorities()
                
                self.load_data()
                self.populate_tree()

if __name__ == "__main__":
    root = tk.Tk()
    app = TgLauncher(root)
    root.mainloop()
