import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import sys
import os
import webbrowser
import re
FLASK_APP_FILE = 'app.py'

class FlaskLauncherApp:
    def __init__(self, master):
        self.master = master
        master.title("Service PC Web Server Launcher & Logger")
        master.geometry("800x600")
        
        self.flask_process = None
        
        control_frame = ttk.Frame(master, padding="10")
        control_frame.pack(fill=tk.X)

        self.start_button = ttk.Button(control_frame, text="Запустить Web-сервер", 
                                       command=self.start_server, style='Accent.TButton')
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(control_frame, text="Остановить Сервер", 
                                      command=self.stop_server, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(control_frame, text="Статус: Остановлен", 
                                      foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        log_frame = ttk.Frame(master, padding="10")
        log_frame.pack(expand=True, fill=tk.BOTH)
        
        ttk.Label(log_frame, text="Логи Web-сервера:").pack(fill=tk.X)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, 
                                                  state='disabled', height=25,
                                                  bg="#1e1e1e", fg="#ffffff",
                                                  font=("Consolas", 10))
        self.log_area.pack(expand=True, fill=tk.BOTH)
        
        self.log_area.tag_config("url", foreground="lightblue", underline=True)
        self.log_area.tag_bind("url", "<Button-1>", self.open_link) 
        self.log_area.tag_bind("url", "<Enter>", self.on_enter_link) 
        self.log_area.tag_bind("url", "<Leave>", self.on_leave_link) 

        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        style = ttk.Style()
        try:
             style.configure('Accent.TButton', foreground='green', font=('Helvetica', 10, 'bold'))
        except:
             pass

    def on_enter_link(self, event):
        """Меняет курсор на "руку" при наведении на ссылку."""
        self.log_area.config(cursor="hand2")

    def on_leave_link(self, event):
        """Возвращает курсор по умолчанию."""
        self.log_area.config(cursor="")

    def open_link(self, event):
        try:
            index = self.log_area.index(f"@{event.x},{event.y}")
            tag_indices = self.log_area.tag_prevrange("url", index) 
            
            if tag_indices:
                start, end = tag_indices
                url = self.log_area.get(start, end)
                
                if url:
                    self.log_message(f"\nОткрытие ссылки в браузере: {url}\n")
                    webbrowser.open_new_tab(url)

            
        except Exception as e:
            self.log_message(f"\nОшибка при открытии ссылки: {e}\n")


    def log_message(self, message, tag=None):
        self.log_area.configure(state='normal')
        
        start_char_index = self.log_area.index(tk.END)
        self.log_area.insert(tk.END, message)
        
        url_pattern = r'http[s]?://[^\s]+'
        
        for match in re.finditer(url_pattern, message):
            

            start_index_abs = self.log_area.index(f"{start_char_index} + {match.start()} chars")
            end_index_abs = self.log_area.index(f"{start_char_index} + {match.end()} chars")

            self.log_area.tag_add("url", start_index_abs, end_index_abs)

        self.log_area.see(tk.END) 
        self.log_area.configure(state='disabled')

    def read_output(self, pipe):
        encoding = sys.stdout.encoding or 'utf-8' 
        
        while self.flask_process and self.flask_process.poll() is None:
            try:
                line = pipe.readline()
                if not line:
                    break
                
                decoded_line = line.decode(encoding, errors='replace')
                
                self.master.after(0, self.log_message, decoded_line)
                
            except Exception as e:
                self.master.after(0, self.log_message, f"Ошибка чтения логов: {e}\n")
                break
        
        self.master.after(0, self.update_status_on_exit)

    def start_server(self):
        if not os.path.exists(FLASK_APP_FILE):
             self.log_message(f"ОШИБКА: Файл {FLASK_APP_FILE} не найден!\n")
             return

        self.log_area.delete('1.0', tk.END)
        self.log_message("--- ЗАПУСК СЕРВЕРА ---\n")
        
        try:
            self.flask_process = subprocess.Popen([sys.executable, FLASK_APP_FILE],
                                                  stdout=subprocess.PIPE,
                                                  stderr=subprocess.STDOUT,
                                                  shell=False)
            
            threading.Thread(target=self.read_output, args=(self.flask_process.stdout,), daemon=True).start()
            
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.status_label.config(text="Статус: РАБОТАЕТ", foreground="green")
            
        except Exception as e:
            self.log_message(f"ОШИБКА ЗАПУСКА: Не удалось запустить {FLASK_APP_FILE}. {e}\n")
            self.status_label.config(text="Статус: Остановлен (Ошибка)", foreground="red")

    def stop_server(self):
        if self.flask_process and self.flask_process.poll() is None:
            try:
                self.flask_process.terminate()
                self.flask_process.wait(timeout=5) 
                

                if self.flask_process.poll() is None:
                    self.flask_process.kill() 
                
            except Exception as e:
                self.log_message(f"Ошибка при попытке завершения процесса: {e}. Принудительное завершение.\n")
                if self.flask_process and self.flask_process.poll() is None:
                    self.flask_process.kill() 
            
        self.update_status_on_exit()
        self.log_message("--- СЕРВЕР ОСТАНОВЛЕН ---\n")


    def update_status_on_exit(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Статус: Остановлен", foreground="red")
        self.flask_process = None


    def on_closing(self):
        if self.flask_process and self.flask_process.poll() is None:
            self.log_message("Закрытие окна: Остановка сервера...\n")
            self.stop_server()
        self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = FlaskLauncherApp(root)
    root.mainloop()