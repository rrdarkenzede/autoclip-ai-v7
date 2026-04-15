import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import sys
import threading
import time
import traceback

# Setup basic error logging for the notifier
def log_notifier_error(err_msg):
    try:
        with open("notifier_error.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.ctime()}] {err_msg}\n")
    except:
        pass

def is_process_running(pid):
    """Checks if a process with the given PID is running on Windows."""
    try:
        # Use tasklist to check if PID exists
        output = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /FO CSV', shell=True).decode('utf-8', errors='ignore')
        return str(pid) in output
    except:
        return False

def get_main_pid():
    """Reads the PID from main.pid file or searches by window title."""
    pid_file = "main.pid"
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
                if is_process_running(pid):
                    return pid
        except:
            pass
    
    # Fallback to window title
    try:
        output = subprocess.check_output('tasklist /V /FI "IMAGENAME eq cmd.exe" /FO CSV', shell=True).decode('utf-8', errors='ignore')
        if "AutoClipAI_Main_Pipeline" in output:
             return "WindowActive"
    except:
        pass
        
    return None

def stop_ai():
    """Kills the main AI process and children."""
    try:
        # Kill by PID if possible
        pid_file = "main.pid"
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid = f.read().strip()
                    subprocess.run(f'taskkill /F /PID {pid} /T', shell=True, capture_output=True)
            except:
                pass

        # Cleanup: Kill window title and any python processes just in case
        subprocess.run('taskkill /F /FI "WINDOWTITLE eq AutoClipAI_Main_Pipeline*" /T', shell=True, capture_output=True)
        subprocess.run('taskkill /F /IM python.exe /T', shell=True, capture_output=True)
        
        messagebox.showinfo("AutoClipAI", "L'IA a été arrêtée avec succès.")
        if os.path.exists(pid_file):
            try: os.remove(pid_file)
            except: pass
        os._exit(0)
    except Exception as e:
        log_notifier_error(f"Error in stop_ai: {e}")
        messagebox.showerror("Erreur", f"Impossible d'arrêter l'IA: {e}")

def monitor_main(root):
    # Wait a bit for main.py to start and create the PID file
    time.sleep(5)
    while True:
        try:
            time.sleep(3)
            if get_main_pid() is None:
                log_notifier_error("Main process not detected, closing notifier.")
                root.after(0, root.destroy)
                break
        except:
            pass

def main():
    try:
        root = tk.Tk()
        root.title("AutoClipAI Status")
        root.geometry("320x140")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        
        bg_color = "#121212"
        fg_color = "#ffffff"
        accent_color = "#e53935"
        
        root.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("Segoe UI", 11, "bold"))
        
        frame = ttk.Frame(root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        label = ttk.Label(frame, text="🤖 AutoClipAI : ACTIF", style="TLabel")
        label.pack(pady=(0, 10))
        
        stop_btn = tk.Button(
            frame, 
            text="🛑 STOPPER L'IA", 
            command=stop_ai,
            bg=accent_color,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            activebackground="#b71c1c",
            activeforeground="white"
        )
        stop_btn.pack(pady=5)
        
        info = ttk.Label(frame, text="(Réduis-moi, ne me ferme pas)", font=("Segoe UI", 8), foreground="#757575")
        info.pack(pady=(10, 0))

        # Position bottom right
        try:
            screen_width = root.winfo_screenwidth()
            screen_height = root.winfo_screenheight()
            root.geometry(f"+{screen_width - 340}+{screen_height - 180}")
        except:
            pass

        monitor_thread = threading.Thread(target=monitor_main, args=(root,), daemon=True)
        monitor_thread.start()

        root.mainloop()
    except Exception as e:
        log_notifier_error(f"Fatal error in notifier UI: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
