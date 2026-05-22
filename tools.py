import os
import re
import hashlib
import ast
from openai import OpenAI
import requests
import os
import base64
import json
ACTION_MISSED = None

def get_id_from_view_desc(view_desc):
    '''
    given a view(UI element), get its ID
    '''
    match = re.findall(r'index="(\d+)"', view_desc)
    if match:
        return int(match[0])
    else:
        print("No id found in view description.")
        print("the view description is: ", view_desc)
        return None 
    
def insert_id_into_view(view, id):
    if view[0] == ' ':
        view = view[1:]
    if view[:2] == '<p':
        return view[:2] + f' id={id}' + view[2:]
    if view[:7] == '<button':
        return view[:7] + f' id={id}' + view[7:]
    if view[:6] == '<input':
        return view[:6] + f' id={id}' + view[6:]
    if view[:9] == '<checkbox':
        return view[:9] + f' id={id}' + view[9:]
    if view[:5] == '<span':
        return view[:5] + f' id={id}' + view[5:]
    import pdb;pdb.set_trace()

def get_view_without_id(view_desc):
    '''
    remove the id from the view
    '''
    id = re.findall(r'id=(\d+)', view_desc)[0]
    id_string = ' id=' + id
    return re.sub(id_string, '', view_desc)


def delete_old_views_from_new_state(old_state, new_state, without_id=True):
    '''
    remove the UI element in new_state if it also exists in the old_state
    '''
    old_state_list = old_state.split('>\n')
    new_state_list = new_state.split('>\n')
    old_state_list_without_id = []
    for view in old_state_list:
        view_without_id = get_view_without_id(view)
        if view[-1] != '>':
            view = view + '>'
        if view_without_id[-1] != '>':
            view_without_id = view_without_id + '>'
        old_state_list_without_id.append(view_without_id)
    customized_new_state_list = []
    for view in new_state_list:
        view_without_id = get_view_without_id(view)
        if view[-1] != '>':
            view = view + '>'
        if view_without_id[-1] != '>':
            view_without_id = view_without_id + '>'
        if view_without_id not in old_state_list_without_id: #or 'go back' in view or 'scroll' in view:
            if without_id:
                customized_new_state_list.append(view_without_id)
            else:
                customized_new_state_list.append(view)
    return customized_new_state_list


def get_item_properties_from_id(ui_state_desc, view_id):
    '''
    given the element id, get the UI element property from the state prompt
    '''
    # ui_state_desc = self.states[state_str]['raw_prompt']
    ui_state_list = ui_state_desc.split('>\n')
    for view_desc in ui_state_list:
        if view_desc[0] == ' ':
            view_desc = view_desc[1:]
        if view_desc[-1] != '>':
            view_desc += '>'
        id = get_id_from_view_desc(view_desc)
        if id == view_id:
            # print("view_desc:" + view_desc)
            return view_desc.lstrip()
            # return get_view_without_id(view_desc)
    return ACTION_MISSED

def get_thought(answer):
    start_index = answer.find('Thought:') + len('Thought:')   # Find the location of 'start'
    if start_index == -1:
        start_index = answer.find('thought:') + len('thought:')
    if start_index == -1:
        start_index = answer.find('Thought') + len('Thought')
    if start_index == -1:
        start_index = answer.find('thought') + len('thought')
    if start_index == -1:
        start_index = 0
    end_index = answer.find('}')                   # Find the location of 'end'
    substring = answer[start_index:end_index] if end_index != -1 else answer[start_index:]
    return substring

def process_gpt_answer(answer):
    answer = answer.replace('\n', ' ')
    return answer

def extract_gpt_answer(answer):
    split_answer = answer.split('4.')
    if len(split_answer) > 1:
        last_sentence = split_answer[1]
        pattern = r'id=(\d+)'
        match = re.search(pattern, last_sentence)
        try:
            id = int(match.group(0)[3:])
        except:
            id = re.search(r'\d+', last_sentence)
        return id
    else:
        return re.search(r'\d+', answer)

