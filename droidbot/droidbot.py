import logging
import os
import sys
from threading import Timer

from .device import Device
from .app import App
from .input_manager import InputManager


class DroidBot:
    """
    The main class of DroidBot, responsible for managing the interaction process
    with a mobile device and app based on specified configurations.
    """

    def __init__(self,
                 app_path=None,
                 package_name = None,
                 app_name = None,
                 device_serial=None,
                 task=None,
                 is_emulator=False,
                 output_dir=None,
                 policy_name=None,
                 event_count=None,
                 event_interval=None,
                 keep_app=None):
        """
        Initialize DroidBot with the provided configurations.
        :param app_path: Path to the application APK
        :param device_serial: Serial number of the device
        :param task: Task to be performed
        :param is_emulator: Boolean indicating if the device is an emulator
        :param output_dir: Directory to store output logs and files
        :param policy_name: Name of the input policy to use
        :param event_count: Number of events to generate
        :param event_interval: Interval between events
        :param keep_app: Boolean indicating if the app should remain installed
        """
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger('DroidBot')

        self.output_dir = output_dir
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

        self.keep_app = keep_app

        self.device = None
        self.app = None
        self.task = task
        self.input_manager = None

        self.enabled = True

        try:
            self.device = Device(
                device_serial=device_serial,
                is_emulator=is_emulator,
                output_dir=self.output_dir)
            self.app = App(app_path, package_name=package_name, app_name=app_name, output_dir=self.output_dir)

            self.input_manager = InputManager(
                device=self.device,
                app=self.app,
                task=self.task,
                policy_name=policy_name,
                event_count=event_count,
                event_interval=event_interval,
                output_dir=self.output_dir)
        except Exception as e:
            self.logger.error("Failed to initialize DroidBot: %s", str(e))
            self.stop()
            sys.exit(-1)

    def start(self):
        """
        Start the interaction process with the device and app.
        :return:
        """
        if not self.enabled:
            return

        self.logger.info("Starting DroidBot")
        try:

            self.device.set_up()

            if not self.enabled:
                return
            self.device.connect()

            if not self.enabled:
                return
            self.device.install_app(self.app)

            if not self.enabled:
                return
            self.input_manager.start()
        except KeyboardInterrupt:
            self.logger.info("DroidBot execution interrupted by the user.")
        except Exception as e:
            self.logger.error("An error occurred during DroidBot execution: %s", str(e))
            self.stop()
            sys.exit(-1)
        finally:
            self.stop()
            self.logger.info("DroidBot Stopped")

    def stop(self):
        """
        Stop the DroidBot execution and clean up resources.
        :return:
        """
        self.enabled = False
        if self.input_manager:
            self.input_manager.stop()
        if self.device:
            self.device.disconnect()
        if not self.keep_app and self.device and self.app:
            self.device.uninstall_app(self.app)


class DroidBotException(Exception):
    """Custom exception class for DroidBot-related errors."""
    pass
