import logging
import os
import re
import subprocess
import sys
import time

from .adapter.adb import ADB
from .app import App
from .intent import Intent
from .device_state import DeviceState

DEFAULT_NUM = '1234567890'
DEFAULT_CONTENT = 'Hello world!'


class Device(object):
    """
    this class describes a connected device
    """

    def __init__(self, device_serial=None, is_emulator=False, output_dir=None):
        """
        initialize a device connection
        :param device_serial: serial number of target device
        :param is_emulator: boolean, type of device, True for emulator, False for real device
        :return:
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        if device_serial is None:
            from .utils import get_available_devices
            all_devices = get_available_devices()
            if len(all_devices) == 0:
                self.logger.warning("ERROR: No device connected.")
                sys.exit(-1)
            device_serial = all_devices[0]
        if "emulator" in device_serial and not is_emulator:
            self.logger.warning("Seems like you are using an emulator. If so, please add is_emulator option.")
        self.serial = device_serial
        self.is_emulator = is_emulator
        self.output_dir = output_dir
        if output_dir is not None:
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)

        self.settings = {}
        self.display_info = None
        self.model_number = None
        self.sdk_version = None
        self.release_version = None
        self.ro_debuggable = None
        self.ro_secure = None
        self.connected = True
        self.last_know_state = None

        self.adb = ADB(device=self)

        self.adapters = {
            self.adb: True
        }

    def check_connectivity(self):
        """
        check if the device is available
        """
        for adapter in self.adapters:
            adapter_name = adapter.__class__.__name__
            adapter_enabled = self.adapters[adapter]
            if not adapter_enabled:
                print("[CONNECTION] %s is not enabled." % adapter_name)
            else:
                if adapter.check_connectivity():
                    print("[CONNECTION] %s is enabled and connected." % adapter_name)
                else:
                    print("[CONNECTION] %s is enabled but not connected." % adapter_name)

    def wait_for_device(self):
        """
        wait until the device is fully booted
        :return:
        """
        self.logger.info("waiting for device")
        try:
            subprocess.check_call(["adb", "-s", self.serial, "wait-for-device"])
        except:
            self.logger.warning("error waiting for device")

    def set_up(self):
        """
        Set connections on this device
        """
        # wait for emulator to start
        self.wait_for_device()
        for adapter in self.adapters:
            adapter_enabled = self.adapters[adapter]
            if not adapter_enabled:
                continue
            adapter.set_up()

    def connect(self):
        """
        establish connections on this device
        :return:
        """
        for adapter in self.adapters:
            adapter_enabled = self.adapters[adapter]
            if not adapter_enabled:
                continue
            adapter.connect()

        self.get_sdk_version()
        self.get_release_version()
        self.get_ro_secure()
        self.get_ro_debuggable()
        self.get_display_info()

        self.unlock()
        self.check_connectivity()
        self.connected = True

    def disconnect(self):
        """
        disconnect current device
        :return:
        """
        self.connected = False
        for adapter in self.adapters:
            adapter_enabled = self.adapters[adapter]
            if not adapter_enabled:
                continue
            adapter.disconnect()

        if self.output_dir is not None:
            temp_dir = os.path.join(self.output_dir, "temp")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)

    def tear_down(self):
        for adapter in self.adapters:
            adapter_enabled = self.adapters[adapter]
            if not adapter_enabled:
                continue
            adapter.tear_down()

    def is_foreground(self, app):
        """
        check if app is in foreground of device
        :param app: App
        :return: boolean
        """
        if isinstance(app, str):
            package_name = app
        elif isinstance(app, App):
            package_name = app.get_package_name()
        else:
            return False

        top_activity_name = self.get_top_activity_name()
        if top_activity_name is None:
            return False
        return top_activity_name.startswith(package_name)

    def get_model_number(self):
        """
        Get model number
        """
        if self.model_number is None:
            self.model_number = self.adb.get_model_number()
        return self.model_number

    def get_sdk_version(self):
        """
        Get version of current SDK
        """
        if self.sdk_version is None:
            self.sdk_version = self.adb.get_sdk_version()
        return self.sdk_version

    def get_release_version(self):
        """
        Get version of current SDK
        """
        if self.release_version is None:
            self.release_version = self.adb.get_release_version()
        return self.release_version

    def get_ro_secure(self):
        if self.ro_secure is None:
            self.ro_secure = self.adb.get_ro_secure()
        return self.ro_secure

    def get_ro_debuggable(self):
        if self.ro_debuggable is None:
            self.ro_debuggable = self.adb.get_ro_debuggable()
        return self.ro_debuggable

    def get_display_info(self, refresh=True):
        """
        get device display information, including width, height, and density
        :param refresh: if set to True, refresh the display info instead of using the old values
        :return: dict, display_info
        """
        if self.display_info is None or refresh:
            self.display_info = self.adb.get_display_info()
        return self.display_info

    def get_width(self, refresh=False):
        display_info = self.get_display_info(refresh=refresh)
        width = 0
        if "width" in display_info:
            width = display_info["width"]
        elif not refresh:
            width = self.get_width(refresh=True)
        else:
            self.logger.warning("get_width: width not in display_info")
        return width

    def get_height(self, refresh=False):
        display_info = self.get_display_info(refresh=refresh)
        height = 0
        if "height" in display_info:
            height = display_info["height"]
        elif not refresh:
            height = self.get_width(refresh=True)
        else:
            self.logger.warning("get_height: height not in display_info")
        return height

    def unlock(self):
        """
        unlock screen
        skip first-use tutorials
        etc
        :return:
        """
        self.adb.unlock()

    def send_intent(self, intent):
        """
        send an intent to device via am (ActivityManager)
        :param intent: instance of Intent or str
        :return:
        """
        assert self.adb is not None
        assert intent is not None
        if isinstance(intent, Intent):
            cmd = intent.get_cmd()
        else:
            cmd = intent
        return self.adb.shell(cmd)

    def send_event(self, event):
        """
        send one event to device
        :param event: the event to be sent
        :return:
        """
        event.send(self)

    def start_app(self, app):
        """
        start an app on the device
        :param app: instance of App, or str of package name
        :return:
        """
        if isinstance(app, str):
            package_name = app
        elif isinstance(app, App):
            package_name = app.get_package_name()
            if app.get_main_activity():
                package_name += "/%s" % app.get_main_activity()
        else:
            self.logger.warning("unsupported param " + app + " with type: ", type(app))
            return
        intent = Intent(suffix=package_name)
        self.send_intent(intent)

    def get_top_activity_name(self):
        """
        Get current activity
        """
        r = self.adb.shell("dumpsys activity activities")
        # activity_line_re = re.compile('\* Hist #\d+: ActivityRecord{[^ ]+ [^ ]+ ([^ ]+) t(\d+)}')
        activity_line_re = re.compile('\* Hist\s+#\d+: ActivityRecord{[^ ]+ [^ ]+ ([^ ]+) t(\d+)}')
        m = activity_line_re.search(r)
        if m:
            return m.group(1)
        # data = self.adb.shell("dumpsys activity top").splitlines()
        # regex = re.compile("\s*ACTIVITY ([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)")
        # m = regex.search(data[1])
        # if m:
        #     return m.group(1) + "/" + m.group(2)
        self.logger.warning("Unable to get top activity name.")
        return None

    def get_current_activity_stack(self):
        """
        Get current activity stack
        :return: a list of str, each str is an activity name, the first is the top activity name
        """
        task_to_activities = self.get_task_activities()
        top_activity = self.get_top_activity_name()
        if top_activity:
            for task_id in task_to_activities:
                activities = task_to_activities[task_id]
                if len(activities) > 0 and activities[0] == top_activity:
                    return activities
            self.logger.warning("Unable to get current activity stack.")
            return [top_activity]
        else:
            return None

    def get_task_activities(self):
        """
        Get current tasks and corresponding activities.
        :return: a dict mapping each task id to a list of activities, from top to down.
        """
        task_to_activities = {}

        lines = self.adb.shell("dumpsys activity activities").splitlines()
        # activity_line_re = re.compile('\* Hist #\d+: ActivityRecord{[^ ]+ [^ ]+ ([^ ]+) t(\d+)}')
        activity_line_re = re.compile('\* Hist\s+#\d+: ActivityRecord{[^ ]+ [^ ]+ ([^ ]+) t(\d+)}')

        for line in lines:
            line = line.strip()
            if line.startswith("Task id #"):
                task_id = line[9:]
                task_to_activities[task_id] = []
            # elif line.startswith("* Hist #"):
            elif line.startswith("* Hist #") or line.startswith("* Hist  #"):
                m = activity_line_re.match(line)
                if m:
                    activity = m.group(1)
                    task_id = m.group(2)
                    if task_id not in task_to_activities:
                        task_to_activities[task_id] = []
                    task_to_activities[task_id].append(activity)

        return task_to_activities

    def get_service_names(self):
        """
        get current running services
        :return: list of services
        """
        services = []
        dat = self.adb.shell('dumpsys activity services')
        lines = dat.splitlines()
        service_re = re.compile('^.+ServiceRecord{.+ ([A-Za-z0-9_.]+)/([A-Za-z0-9_.]+)')

        for line in lines:
            m = service_re.search(line)
            if m:
                package = m.group(1)
                service = m.group(2)
                services.append("%s/%s" % (package, service))
        return services

    def get_package_path(self, package_name):
        """
        get installation path of a package (app)
        :param package_name:
        :return: package path of app in device
        """
        dat = self.adb.shell('pm path %s' % package_name)
        package_path_re = re.compile('^package:(.+)$')
        m = package_path_re.match(dat)
        if m:
            path = m.group(1)
            return path.strip()
        return None

    def start_activity_via_monkey(self, package):
        """
        use monkey to start activity
        @param package: package name of target activity
        """
        cmd = 'monkey'
        if package:
            cmd += ' -p %s' % package
        out = self.adb.shell(cmd)
        if re.search(r"(Error)|(Cannot find 'App')", out, re.IGNORECASE | re.MULTILINE):
            raise RuntimeError(out)

    def install_app(self, app):
        """
        install an app to device
        @param app: instance of App
        @return:
        """
        assert isinstance(app, App)
        # subprocess.check_call(["adb", "-s", self.serial, "uninstall", app.get_package_name()],
        #                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        package_name = app.get_package_name()
        if package_name not in self.adb.get_installed_apps():
            install_cmd = ["adb", "-s", self.serial, "install", "-r"]
            install_cmd.append(app.app_path)
            install_p = subprocess.Popen(install_cmd, stdout=subprocess.PIPE)
            while self.connected and package_name not in self.adb.get_installed_apps():
                print("Please wait while installing the app...")
                time.sleep(2)
            if not self.connected:
                install_p.terminate()
                return

        dumpsys_p = subprocess.Popen(["adb", "-s", self.serial, "shell",
                                      "dumpsys", "package", package_name], stdout=subprocess.PIPE)
        dumpsys_lines = []
        while True:
            line = dumpsys_p.stdout.readline()
            if not line:
                break
            if not isinstance(line, str):
                line = line.decode()
            dumpsys_lines.append(line)
        if self.output_dir is not None:
            package_info_file_name = "%s/dumpsys_package_%s.txt" % (self.output_dir, app.get_package_name())
            package_info_file = open(package_info_file_name, "w")
            package_info_file.writelines(dumpsys_lines)
            package_info_file.close()
        app.dumpsys_main_activity = self.__parse_main_activity_from_dumpsys_lines(dumpsys_lines)

        self.logger.info("App installed: %s" % package_name)
        self.logger.info("Main activity: %s" % app.get_main_activity())

    @staticmethod
    def __parse_main_activity_from_dumpsys_lines(lines):
        main_activity = None
        activity_line_re = re.compile("[^ ]+ ([^ ]+)/([^ ]+) filter [^ ]+")
        action_re = re.compile("Action: \"([^ ]+)\"")
        category_re = re.compile("Category: \"([^ ]+)\"")

        activities = {}

        cur_package = None
        cur_activity = None
        cur_actions = []
        cur_categories = []

        for line in lines:
            line = line.strip()
            m = activity_line_re.match(line)
            if m:
                activities[cur_activity] = {
                    "actions": cur_actions,
                    "categories": cur_categories
                }
                cur_package = m.group(1)
                cur_activity = m.group(2)
                if cur_activity.startswith("."):
                    cur_activity = cur_package + cur_activity
                cur_actions = []
                cur_categories = []
            else:
                m1 = action_re.match(line)
                if m1:
                    cur_actions.append(m1.group(1))
                else:
                    m2 = category_re.match(line)
                    if m2:
                        cur_categories.append(m2.group(1))

        if cur_activity is not None:
            activities[cur_activity] = {
                "actions": cur_actions,
                "categories": cur_categories
            }

        for activity in activities:
            if "android.intent.action.MAIN" in activities[activity]["actions"] \
                    and "android.intent.category.LAUNCHER" in activities[activity]["categories"]:
                main_activity = activity
        return main_activity

    def uninstall_app(self, app):
        """
        Uninstall an app from device.
        :param app: an instance of App or a package name
        """
        if isinstance(app, App):
            package_name = app.get_package_name()
        else:
            package_name = app
        if package_name in self.adb.get_installed_apps():
            uninstall_cmd = ["adb", "-s", self.serial, "uninstall", package_name]
            uninstall_p = subprocess.Popen(uninstall_cmd, stdout=subprocess.PIPE)
            while package_name in self.adb.get_installed_apps():
                print("Please wait while uninstalling the app...")
                time.sleep(2)
            uninstall_p.terminate()

    def get_app_pid(self, app):
        if isinstance(app, App):
            package = app.get_package_name()
        else:
            package = app

        name2pid = {}
        ps_out = self.adb.shell(["ps"])
        ps_out_lines = ps_out.splitlines()
        ps_out_head = ps_out_lines[0].split()
        if ps_out_head[1] != "PID" or ps_out_head[-1] != "NAME":
            self.logger.warning("ps command output format error: %s" % ps_out_head)
        for ps_out_line in ps_out_lines[1:]:
            segs = ps_out_line.split()
            if len(segs) < 4:
                continue
            pid = int(segs[1])
            name = segs[-1]
            name2pid[name] = pid

        if package in name2pid:
            return name2pid[package]

        possible_pids = []
        for name in name2pid:
            if name.startswith(package):
                possible_pids.append(name2pid[name])
        if len(possible_pids) > 0:
            return min(possible_pids)

        return None

    def push_file(self, local_file, remote_dir="/sdcard/"):
        """
        push file/directory to target_dir
        :param local_file: path to file/directory in host machine
        :param remote_dir: path to target directory in device
        :return:
        """
        if not os.path.exists(local_file):
            self.logger.warning("push_file file does not exist: %s" % local_file)
        self.adb.run_cmd(["push", local_file, remote_dir])

    def pull_file(self, remote_file, local_file):
        self.adb.run_cmd(["pull", remote_file, local_file])
    
    def get_current_state(self) -> DeviceState:
        self.logger.debug("getting current device state...")
        current_state = None
        try:
            views, xml_data = self.get_views()
            # print(views[:-10])
            # print(xml_data)
            foreground_activity = self.get_top_activity_name()
            activity_stack = self.get_current_activity_stack()
            background_services = self.get_service_names()
            self.logger.debug("finish getting current device state...")
            current_state = DeviceState(self,
                                        views=views,
                                        foreground_activity=foreground_activity,
                                        activity_stack=activity_stack,
                                        background_services=background_services,
                                        xml_tree=xml_data
                                        )
        except Exception as e:
            self.logger.warning("exception in get_current_state: %s" % e)
            import traceback
            traceback.print_exc()
        self.logger.debug("finish getting current device state...")
        self.last_know_state = current_state
        if not current_state:
            self.logger.warning("Failed to get current state!")
        return current_state

    def get_last_known_state(self):
        return self.last_know_state

    def view_touch(self, x, y):
        self.adb.touch(x, y)

    def view_long_touch(self, x, y, duration=2000):
        """
        Long touches at (x, y)
        @param duration: duration in ms
        This workaround was suggested by U{HaMi<http://stackoverflow.com/users/2571957/hami>}
        """
        self.adb.long_touch(x, y, duration)

    def view_drag(self, start_xy, end_xy, duration):
        """
        Sends drag event n PX (actually it's using C{input swipe} command.
        """
        self.adb.drag(start_xy, end_xy, duration)

    def view_set_text(self, text):
        self.adb.type(text)
    
    def key_press(self, key_code):
        self.adb.press(key_code)

    def shutdown(self):
        self.adb.shell("reboot -p")

    def get_views(self):
        from app_hierarchy.provider import AndroidProvider
        provider = AndroidProvider()
        driver = provider.get_single_device_driver()
        xml_data, view_tree = driver.dump_hierarchy()
        views = []
        def __nodes_to_list(node, nodes_list:list):
            tree_id = len(nodes_list)
            node.properties['temp_id'] = tree_id

            if "bounds" and "hint" and "drawing-order" in node.properties:
                del node.properties["bounds"]
                del node.properties["hint"]
                del node.properties["drawing-order"]
            node.properties["bounds"] = node.rect         
            nodes_list.append(node.properties)                  
            children_ids = []
            for child_node in node.children:
                if "bounds" and "hint" and "drawing-order" in child_node.properties:
                    del child_node.properties["bounds"]
                    del child_node.properties["hint"]
                    del child_node.properties["drawing-order"]
                child_node.properties["bounds"] = child_node.rect  
                child_node.properties['parent'] = tree_id
                __nodes_to_list(child_node, nodes_list)
                children_ids.append(child_node.properties['temp_id'])
            node.properties['children'] = children_ids
        
        view_tree.properties['temp_id'] = -1
        views = []
        __nodes_to_list(view_tree, views)

        if views:
            return views, xml_data
        else:
            self.logger.warning("Failed to get views using Accessibility.")
        self.logger.warning("failed to get current views!")
        return None