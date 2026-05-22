def prompt_for_score_chunks(task, UI_state):       
    UI_explanation = "You are a smartphone assistant to help users complete tasks by interacting with mobile apps. The current UI state is shown below. It is separated into several sections, and each section is composed by several UI elements."   
    full_state_prompt = 'Current UI state: \n' + UI_state
    requirement = f'''Given a current task, and the sections of part of current UI state, your job is to score each section to judge the probability that it can solve or progress current task: {task}. In most time, elements grouped in one section are relevant. Sometimes, maybe only one UI element is most useful and other elements in the same section are irrelevant, this section should still be assigned high score.''' + ''' Output json like {"0": "<score of section 0>", "1": "<score of section 1>", ...}, the score should be a float between 0 and 1 and sum up to 1. Also output your explanation briefly.'''
    return UI_explanation + "\n" + full_state_prompt + "\n" + requirement

def prompt_local_LLM_current_task(task, previous_ui_actions, current_ui):
    intro = '''You are a Planner, skilled at analyzing mobile UI states and task progress. Given a task description, previous UI actions, and part of current UI state, your job is to provide the most appropriate current step instruction.'''       
    instruction = f''' You receive the task description from the user: {task}. The previously completed steps for the task include: {previous_ui_actions}. This is one section of current UI state: {current_ui}. You must give the current step instruction based on the given section of current UI state(others are masked for privacy), even if the section seems irrelevant. Your response should be a single, precise current step instruction, it can't involve precise UI element information but should involve a logic task explanation, focusing only on what needs to be done immediately in the current UI state to progress the task.'''
    prompt = intro + instruction 
    return prompt

def prompt_LLM_current_task(task, previous_ui_actions, several_options):
    intro = '''You are a Planner, skilled at analyzing mobile UI states and task progress. Based on a whole task description and previous UI actions, you need to give the current step instruction focusing only on what needs to be done immediately. A weaker local LLM has generated several current step instructions based on different sections of current UI state. Due to its weaker ability and incomplete information, some of them may be wrong. You can't see any private UI state, but the weaker local LLM can. You can analyze based on its generated current step instructions. '''       
    instruction = f''' You receive the task description from the user: {task}. The previously completed steps for the task include: {previous_ui_actions}. The weaker local LLM generated several current step instructions based on different part of current UI: {several_options}. You can choose a most appropriate one from them, if you think all of them are wrong, you can correct them and give a new correct current step instruction. Never output other explanations.''' + "If you think the task has been finished, output FINISHED only."
    prompt = intro + instruction
    return prompt

def prompt_for_making_decision(current_task, UI_list, task, previous_ui_actions):
    introduction = '''You are a smartphone assistant to help users complete tasks by interacting with mobile apps. Given the whole task, the previous UI actions, the content of current UI state(may be incomplete), you should first decide the current task. Then you need to decide which UI element in current UI state should be interacted.'''
    task_prompt = 'Whole Task: ' + task
    history_prompt = 'Previous UI actions: ' + '\n'.join(previous_ui_actions)
    full_state_prompt = 'Current UI state: \n' + '\n'.join(UI_list)
    request_prompt = '''\nYou should first give a current task. It should be a single, precise current step instruction, it can't involve precise UI element information but should involve a logic task explanation, focusing only on what needs to be done immediately in the current UI state to progress the task. But note that the current UI state may not be complete for privacy protection. First, you need to judge whether the information in the current UI state can help the current task. If not, set the index to '-1'. Your response should always be in the following JSON format: 
{
"current_task": "<a brief description of what to do at current step>",
"index": "<an integer, representing the index number of the UI element to interact with for current task or -1 (if none of the elements in the current UI state is relevant to the task)>",
"action": "tap, longtap or input",
"input_text": "<input text (if action is 'input') or 'N/A' (if action is 'tap' or 'longtap')>"
}'''
    prompt = introduction + '\n' + task_prompt + '\n' + history_prompt + '\n' + full_state_prompt + '\n' + request_prompt
    return prompt


def prompt_for_making_decision_complete(current_task, UI_list, task, previous_ui_actions):
    introduction = '''You are a smartphone assistant to help users complete tasks by interacting with mobile apps. Given the whole task, the previous UI actions, the content of current UI state, you should first decide the current task. Then you need to decide which UI element in current UI state should be interacted.'''
    task_prompt = 'Whole Task: ' + task
    history_prompt = 'Previous UI actions: ' + '\n'.join(previous_ui_actions)
    full_state_prompt = 'Current UI state: \n' + '\n'.join(UI_list)
    request_prompt = '''\nYou should first give a current task. It should be a single, precise current step instruction, it can't involve precise UI element information but should involve a logic task explanation, focusing only on what needs to be done immediately in the current UI state to progress the task. Your response should always be in the following JSON format: 
{
"current_task": "<a brief description of what to do at current step>",
"index": "<an integer, representing the index number of the UI element to interact with for current task or -1 (if none of the elements in the current UI state is relevant to the task and need to scroll to observe more elements)>", 
"action": "tap, longtap or input",
"input_text": "<input text (if action is 'input') or 'N/A' (if action is 'tap' or 'longtap')>"
}'''
    prompt = introduction + '\n' + task_prompt + '\n' + history_prompt + '\n' + full_state_prompt + '\n' + request_prompt
    return prompt