def make_prompt(task, ui_desc, history):
    introduction_prompt = "You are a smartphone assistant to help users complete tasks by interacting with mobile apps.\nGiven a task, the previous UI actions, and the content of current UI state, your job is to decide whether the task is already finished by the previous actions, and if not, decide which UI element in current UI state should be interacted."
    task_prompt = "Task: "
    history_prompt = "Previous UI actions: "
    interface_prompt = "Current UI state: "
    question_prompt = "Your answer should always use the following format:\n1. Completing this task on a smartphone usually involves these steps: <?>.\n2. Analyse the relations between the task and the previous UI actions and current UI state: <?>.\n3. Based on the analyses, is the task already finished? <Y/N>. The next step should be <?/None>.\n4. Can the task be proceeded with the current UI state? <Y/N>. Fill in the blank about next interaction: - id=<id/-1 for finished> - action=<tap/input> - input text=<text or N/A>"
    return introduction_prompt+'\n'+task_prompt + task + '\n' + history_prompt + '\n' + history + '\n' + interface_prompt +'\n'+ ui_desc + '\n' + question_prompt

def visualize_network(G):
    from pyvis.network import Network
    nt = Network('1500px', notebook=True, directed=True)
    nt.from_nx(G)
    nt.toggle_physics(True)
    nt.show('visualize/nx.html')


def extract_actionv0(answer):
    llm_id = 'N/A'
    llm_action = 'tap'
    llm_input = "N/A"
    whether_finished_answer = re.findall(
        "3\.(.*)4\.", answer, flags=re.S
    )[0]
    for e in ["Yes.", "Y.", "y.", "yes.", "is already finished"]:
        if e in whether_finished_answer:
            llm_id = -1
            llm_action = "N/A"
            llm_input = "N/A"
            break
    finished_check = re.findall("4\.(.*)", answer, flags=re.S)[0]
    for e in [
        "No further interaction is required",
        "cannot be determined based on",
        "no further action is needed",
    ]:
        if e in finished_check:
            llm_id = -1
            llm_action = "N/A"
            llm_input = "N/A"
    if llm_id != -1:
        try:
            llm_id, llm_action, llm_input = re.findall(
                "- id=(N/A|-?\d+)(?:.|\\n)*-\s?action=(.+?)(?:\\n|\s)(?:.|\\n)*-\s*input text=\"?'?(N/A|\w+)\"?'?",
                answer,
            )[0]
            if llm_id == "N/A":
                llm_id = -1
            else:
                llm_id = int(llm_id)
            if "tapon" in llm_action.lower():
                llm_action = "tap"
            elif "none" in llm_action.lower():
                llm_action = "N/A"
            elif "click" in llm_action.lower():
                llm_action = "tap"
            assert llm_action in ["tap", "input", "N/A"]
        except:
            try:
                llm_id, llm_action = re.findall(
                    "-\s?id=(\d+).*-\s?action=(\w+)", answer, flags=re.S
                )[0]
                llm_id = int(llm_id)
                if (
                    "tapon" in llm_action.lower()
                    or "check" in llm_action.lower()
                    or "uncheck" in llm_action.lower()
                ):
                    llm_action = "tap"
                elif "none" in llm_action.lower():
                    llm_action = "N/A"
                assert llm_action in ["tap", "input", "N/A"]
            except:
                llm_id, llm_action, llm_input = eval(
                    input(
                        answer + "\nPlease input id, action, and text: "
                    )
                )
                llm_id = int(llm_id)
                llm_action = ["tap", "input", "N/A"][
                    int(llm_action)
                ]
                try:
                    if int(llm_input) == -1:
                        llm_input = "N/A"
                except:
                    pass
    return llm_id, llm_action, llm_input

def extract_action(v):
    llm_input = None
    llm_action = "N/A"
    try:
        if isinstance(v, str):
            v = ast.literal_eval(v)
    except:
        print('format error: v')
        llm_id = -1
        llm_action = "N/A"
        llm_input = "N/A"
    try:
        whether_finished_answer = False
        if whether_finished_answer:
            llm_id = -1
            llm_action = "N/A"
            llm_input = "N/A"
        else:
            llm_id = 'N/A'

    except:
        pass
    if llm_id != -1:
        step_desc = v
        if 'action' in step_desc:
            llm_action = step_desc['action']
        if 'input_text' in step_desc:
            llm_input = step_desc['input_text']
        if 'id' in step_desc:
            llm_id = step_desc['id']
        if 'ID' in step_desc:
            llm_id = step_desc['ID']
        if 'index' in step_desc:
            llm_id = step_desc['index']
        if 'Action' in step_desc:
            llm_action = step_desc['Action']
        if 'Input_text' in step_desc:
            llm_input = step_desc['Input_text']
        if llm_id == "N/A":
            llm_id = -1
        else:
            llm_id = int(llm_id)

        if "longtap" in llm_action.lower() or "long" in llm_action.lower():
            llm_action = "longtap"
        elif "tap" in llm_action.lower() or "check" in llm_action.lower() or "choose" in llm_action.lower():
            llm_action = "tap"
        elif "none" in llm_action.lower():
            llm_action = "N/A"
        elif "click" in llm_action.lower():
            llm_action = "tap"
        elif "input" in llm_action.lower():
            llm_action = "input"
        assert llm_action in ["longtap", "tap", "input", "N/A"]

    return llm_id, llm_action, llm_input

