import sys
import json
import re
import logging
import random
from abc import abstractmethod
import copy
import requests
import ast
#RR calc
import tiktoken
import os
import base64

from .input_event import *
import time
from .input_event import ScrollEvent
import tools
from tools import *
import pdb
import os
from .device import Device
from .device_state import DeviceState
from .app import App
from .prompt import *
import subprocess
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from .locator import LocatorMethods
from tools import query_openai_LLM, extract_json, clean_json, extract_action, get_thought

# Max number of restarts
MAX_NUM_RESTARTS = 5
# Max number of steps outside the app
MAX_NUM_STEPS_OUTSIDE = 1000
MAX_NUM_STEPS_OUTSIDE_KILL = 1000
# Max number of replay tries
MAX_REPLY_TRIES = 5

# Some input event flags
EVENT_FLAG_STARTED = "+started"
EVENT_FLAG_START_APP = "+start_app"
EVENT_FLAG_STOP_APP = "+stop_app"
EVENT_FLAG_EXPLORE = "+explore"
EVENT_FLAG_NAVIGATE = "+navigate"
EVENT_FLAG_TOUCH = "+touch"

POLICY_TASK = "task"
POLICY_MEMORY_GUIDED = "memory_guided"  # implemented in input_policy2
FINISHED = "task_completed"
MAX_SCROLL_NUM = 7
# USE_LMQL = False

print("MODIFIED input_policy.py LOADED")
class InputInterruptedException(Exception):
    pass

def safe_dict_get(view_dict, key, default=None):
    return_itm = view_dict[key] if (key in view_dict) else default
    if return_itm == None:
        return_itm = ''
    return return_itm

class InputPolicy(object):
    """
    This class is responsible for generating events to stimulate more app behaviour
    It should call AppEventManager.send_event method continuously
    """

    def __init__(self, device:Device, app:App, output_dir):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.device = device
        self.app = app
        self.action_count = 0
        self.output_dir = output_dir

    def start(self, input_manager):
        """
        start producing events
        :param input_manager: instance of InputManager
        """
        max_num = 12

        self.action_count = 0
        while input_manager.enabled and self.action_count < max_num:
            try:
                subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/screenshot.png"], check=True)
                subprocess.run(["adb", "pull", "/sdcard/screenshot.png", self.output_dir + f"/{self.action_count}.png"], check=True)
                if self.action_count == 0:
                    event = KillAppEvent(app=self.app)
                else:
                    event = self.generate_event(input_manager)
                    if event == None:
                        continue
                if event == FINISHED:
                    break
                input_manager.add_event(event)
            except KeyboardInterrupt:
                break
            except InputInterruptedException as e:
                self.logger.warning("stop sending events: %s" % e)
                break
            except Exception as e:
                self.logger.warning("exception during sending events: %s" % e)
                import traceback
                traceback.print_exc()
                continue
            self.action_count += 1


    @abstractmethod
    def generate_event(self, input_manager):
        """
        generate an event
        @return:
        """
        pass

class UtgBasedInputPolicy(InputPolicy):
    """
    state-based input policy
    """

    def __init__(self, device, app, output_dir):
        super(UtgBasedInputPolicy, self).__init__(device, app, output_dir)
        self.last_event = None
        self.last_state = None
        self.current_state = None

    def generate_event(self, input_manager):
        """
        generate an event
        @return:
        """

        # Get current device state
        self.current_state = self.device.get_current_state()
        if self.current_state is None:
            import time
            time.sleep(5)
            return KeyEvent(name="BACK")

        event = None

        if event is None:
            old_state, event = self.generate_event_based_on_utg()
            import time
            time.sleep(3)

        self.last_state = self.current_state if old_state is None else old_state
        self.last_event = event
        return event

    @abstractmethod
    def generate_event_based_on_utg(self, input_manager):
        """
        generate an event based on UTG
        :return: InputEvent
        """
        pass

