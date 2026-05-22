import logging
import os
import hashlib
from .intent import Intent
import subprocess
import json

class App(object):
    """
    this class describes an app
    """

    def __init__(self, app_path=None, package_name=None, app_name=None, output_dir=None):
        """
        Create an App instance.

        :param app_path: Local file path of the APK (optional)
        :param package_name: Package name of the installed app (optional)
        :param output_dir: Directory to save output files
        """
        assert app_path or package_name, "Either 'app_path' or 'package_name' must be provided."
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_path = app_path
        self.package_name = package_name
        self.output_dir = output_dir

        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir)

        self.dumpsys_main_activity = None
        self.activities = []
        self.permissions = []
        self.app_name = app_name
        self.main_activity = None
        self.hashes = None

        if app_path:
            # Extract information from APK file
            from androguard.core.apk import APK
            self.apk = APK(app_path)
            self.package_name = self.apk.get_package()
            self.app_name = self.apk.get_app_name()
            self.main_activity = self.apk.get_main_activity()
            self.permissions = self.apk.get_permissions()
            self.activities = self.apk.get_activities()
            self.hashes = self.get_hashes()
        else:
            # Extract information from installed app using ADB
            self._fetch_app_info_from_device()

    def _run_adb_command(self, command):
        """
        Helper function to run ADB commands in Windows.
        """
        try:
            result = subprocess.run(command, capture_output=True, text=True, shell=True, encoding='utf-8', errors='ignore')
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _fetch_app_info_from_device(self):
        """
        Fetch package name, main activity, and permissions from an installed app using ADB.
        """
        if not self.package_name:
            self.logger.error("Package name is required to fetch data from the installed app.")
            return

        # Get main activity (Windows)
        self.main_activity = self._run_adb_command(f'adb shell cmd package resolve-activity --brief {self.package_name}')
        if self.main_activity and "/" in self.main_activity:
            self.main_activity = self.main_activity.split("/")[-1]
        else:
            self.main_activity = None
            self.logger.warning("Cannot get main activity from manifest. Using dumpsys result instead.")
            self.dumpsys_main_activity = self._run_adb_command(f'adb shell dumpsys activity activities | findstr "Hist"')        
        # print(self.main_activity)
        # print(self.dumpsys_main_activity)

        # Get permissions (Windows)
        self.permissions = self._run_adb_command(f'adb shell dumpsys package {self.package_name} | findstr "android.permission."')
        if self.permissions:
            self.permissions = [perm.strip() for perm in self.permissions.split("\n")]
        # print(self.permissions)


    def get_package_name(self):
        """
        Get package name of the current app.
        """
        return self.package_name

    def get_main_activity(self):
        """
        Get the main activity of the app.
        """
        return self.main_activity or self.dumpsys_main_activity

    def get_start_intent(self):
        """
        Get an intent to start the app.
        """
        package_name = self.get_package_name()
        if self.get_main_activity():
            package_name += f"/{self.get_main_activity()}"
        return Intent(suffix=package_name)

    def get_stop_intent(self):
        """
        Get an intent to stop the app.
        """
        package_name = self.get_package_name()
        return Intent(prefix="force-stop", suffix=package_name)

    def get_hashes(self, block_size=2**8):
        """
        Calculate MD5, SHA-1, and SHA-256 hashes of the APK file.
        """
        if not self.app_path:
            self.logger.warning("Cannot calculate hashes without APK file.")
            return None

        md5, sha1, sha256 = hashlib.md5(), hashlib.sha1(), hashlib.sha256()
        with open(self.app_path, 'rb') as f:
            while chunk := f.read(block_size):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)

        return [md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()]
