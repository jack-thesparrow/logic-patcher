import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from .core import process_folder


def launch_gui():
    root = tk.Tk()
    root.title("Logic File Replacer")
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
        root.update()

    def start():
        name = name_var.get().strip()
        roll = roll_var.get().strip()
        folder = folder_var.get().strip()

        if not name or not roll or not folder:
            messagebox.showerror("Error", "All fields required")
            return

        output.delete(1.0, tk.END)

        changed, total, out = process_folder(name, roll, folder, log)

        log("\n===== SUMMARY =====")
        log(f"Files changed: {changed}")
        log(f"Total replacements: {total}")
        log(f"Output: {out}")

        messagebox.showinfo("Done", "Completed")

    tk.Label(root, text="Full Name").pack()
    tk.Entry(root, textvariable=name_var).pack()

    tk.Label(root, text="Roll Number").pack()
    tk.Entry(root, textvariable=roll_var).pack()

    tk.Label(root, text="Folder").pack()
    frame = tk.Frame(root)
    frame.pack()

    tk.Entry(frame, textvariable=folder_var, width=40).pack(side=tk.LEFT)
    tk.Button(frame, text="Browse", command=browse).pack(side=tk.LEFT)

    tk.Button(root, text="Start", command=start).pack(pady=10)

    output = tk.Text(root)
    output.pack(fill=tk.BOTH, expand=True)

    root.mainloop()


if __name__ == "__main__":
    launch_gui()
