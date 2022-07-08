from dataclasses import dataclass
from typing import Dict, List, Union
from smdb_api import API, Message
import time
import json
import os
import sys
from datetime import datetime, timedelta
from hashlib import md5
from smdb_logger import Logger

service_mode = True if sys.argv[-1] == "SERVICE" else False
logger = Logger(
    "smdb_backup.log", level="DEBUG", log_folder=("/var/log" if service_mode else "."), log_to_console=True, storage_life_extender_mode=True)


@dataclass
class Settings:
    saved: str
    folder_from: str
    folder_to: str
    folders_for_admins: Dict[str, List[str]]
    sleep_time: int
    log_folder: str
    log_level: str
    user_to_own: Union[str, None]
    group_to_own: Union[str, None]


def walk(_path):
    _files = {}
    try:
        for fname in os.listdir(_path):
            inner_path = os.path.join(_path, fname)
            if os.path.isfile(inner_path):
                _files[os.path.abspath(inner_path)] = os.path.getmtime(
                    inner_path)
            else:
                _files.update(walk(inner_path))
        else:
            return _files
    except Exception as ex:
        logger.error(f"Exception occured in 'walk': {type(ex)} -> {ex}")


def check_folder(folder):
    if os.path.exists(folder):
        content = md5(str(walk(folder)).encode(encoding='utf-8')).hexdigest()
        logger.debug(f"{content} --> {settings.saved}")
        try:
            if content != settings.saved:
                create_backup(content, folder)
        except Exception as ex:
            logger.error(
                f"Error occured in 'check_folder': {type(ex)} -> {ex}")
            create_backup(content, folder)
    else:
        logger.error(f"Folder '{folder}' not found!")


def old_backup(limit=31536000):  # 1 év
    try:
        obc = walk(settings.folder_to)
        for key, value in obc.items():
            logger.debug(
                f"Comparing {datetime.now()} --> {datetime.fromtimestamp(value)}")
            if datetime.now() - datetime.fromtimestamp(value) >= timedelta(seconds=limit):
                logger.info(
                    f"'{key}' was older than the limit ({timedelta(seconds=limit)})")
                os.remove(key)
    except Exception as ex:
        logger.error(f"Error occured in 'old_backup': {type(ex)} -> {ex}")


def create_backup(status, folder):
    import shutil
    backup_name = os.path.join(
        settings.folder_to, f"Backup-{datetime.now().date()}")
    logger.debug(f"Creating backup to '{backup_name}'")
    shutil.make_archive(backup_name, 'zip', root_dir=f"{folder}")
    logger.info("Backup created!")
    save_status(status)
    old_backup()


def save_status(status):
    settings.saved = status
    save_settings()


def save_settings():
    with open("settings.cfg", "w", encoding="utf-8") as f:
        json.dump(settings.__dict__, f)


def files_sent(message: Message):
    try:
        if api.is_admin(message.sender) and message.has_attachments():
            logger.debug(
                f"Incoming file from user {api.get_username(message.sender)}")
            folder = os.path.join(
                settings.folder_from, settings.folders_for_admins[message.sender], message.content if message.content is not None else "")
            if not os.path.exists(folder):
                os.mkdir(folder)
            for attachment in message.attachments:
                file_path = attachment.save(folder)
                if settings.user_to_own is not None:
                    os.system(
                        ["sudo", "chown", settings.user_to_own, file_path])
                if settings.group_to_own is not None:
                    os.system(
                        ["sudo", "chgroup", settings.user_to_own, file_path])
                if settings.group_to_own is not None or settings.user_to_own is not None:
                    os.system(["sudo", "chgroup", "777", file_path])
                logger.debug(f"File saved to {file_path}")
        return
    except Exception as ex:
        logger.error(f"Error in downloading file: {ex}")


def add_admin_folder(message: Message):
    try:
        if api.is_admin(message.sender):
            settings.folders_for_admins[message.sender] = message.content
            if not os.path.exists(os.path.join(settings.folder_from, message.content)):
                os.mkdir(os.path.join(settings.folder_from, message.content))
        save_settings()
        return
    except Exception as ex:
        logger.error(f"Error in adding admin: {ex}")


def create_default_settings():
    global settings
    logger.debug("Creating default settings")
    settings = Settings("", "FOLDER/FOR/UNZIPPED/FILES",
                        "FOLDER/FOR/ZIP/SAVES", {}, 20, "/var/log", "INFO")
    with open("settings.cfg", "w", encoding="utf-8") as f:
        json.dump(settings.__dict__, f)


def load():
    cfg_path = "settings.cfg"
    if not os.path.exists(cfg_path):
        logger.error("Settings file not found!")
        create_default_settings()
        logger.info(
            f"Default settings file created, you can find it in {os.path.abspath(os.path.curdir)}/settings.cfg")
        exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        _settings = json.load(f)
    global settings
    settings = Settings(_settings["saved"], _settings["folder_from"], _settings["folder_to"],
                        _settings["folders_for_admins"], _settings["sleep_time"], _settings["log_folder"],
                        _settings["log_level"], _settings["user_to_own"], _settings["group_to_own"])


def main():
    api.validate()
    api.create_function(
        "Backup", "Creates a backup of the sent file in the admin user's folder.\nUsage: &Backup <additional folder name under your folder if needed> [attached file(s)]\nCategory: HARDWARE", files_sent)
    api.create_function(
        "AddAdmin", "Adds a folder for the admin user.\nUsage: &AddAdmin <folder name for the admin user>\nCategory: HARDWARE", add_admin_folder)
    logger.debug("Api calls created")
    while True:
        check_folder(settings.folder_from)
        time.sleep(settings.sleep_time)


if __name__ == "__main__":
    api = API(
        "Backup", "705663eec52de5a580c48a2a42c11b050dbfc40b475c9900e1475fe4b1a4fdc2")
    settings: Settings
    logger.header(
        f"Started in {'service' if service_mode else 'console'} mode")
    try:
        load()
        logger.debug("Settings loaded")
        logger.log_folder = settings.log_folder
        logger.set_level(level=settings.log_level)
        logger.flush_buffer()
        logger.storage_life_extender_mode = False
        main()
    except KeyboardInterrupt:
        logger.info("User stopped the program")
    except Exception as ex:
        logger.error(f"Exception happaned: {ex}")
    finally:
        logger.flush_buffer()
