"""Some codes are adapted from Autodroid, uiautomator2 and MobileGPT.
"""
import argparse
from droidbot import input_manager
from droidbot import DroidBot

import _locale
_locale._getdefaultlocale = (lambda *args: ['zh_CN', 'utf8'])


def parse_args():
    """
    parse command line input
    """
    parser = argparse.ArgumentParser(description="Start DroidBot to test an Android app.",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-d", action="store", dest="device_serial", required=False,
                        help="The serial number of target device (use `adb devices` to find)")
    parser.add_argument("-a", action="store", dest="apk_path",
                        help="The file path to target APK")
    parser.add_argument("-pn", action="store", dest="package_name", required=True,
                        help="The package name")
    parser.add_argument("-an", action="store", dest="app_name",
                        help="The app name")
    parser.add_argument("-o", action="store", dest="output_dir",
                        help="directory of output")
    parser.add_argument("-task", action="store", dest="task", default="mingle around",
                        help="the task to execute, in natural language")
    parser.add_argument("-count", action="store", dest="count", default=input_manager.DEFAULT_EVENT_COUNT, type=int,
                        help="Number of events to generate in total. Default: %d" % input_manager.DEFAULT_EVENT_COUNT)
    parser.add_argument("-interval", action="store", dest="interval", default=input_manager.DEFAULT_EVENT_INTERVAL,
                        type=int,
                        help="Interval in seconds between each two events. Default: %d" % input_manager.DEFAULT_EVENT_INTERVAL)
    parser.add_argument("-timeout", action="store", dest="timeout", default=input_manager.DEFAULT_TIMEOUT, type=int,
                        help="Timeout in seconds, -1 means unlimited. Default: %d" % input_manager.DEFAULT_TIMEOUT)
    parser.add_argument("-keep_app", action="store_true", dest="keep_app",
                        help="Keep the app on the device after testing.")
    parser.add_argument("-is_emulator", action="store_true", dest="is_emulator",
                        help="Declare the target device to be an emulator, which would be treated specially by DroidBot.")
    options = parser.parse_args()
    return options


def main():
    """
    the main function
    it starts a droidbot according to the arguments given in cmd line
    """
    opts = parse_args()

    droidbot = DroidBot(
        app_path=opts.apk_path,
        package_name=opts.package_name,
        app_name=opts.app_name,
        device_serial=opts.device_serial,
        task=opts.task,
        is_emulator=opts.is_emulator,
        output_dir=opts.output_dir,
        policy_name=input_manager.POLICY_TASK,
        event_count=opts.count,
        event_interval=opts.interval,
        keep_app=opts.keep_app)
    droidbot.start()


if __name__ == "__main__":
    main()
