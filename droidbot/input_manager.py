import json
import logging
import subprocess
import time

from .input_event import EventLog
from .input_policy import UtgBasedInputPolicy, TaskPolicy, POLICY_TASK

DEFAULT_POLICY = POLICY_TASK
DEFAULT_EVENT_INTERVAL = 1
DEFAULT_EVENT_COUNT = 100000000
DEFAULT_TIMEOUT = -1


class UnknownInputException(Exception):
    pass


class InputManager(object):
    """
    This class manages all events to send during app running
    """

    def __init__(self, device, app, task, policy_name,
                 event_count, event_interval, output_dir):
        """
        manage input event sent to the target device
        :param device: instance of Device
        :param app: instance of App
        :param policy_name: policy of generating events, string
        :return:
        """
        self.logger = logging.getLogger('InputEventManager')
        self.enabled = True

        self.device = device
        self.app = app
        self.task = task
        self.policy_name = policy_name
        self.events = []
        self.policy = None
        self.event_count = event_count
        self.event_interval = event_interval

        self.event = None
        self.from_state = None
        self.event_str = None
        self.policy = self.get_input_policy(device, app, output_dir)

    def get_input_policy(self, device, app, output_dir):
        if self.policy_name == POLICY_TASK:
            input_policy = TaskPolicy(device, app, output_dir, task=self.task, use_memory=False)
        else:
            self.logger.warning("No valid input policy specified. Using policy \"none\".")
            input_policy = None
        return input_policy

    def add_event(self, event):
        """
        add one event to the event list
        :param event: the event to be added, should be subclass of AppEvent
        :return:
        """
        if event is None:
            return
        self.events.append(event)

        self.event = event
        self.from_state = self.device.get_current_state()
        self.event_str = event.get_event_str(self.from_state)
        print("Action: %s" % self.event_str)
        self.device.send_event(self.event)

        if event.event_type == "intent" and event.intent[0:8] == "am start":
            time.sleep(10)
        else:
            # time.sleep(self.event_interval) # 1
            # time.sleep(3)
            time.sleep(5)
        
        self.to_state = self.device.get_current_state()

    def start(self):
        """
        start sending event
        """
        self.logger.info("start sending events, policy is %s" % self.policy_name)

        try:
            if self.policy is not None:
                self.policy.start(self)
        except KeyboardInterrupt:
            pass

        self.stop()
        self.logger.info("Finish sending events")

    def stop(self):
        """
        stop sending event
        """
        self.enabled = False

