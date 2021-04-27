import smdb_api, logger, time, json, os, writer, platform
import PySimpleGUI as sg
from datetime import datetime, timedelta
from hashlib import md5

lg = logger.logger("backup")
saved = ""
folder_from = ""
folder_to = ""
folders_for_admins = {}
api = smdb_api.API("Backup", "705663eec52de5a580c48a2a42c11b050dbfc40b475c9900e1475fe4b1a4fdc2")

def split(text, error=False, log_only=False, print_only=False):
    """Logs to both stdout and a log file, using both the writer, and the logger module
    """
    if not log_only: writer.write(text)
    if not print_only: lg.log(text, error=error)

writer = writer.writer("Backup")
print = split   #Changed print to the split function

def walk(_path):
    _files = {}
    try:
        for fname in os.listdir(_path):
            inner_path = os.path.join(_path, fname)
            if os.path.isfile(inner_path):
                _files[os.path.abspath(inner_path)] = os.path.getmtime(inner_path)
            else:
                _files.update(walk(inner_path))
        else:
            return _files
    except Exception as ex:
        print(f"Exception occured in 'walk': {type(ex)} -> {ex}", error=True)

def check_folder(folder):
    if os.path.exists(folder):
        content = md5(str(walk(folder)).encode(encoding='utf-8')).hexdigest()
        print(f"{content} --> {saved}", print_only=True)
        try:
            if content != saved:
                create_backup(content, folder)
        except Exception as ex:
            print(f"Error occured in 'check_folder': {type(ex)} -> {ex}", error=True)
            create_backup(content, folder)
    else:
        print("Folder not found!")

def old_backup(limit=31536000): #1 év
    try:
        obc = walk(folder_to)
        for key, value in obc.items():
            print(f"Comparing {datetime.now()} --> {datetime.fromtimestamp(value)}", print_only=True)
            if datetime.now() - datetime.fromtimestamp(value) >= timedelta(seconds=limit):
                print(f"'{key}' was older than the limit ({timedelta(seconds=limit)})", log_only=True)
                os.remove(key)
    except Exception as ex:
        print(f"Error occured in 'old_backup': {type(ex)} -> {ex}", error=True)

def create_backup(status, folder):
    import shutil
    print("Creating backup", print_only=True)
    shutil.make_archive(os.path.join(folder_to, f"Backup-{datetime.now().date()}"), 'zip', root_dir=f"{folder}")
    print("Backup created!")
    save_status(status)
    old_backup()

def save_status(status):
    global saved
    saved = status
    save_settings()

def save_settings():
    with open("backup.cfg", "w", encoding="utf-8") as f:
        json.dump({"saved": saved, "folder_from": folder_from, "folder_to": folder_to, "folder_for_admins": folders_for_admins}, f)
        
def files_sent(message):
    if api.is_admin(message.sender) and message.has_attachments():
        print(f"Incoming file from user {api.get_username(message.sender)}", print_only=True)
        folder = os.path.join(folder_from, folders_for_admins[message.sender], message.content if message.content is not None else "")
        if not os.path.exists(folder): os.mkdir(folder)
        for attachment in message.attachments:
            file_path = attachment.save(folder)
            print(f"File saved to {file_path}", log_only=True)
    return

def add_admin_folder(message):
    if api.is_admin(message.sender):
        folders_for_admins[message.sender] = message.content
        if not os.path.exists(os.path.join(folder_from, message.content)): os.mkdir(os.path.join(folder_from, message.content))
    save_settings()
    return

class UI:
    def __init__(self):
        sg.theme("dark")
        layout = [
            [sg.Text(f"Select a folder where files are being saved:"), sg.FolderBrowse(key="folder_from")],
            [sg.Text(f"Select a folder where files are going to be backed up to:"), sg.FolderBrowse(key="folder_to")],
            [sg.Button("Save", key="SAVE")]
        ]
        self.window = sg.Window("Warning", layout, finalize=True, keep_on_top=True)
        self.read = self.window.read
        self.is_running = True

    def close(self):
        self.is_running = False
        self.window.Close()

    def work(self, event, values):
        if event == sg.WINDOW_CLOSED:
            self.close()
        elif event == "SAVE":
            with open("backup.cfg", "w", encoding="utf-8") as f:
               json.dump({"saved": "", "folder_from": values["folder_from"], "folder_to": values["folder_to"], "folder_for_admins": {}}, f)
            self.close()

    def show(self):
        while True:
            event, values = self.read()
            self.work(event, values)
            if not self.is_running:
                self.close()
                break
        
def load():
    if not os.path.exists("backup.cfg"): 
        ui = UI()
        ui.show()
    if not os.path.exists("backup.cfg"): exit(1)
    with open("backup.cfg", "r", encoding="utf-8") as f:
        settings = json.load(f)
    global saved
    global folder_from
    global folder_to
    global folders_for_admins
    saved = settings["saved"]
    folder_from = settings["folder_from"].replace("/", "\\") if platform.system() == "Windows" else settings["folder_from"]
    folder_to = settings["folder_to"].replace("/", "\\") if platform.system() == "Windows" else settings["folder_to"]
    folders_for_admins = settings["folder_for_admins"]

def main(sleep_time):
    api.validate()
    load()
    api.create_function("Backup", "Creates a backup of the sent file in the admin user's folder.\nUsage: &Backup <additional folder name if needed> [attached file(s)]\nCategory: HARDWARE", files_sent)
    api.create_function("AddAdmin", "Adds a folder for the admin user.\nUsage: &AddAdmin <folder name for the admin user>\nCategory: HARDWARE", add_admin_folder)
    while True:
        check_folder(folder_from)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main(int(os.sys.argv[1]) if len(os.sys.argv) > 1 else 20)