import smdb_backup
from os import getcwdb
import subprocess

try:
    with open("smdb-backup.service.template", 'r') as f:
        service = f.read(-1)
    service = service.replace(
        "<folder_path>", f'{getcwdb().decode("utf-8")}').replace("file_name", "smdb_backup.py")
    with open("/etc/systemd/system/smdb-backup.service", "w") as f:
        f.write(service)
    subprocess.call(["sudo", "systemctl", "daemon-reload"])
    subprocess.call(["sudo", "systemctl", "enable",
                    "smdb-backup.service"])
    subprocess.call(["sudo", "systemctl", "start",
                    "smdb-backup.service"])
except Exception as ex:
    print("Service creation failed, please try starting this with sudo!")