class TaskPolicy(UtgBasedInputPolicy):

    def __init__(self, device, app, output_dir, task, use_memory=False):
        super(TaskPolicy, self).__init__(device, app, output_dir)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.task = task

        self.__num_restarts = 0
        self.__num_steps_outside = 0
        self.__event_trace = ""
        self.__missed_states = set()
        self.__action_history = []
        self.__thought_history = []
        self.use_memory = use_memory

        self.completed_steps = []

        #ADDED FOR RR CALCULATION
        self.total_baseline = 0
        self.total_core = 0

        #RR calc
        self.total_baseline_tokens = 0
        self.total_core_tokens = 0

        self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        


    def generate_event_based_on_utg(self):
        """
        generate an event based on current UTG
        @return: InputEvent
        """
        current_state = self.current_state
        self.logger.info("Current state: %s" % current_state.state_str)

        if current_state.get_app_activity_depth(self.app) < 0:
            # If the app is not in the activity stack
            start_app_intent = self.app.get_start_intent()

            if self.__event_trace.endswith(EVENT_FLAG_START_APP + EVENT_FLAG_STOP_APP) \
                    or self.__event_trace.endswith(EVENT_FLAG_START_APP):
                self.__num_restarts += 1
                self.logger.info("The app had been restarted %d times.", self.__num_restarts)
            else:
                self.__num_restarts = 0

            # pass (START) through
            if not self.__event_trace.endswith(EVENT_FLAG_START_APP):
                self.__event_trace += EVENT_FLAG_START_APP
                self.logger.info("Trying to start the app...")
                self.__action_history = [f'- launchApp {self.app.app_name}']
                self.__thought_history = [f'launch the app {self.app.app_name} to finish the task {self.task}']
                return None, IntentEvent(intent=start_app_intent)

        elif current_state.get_app_activity_depth(self.app) > 0:
            # If the app is in activity stack but is not in foreground
            self.__num_steps_outside += 1

            if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE:
                # If the app has not been in foreground for too long, try to go back
                if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE_KILL:
                    stop_app_intent = self.app.get_stop_intent()
                    go_back_event = IntentEvent(stop_app_intent)
                else:
                    go_back_event = KeyEvent(name="BACK")
                self.__event_trace += EVENT_FLAG_NAVIGATE
                self.logger.info("Going back to the app...")
                self.__action_history.append('- go back')
                self.__thought_history.append('the app has not been in foreground for too long, try to go back')
                return None, go_back_event
        else:
            # If the app is in foreground
            self.__num_steps_outside = 0

        
        action, candidate_actions, target_view, thought = self._get_action_from_views_actions(
            current_state=current_state, action_history=self.__action_history, thought_history=self.__thought_history, state_strs=current_state.state_str)
        
        if action == FINISHED:
            print("Total Baseline Tokens:", self.total_baseline_tokens)
            print("Total CORE Tokens:", self.total_core_tokens)

            if self.total_baseline_tokens > 0:
                reduction = (
                        (self.total_baseline_tokens - self.total_core_tokens)
                        / self.total_baseline_tokens
                        * 100
                )
                print("Token Reduction Rate:", reduction, "%")
            else:
                print("No baseline token data recorded.")
            print("=================================")
            return None, FINISHED

        if action is None:
            return None, None
        if action is not None:
            self.__action_history.append(current_state.get_action_descv2(action, target_view))
            self.__thought_history.append(thought)
            return None, action

        stop_app_intent = self.app.get_stop_intent()
        self.logger.info("Cannot find an exploration target. Trying to restart app...")
        self.__action_history.append('- stop the app')
        self.__thought_history.append("couldn't find a exploration target, stop the app")
        self.__event_trace += EVENT_FLAG_STOP_APP
        return None, IntentEvent(intent=stop_app_intent)

    
    def _extract_input_text(self, string, start='Text: ', end=' Thought'):
        start_index = string.find(start) + len(start)   # Find the location of 'start'
        if start_index == -1:
            start_index = 0
        end_index = string.find(end)                   # Find the location of 'end'
        substring = string[start_index:end_index] if end_index != -1 else string[start_index:]
        return substring
    
    def _extract_input_textv2(self, string):
        if string[:11] == 'InputText: ':
            return string[11:]
        else:
            return string
    
    def _get_text_view_description(self, view):
        content_description = safe_dict_get(view, 'content_description', default='')
        view_text = safe_dict_get(view, 'text', default='')

        view_desc = f"<input class='&'>#</input>"
        if view_text:
            view_desc = view_desc.replace('#', view_text)
        else:
            view_desc = view_desc.replace('#', '')
        if content_description:
            view_desc = view_desc.replace('&', content_description)
        else:
            view_desc = view_desc.replace(" class='&'", "")
        return view_desc

    def _get_action_from_views_actions(self, current_state, action_history, thought_history, state_strs):

        # path to the current screenshot
        image_path = os.path.join(self.output_dir, f"{self.action_count}.png")

        if current_state:
            # Prepare XML data for Baseline RR calculation and Locator mapping
            minified, pretty = current_state.process_xml()
            all_list, important_map, leaf_ancestors_map, results, readable_results, candidate_actions = current_state.extract_info_from_xml(
                pretty)
            important_list = [value for key, value in important_map.items()]

            # --- PHASE 1: CO-PLANNING (Local LLaVA) ---
            # Ask LLaVA to look at the screenshot and propose sub-tasks
            subtask_prompt = self.prompt_local_LLM_generate_subtasks(self.task, action_history)
            several_options = tools.query_local_LLM(subtask_prompt, image_path)

            if not several_options:
                print("WARNING: LLaVA failed. Using fallback proposal.")
                several_options = "Identify next logical click based on visual UI."

            print(f"LLaVA Proposals: {several_options}")

            # --- PHASE 2: CO-DECISION-MAKING (Cloud GPT-4o) ---
            decision_prompt = prompt_LLM_current_task(self.task, action_history, several_options)

            # --- RR (Token Reduction) Calculation ---
            baseline_prompt_str = prompt_LLM_current_task(self.task, action_history, "\n".join(important_list))
            self.total_baseline_tokens += len(self.tokenizer.encode(baseline_prompt_str))
            self.total_baseline += len(important_list)

            # CORE:LLaVA's summary
            self.total_core_tokens += len(self.tokenizer.encode(decision_prompt))
            options_list = several_options.strip().split("\n") if several_options else []
            self.total_core += len(options_list)


            state_prompt = "\n".join(important_list)
            state_str = current_state.state_str
        else:
            # Fallback for empty states
            views = []
            views_with_id = []
            for id in range(len(views)):
                views_with_id.append(tools.insert_id_into_view(views[id], id))
            state_prompt = '\n'.join(views_with_id)
            state_str = tools.hash_string(state_prompt)
            return None, None, None, None  # Safety exit if no state

        current_task_raw = query_openai_LLM(decision_prompt)

        if current_task_raw is None:
            return FINISHED, None, None, None

        current_task = current_task_raw.replace("\n", "")
        print(f"GPT-4o Selected Task: {current_task}")

        if "finished" in current_task.lower():
            return FINISHED, None, None, None

        # --- MAPPING: Use Locator to find the XML element for the selected task ---
        locator = LocatorMethods(task=self.task, tree=None, results=results,
                                 important_map=important_map, output_dir=self.output_dir, image_path=image_path)

        i, _ = locator.extract_chunks(results, important_map)
        _, response = locator.chunks_method(readable_results, current_task, action_history)

        # If locator fails, scroll event
        if _ == -1:
            print("Locator failed to find element. Attempting scroll...")
            self.device.send_event(ScrollEvent())
            time.sleep(3)
            return None, None, None, "element_not_found_scrolling"

        # --- EXTRACTION: Convert LLM response to DroidBot Action ---
        if response is None:
            return FINISHED, None, None, None

        response_json = tools.extract_json(response)
        response_clean = tools.clean_json(response_json)
        idx, action_type, input_text = tools.extract_action(response_clean)

        idx = int(idx)
        if idx == -1:
            return FINISHED, None, None, None

        selected_action = candidate_actions[idx]

        # Handle Long Tap
        if isinstance(selected_action, TouchEvent):
            if action_type.replace(" ", "").lower() == "longtap":
                selected_action.duration = 2000

        # Retrieve visual description and thought for logging
        selected_view_description = tools.get_item_properties_from_id(ui_state_desc=state_prompt, view_id=idx)
        thought = tools.get_thought(response_clean)

        # Handle Text Input
        if isinstance(selected_action, SetTextEvent):
            if input_text and input_text != "N/A":
                selected_action.text = input_text.replace('"', '')
                if len(selected_action.text) > 50:
                    selected_action.text = ''
            else:
                selected_action.text = ''

        return selected_action, candidate_actions, selected_view_description, thought

    def prompt_local_LLM_generate_subtasks(self, task, action_history):
        history_str = "\n".join(action_history)
        return f"""
        You are a mobile UI planner. 
        User Goal: {task}
        Action History: {history_str}

        Task: Based on the attached screenshot, suggest the next 3 immediate steps to reach the goal.
        Output only the instructions, one per line. No other text.
        """