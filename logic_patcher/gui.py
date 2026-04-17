# logic_patcher/gui.py

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .core import process_folder


def launch_gui():
    root = tk.Tk()
    root.title("Logic Patcher")
    root.geometry("600x500")

    name_var = tk.StringVar()
    roll_var = tk.StringVar()
    folder_var = tk.StringVar()

    def browse():
        folder = filedialog.askdirectory()
        if folder:
            folder_var.set(folder)

    def log(msg):
        output.insert(tk.END, msg + "\n")
        output.see(tk.END)
        root.update_idletasks()

    def update_progress(current, total):
        progress["maximum"] = total
        progress["value"] = current
        root.update_idletasks()

    def start():
        name = name_var.get().strip()
        roll = roll_var.get().strip()
        folder = folder_var.get().strip()

        if not name or not roll or not folder:
            messagebox.showerror("Error", "All fields required")
            return

        output.delete(1.0, tk.END)
        progress["value"] = 0
        start_btn.config(state=tk.DISABLED)

        def run():
            try:
                changed, total, out = process_folder(name, roll, folder, log, update_progress)
                root.after(0, lambda: finish(changed, total, out))
            except Exception as e:
                root.after(0, lambda err=e: on_error(str(err)))

        threading.Thread(target=run, daemon=True).start()

    def finish(changed, total, out):
        log("\n===== SUMMARY =====")
        log(f"Files changed: {changed}")
        log(f"Total replacements: {total}")
        log(f"Output: {out}")
        start_btn.config(state=tk.NORMAL)
        messagebox.showinfo("Done", "Processing completed!")

    def on_error(msg):
        messagebox.showerror("Error", msg)
        start_btn.config(state=tk.NORMAL)

    tk.Label(root, text="Full Name").pack()
    tk.Entry(root, textvariable=name_var).pack()

    tk.Label(root, text="Roll Number").pack()
    tk.Entry(root, textvariable=roll_var).pack()

    tk.Label(root, text="Folder").pack()
    frame = tk.Frame(root)
    frame.pack()

    tk.Entry(frame, textvariable=folder_var, width=40).pack(side=tk.LEFT)
    tk.Button(frame, text="Browse", command=browse).pack(side=tk.LEFT)

    start_btn = tk.Button(root, text="Start", command=start, bg="green", fg="white")
    start_btn.pack(pady=10)

    progress = ttk.Progressbar(root, length=400)
    progress.pack(pady=5)

    output = tk.Text(root)
    output.pack(fill=tk.BOTH, expand=True)

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
