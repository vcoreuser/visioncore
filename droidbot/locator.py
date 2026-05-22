import json
import re
from .prompt import *
from tools import *
import tools
import time
import random

class LocatorMethods:
    def __init__(self, task, tree, results, important_map, output_dir, image_path=None):
        self.task = task
        self.tree = tree
        self.results = results
        self.important_map = important_map
        self.output_dir = output_dir
        self.image_path = image_path

    @staticmethod
    def extract_chunks(results, important_map):

        def extract_chunks_dict(results):
            for i, result in enumerate(results):
                if isinstance(result, dict) and 3 <= len(result):
                    return i, result
            if results:
                return len(results) - 1, results[-1]
            else:
                return -1, None

        i, the_dict = extract_chunks_dict(results)
        if i == -1:
            tmp = [value for key, value in important_map.items()]
            return -1, tmp
        answer = []
        for key, indices in the_dict.items():
            extracted_items = [important_map[index] for index in indices]  
            answer.append("\n".join(extracted_items))
        return i, answer

    def chunks_method(self, readable_results, current_task, previous_ui_actions):
        i, answer = self.extract_chunks(self.results, self.important_map)
        print(i, answer)
        if i == -1:
            prompt = prompt_for_making_decision_complete(current_task, answer, self.task, previous_ui_actions)
            print(prompt)
            
            response = query_openai_LLM(prompt)
            print(response)

            json_response = json.loads(tools.extract_json(response))
            index = int(json_response.get("index", ""))
            current_task = json_response.get("current_task", current_task)
            print(current_task)
            return index, response
        prompt = prompt_for_score_chunks(current_task, readable_results[i])
        print(prompt)
        response = query_local_LLM(prompt, image_path=self.image_path)
        print(response)

        json_response = json.loads(re.sub(r',\s*}', '}', tools.extract_json(response)))
        int_key_scores_dict = {int(key): float(value) for key, value in json_response.items()}

        sorted_sections = sorted(int_key_scores_dict.items(), key=lambda item: item[1], reverse=True)
        sorted_section_ids = [section_id for section_id, score in sorted_sections]
        print(sorted_section_ids)

        tmp1 = [value for key, value in self.results[i].items()]
        tmp1_keys = []
        for i, id in enumerate(sorted_section_ids):
            # Safety check: skip if LLaVA suggests a section ID that wasn't created
            if id >= len(tmp1):
                print(
                    f"DEBUG: Skipping LLaVA suggested section {id} because it doesn't exist in tmp1 (len: {len(tmp1)})")
                continue
            tmp1_keys += tmp1[id]
            tmp1_keys.sort()
            tmp = [value for key, value in self.important_map.items() if key in tmp1_keys]
            print(tmp)

            if i == len(sorted_section_ids) - 1:
                prompt = prompt_for_making_decision_complete(current_task, tmp, self.task, previous_ui_actions)
            else:
                prompt = prompt_for_making_decision(current_task, tmp, self.task, previous_ui_actions)
            print(prompt)
            
            response = query_openai_LLM(prompt)
            print(response)

            json_response = json.loads(tools.extract_json(response))
            index = int(json_response.get("index", ""))
            current_task = json_response.get("current_task", current_task)
            print(current_task)

            if index != -1:
                return index, response
        
        return -1, None

    