def insert_onclick_into_prompt(state_prompt, insert_ele, target_ele_desc):

    def insert_onclick(statement, description):
        index = statement.find('>')
        inserted_statement = statement[:index] + f" onclick='{description}'" + statement[index:]
        return inserted_statement

    onclick_desc = 'go to complete the ' + target_ele_desc
    element_statements = state_prompt.split('>\n')
    elements_without_id = []
    for ele_statement in element_statements:
        ele_statement_without_id = get_view_without_id(ele_statement)
        if ele_statement_without_id[-1] != '>':
            ele_statement_without_id += '>'
        if insert_ele == ele_statement_without_id:
            ele_statement_without_id = insert_onclick(ele_statement_without_id, onclick_desc)

        elements_without_id.append(ele_statement_without_id)

    elements = []
    for id in range(len(elements_without_id)):
        elements.append(insert_id_into_view(elements_without_id[id], id))
    return '\n'.join(elements)

def hash_string(string):
    byte_string = string.encode()
    hash_obj = hashlib.sha256(byte_string)
    hashed_string = hash_obj.hexdigest()
    return hashed_string

def extract_json(text):
    json_match = re.search(r'\{.*?\}', text, re.DOTALL) 
    if json_match:
        return json_match.group()
    return None


def clean_json(json_str:str):
    pattern = re.compile(r'(?<!^)\{(.*?)(?<!\\)\}(?!\})', re.DOTALL)
    def remove_braces(match):
        return re.sub(r'\{|\}', '', match.group(0))
    json_str = json_str.replace('\\', '')
    json_str = re.sub(pattern, remove_braces, json_str)
    json_str = json_str.replace('"', '')
    json_str = json_str.replace('\'', '')
    json_str = re.sub(r'(?<=\{|,)\s*(\w+\s*\w+)\s*:', r'"\1":', json_str)
    json_str = json_str.replace(',"', '", "')
    json_str = json_str.replace('": ', '": "')
    json_str = json_str.replace('\n', '')
    json_str = json_str.replace('}', '"}')

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print("Json decoding error:", e)
        return None
    def clean_item(item):
        if isinstance(item, dict):
            return {str(k): clean_item(v) for k, v in item.items()}
        elif isinstance(item, list):
            return ", ".join(clean_item(i) for i in item)
        elif isinstance(item, str):
            return item.replace('"', '')
        else:
            return str(item)
    cleaned_data = clean_item(data)

    return json.dumps(cleaned_data, indent = 4, ensure_ascii=False)

def extract_content(raw_str):
    str = raw_str.split("\n")
    first = None
    if len(str) > 1:
        first = str[1]
        return first, "\n".join(str[1:])
    else:
        return first, raw_str


def query_openai_LLM(prompt: str) -> str:
    import os
    messages = [{"role": "user", "content": prompt}]
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")

    LLM_client = OpenAI(api_key=api_key) # your-api-key

    completion = LLM_client.chat.completions.create(
        messages = messages,
        model="gpt-4o-2024-11-20"
    )
    response = completion.choices[0].message.content
    return response

# Updated tools.py logic
def query_local_LLM(prompt: str, image_path: str = None) -> str:
    import requests
    import base64

    payload = {
        "model": "llava",
        "prompt": prompt,
        "stream": False
    }

    # Only add the image if it is actually provided (e.g., from the Locator)
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as image_file:
            img_str = base64.b64encode(image_file.read()).decode('utf-8')
        payload["images"] = [img_str]

    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=1000)
        return response.json().get("response", "")
    except Exception as e:
        return f"Error: {str(e)}"

def log_information(intro, prompt, response, file_path="log.txt"):
    with open(file_path, "a") as log_file:
        log_file.write(intro + "\n")
        log_file.write(f"Prompt:\n{prompt}\n")
        log_file.write(f"Response:\n{response}\n")

if __name__ == '__main__':
    print(query_local_LLM("who are you"))

