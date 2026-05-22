import copy
import math
import os
import pdb

import tools
from .utils import md5
from .input_event import TouchEvent, LongTouchEvent, ScrollEvent, SetTextEvent, KeyEvent, UIEvent
import hashlib
import numpy as np

class DeviceState(object):
    """
    the state of the current device
    """

    def __init__(self, device, views, foreground_activity, activity_stack, background_services,
                 tag=None, screenshot_path=None, xml_tree=None):
        self.device = device
        self.foreground_activity = foreground_activity
        self.activity_stack = activity_stack if isinstance(activity_stack, list) else []
        self.background_services = background_services
        if tag is None:
            from datetime import datetime
            tag = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self.tag = tag
        self.screenshot_path = screenshot_path
        self.views = self.__parse_views(views)
        
        self.bk_views = copy.deepcopy(self.views)
        self.__generate_view_strs()
        self.state_str = self.__get_hashed_state_str()
        self.structure_str = self.__get_content_free_state_str()
        self.search_content = self.__get_search_content()
        self.possible_events = None
        self.width = device.get_width(refresh=True)
        self.height = device.get_height(refresh=False)
        self._save_important_view_ids()
        
        self.xml_tree = xml_tree

    @property
    def activity_short_name(self):
        return self.foreground_activity.split('.')[-1]
    
        
    def _save_important_view_ids(self):
        _, _, _, important_view_ids = self.get_described_actions(remove_time_and_ip=False)
        ids_path = self.device.output_dir +'/states_view_ids'
        if not os.path.exists(ids_path):
            os.mkdir(ids_path)
        important_view_id_path = self.device.output_dir +'/states_view_ids/'+ self.state_str + '.txt'
        f = open(important_view_id_path, 'w')
        f.write(str(important_view_ids))
        f.close()

    def __get_hashed_state_str(self):
        state, _, _, _ = self.get_described_actions(remove_time_and_ip=False)
        hashed_string = tools.hash_string(state)
        return hashed_string

    def to_dict(self):
        state = {'tag': self.tag,
                 'state_str': self.state_str,
                 'state_str_content_free': self.structure_str,
                 'foreground_activity': self.foreground_activity,
                 'activity_stack': self.activity_stack,
                 'background_services': self.background_services,
                 'width': self.width,
                 'height': self.height,
                 'views': self.views}
        return state

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), indent=2)

    def __parse_views(self, raw_views):
        views = []
        if not raw_views or len(raw_views) == 0:
            return views

        for view_dict in raw_views:
            views.append(view_dict)
        return views

    def __assemble_view_tree(self, root_view, views):
        if not len(self.view_tree): # bootstrap
            self.view_tree = copy.deepcopy(views[0])
            self.__assemble_view_tree(self.view_tree, views)
        else:
            children = list(enumerate(root_view["children"]))
            if not len(children):
                return
            for i, j in children:
                root_view["children"][i] = copy.deepcopy(self.views[j])
                self.__assemble_view_tree(root_view["children"][i], views)

    def __generate_view_strs(self):
        for view_dict in self.views:
            self.__get_view_str(view_dict)
            # self.__get_view_structure(view_dict)

    @staticmethod
    def __calculate_depth(views):
        root_view = None
        for view in views:
            if DeviceState.__safe_dict_get(view, 'parent') == -1:
                root_view = view
                break
        DeviceState.__assign_depth(views, root_view, 0)

    @staticmethod
    def __assign_depth(views, view_dict, depth):
        view_dict['depth'] = depth
        for view_id in DeviceState.__safe_dict_get(view_dict, 'children', []):
            DeviceState.__assign_depth(views, views[view_id], depth + 1)

    def __get_state_str(self):
        state_str_raw = self.__get_state_str_raw()
        return md5(state_str_raw)

    def __get_state_str_raw(self):
        view_signatures = set()
        for view in self.views:
            view_signature = DeviceState.__get_view_signature(view)
            if view_signature:
                view_signatures.add(view_signature)
        return "%s{%s}" % (self.foreground_activity, ",".join(sorted(view_signatures)))

    def __get_content_free_state_str(self):     
        view_signatures = set()
        for view in self.views:
            view_signature = DeviceState.__get_content_free_view_signature(view)
            if view_signature:
                view_signatures.add(view_signature)
        state_str = "%s{%s}" % (self.foreground_activity, ",".join(sorted(view_signatures)))
        import hashlib
        return hashlib.md5(state_str.encode('utf-8')).hexdigest()

    def __get_search_content(self):
        """
        get a text for searching the state
        :return: str
        """
        words = [",".join(self.__get_property_from_all_views("resource_id")),
                 ",".join(self.__get_property_from_all_views("text"))]
        return "\n".join(words)

    def __get_property_from_all_views(self, property_name):
        """
        get the values of a property from all views
        :return: a list of property values
        """
        property_values = set()
        for view in self.views:
            property_value = DeviceState.__safe_dict_get(view, property_name, None)
            if property_value:
                property_values.add(property_value)
        return property_values

    def is_different_from(self, another_state):
        """
        compare this state with another
        @param another_state: DeviceState
        @return: boolean, true if this state is different from other_state
        """
        return self.state_str != another_state.state_str

    @staticmethod
    def __get_view_signature(view_dict):
        """
        get the signature of the given view
        @param view_dict: dict, an element of list DeviceState.views
        @return:
        """
        if 'signature' in view_dict:
            return view_dict['signature']

        view_text = DeviceState.__safe_dict_get(view_dict, 'text', "None")
        if view_text is None or len(view_text) > 50:
            view_text = "None"

        signature = "[class]%s[resource_id]%s[text]%s[%s,%s,%s]" % \
                    (DeviceState.__safe_dict_get(view_dict, 'class', "None"),
                     DeviceState.__safe_dict_get(view_dict, 'resource_id', "None"),
                     view_text,
                     DeviceState.__key_if_true(view_dict, 'enabled'),
                     DeviceState.__key_if_true(view_dict, 'checked'),
                     DeviceState.__key_if_true(view_dict, 'selected'))
        view_dict['signature'] = signature
        return signature

    @staticmethod
    def __get_content_free_view_signature(view_dict):
        """
        get the content-free signature of the given view
        @param view_dict: dict, an element of list DeviceState.views
        @return:
        """
        if 'content_free_signature' in view_dict:
            return view_dict['content_free_signature']
        content_free_signature = "[class]%s[resource_id]%s" % \
                                 (DeviceState.__safe_dict_get(view_dict, 'class', "None"),
                                  DeviceState.__safe_dict_get(view_dict, 'resource_id', "None"))
        view_dict['content_free_signature'] = content_free_signature
        return content_free_signature

    def __get_view_str(self, view_dict):
        """
        get a string which can represent the given view
        @param view_dict: dict, an element of list DeviceState.views
        @return:
        """
        if 'view_str' in view_dict:
            return view_dict['view_str']
        view_signature = DeviceState.__get_view_signature(view_dict)
        parent_strs = []
        for parent_id in self.get_all_ancestors(view_dict):
            parent_strs.append(DeviceState.__get_view_signature(self.views[parent_id]))
        parent_strs.reverse()
        child_strs = []
        for child_id in self.get_all_children(view_dict):
            child_strs.append(DeviceState.__get_view_signature(self.views[child_id]))
        child_strs.sort()
        view_str = "Activity:%s\nSelf:%s\nParents:%s\nChildren:%s" % \
                   (self.foreground_activity, view_signature, "//".join(parent_strs), "||".join(child_strs))
        import hashlib
        view_str = hashlib.md5(view_str.encode('utf-8')).hexdigest()
        view_dict['view_str'] = view_str
        return view_str

    def __get_view_structure(self, view_dict):
        """
        get the structure of the given view
        :param view_dict: dict, an element of list DeviceState.views
        :return: dict, representing the view structure
        """
        if 'view_structure' in view_dict:
            return view_dict['view_structure']
        width = DeviceState.get_view_width(view_dict)
        height = DeviceState.get_view_height(view_dict)
        class_name = DeviceState.__safe_dict_get(view_dict, 'class', "None")
        children = {}

        root_x = view_dict['bounds'][0][0]
        root_y = view_dict['bounds'][0][1]

        child_view_ids = self.__safe_dict_get(view_dict, 'children')
        if child_view_ids:
            for child_view_id in child_view_ids:
                child_view = self.views[child_view_id]
                child_x = child_view['bounds'][0][0]
                child_y = child_view['bounds'][0][1]
                relative_x, relative_y = child_x - root_x, child_y - root_y
                children["(%d,%d)" % (relative_x, relative_y)] = self.__get_view_structure(child_view)

        view_structure = {
            "%s(%d*%d)" % (class_name, width, height): children
        }
        view_dict['view_structure'] = view_structure
        return view_structure

    @staticmethod
    def __key_if_true(view_dict, key):
        return key if (key in view_dict and view_dict[key]) else ""

    @staticmethod
    def __safe_dict_get(view_dict, key, default=None):
        return_itm = view_dict[key] if (key in view_dict) else default
        if return_itm == None:
            return_itm = ''
        return return_itm
    
    @staticmethod
    def get_view_center(view_dict):
        """
        return the center point in a view
        @param view_dict: dict, an element of DeviceState.views
        @return: a pair of int
        """
        bounds = view_dict['bounds']
        return bounds.x + bounds.width / 2, bounds.y + bounds.height / 2
        # return (bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2

    @staticmethod
    def get_view_width(view_dict):
        """
        return the width of a view
        @param view_dict: dict, an element of DeviceState.views
        @return: int
        """
        bounds = view_dict['bounds']
        return int(math.fabs(bounds[0][0] - bounds[1][0]))

    @staticmethod
    def get_view_height(view_dict):
        """
        return the height of a view
        @param view_dict: dict, an element of DeviceState.views
        @return: int
        """
        bounds = view_dict['bounds']
        return int(math.fabs(bounds[0][1] - bounds[1][1]))

    def get_all_ancestors(self, view_dict):
        """
        Get temp view ids of the given view's ancestors
        :param view_dict: dict, an element of DeviceState.views
        :return: list of int, each int is an ancestor node id
        """
        result = []
        parent_id = self.__safe_dict_get(view_dict, 'parent', -1)
        if 0 <= parent_id < len(self.views):
            result.append(parent_id)
            result += self.get_all_ancestors(self.views[parent_id])
        return result

    def get_all_children(self, view_dict):
        """
        Get temp view ids of the given view's children
        :param view_dict: dict, an element of DeviceState.views
        :return: set of int, each int is a child node id
        """
        children = self.__safe_dict_get(view_dict, 'children')
        if not children:
            return set()
        children = set(children)
        for child in children:
            children_of_child = self.get_all_children(self.views[child])
            children.union(children_of_child)
        return children

    def get_app_activity_depth(self, app):
        """
        Get the depth of the app's activity in the activity stack
        :param app: App
        :return: the depth of app's activity, -1 for not found
        """
        depth = 0
        for activity_str in self.activity_stack:
            if app.package_name in activity_str:
                return depth
            depth += 1
        return -1

    def _get_self_ancestors_property(self, view, key, default=None):
        all_views = [view] + [self.views[i] for i in self.get_all_ancestors(view)]
        for v in all_views:
            value = self.__safe_dict_get(v, key)
            if value:
                return value
        return default
        
    def _remove_view_ids(self, views):
        import re
        removed_views = []
        for view_desc in views:
            view_desc_without_id = tools.get_view_without_id(view_desc)
            removed_views.append(view_desc_without_id)
        return removed_views
    
    def _adjust_view_clickability(self):
        '''make the view unclickable if it has clickable successors'''
        for view_id in range(1, len(self.views)):
            if self.__safe_dict_get(self.views[view_id], 'clickable', default=False):
                successors = self._extract_all_children(view_id)
                # print('origin:', view_id, 'succs: ', successors)
                for successor in successors:
                    if successor != view_id and self.__safe_dict_get(self.views[successor], 'clickable', False):
                        # print(self.views[view_id], 'disabled, because of ', self.views[successor])
                        self.views[view_id]['clickable'] = False
                        # print('origin:', view_id, 'because of:', successor, 'disabled')
                        break
            if self.__safe_dict_get(self.views[view_id], 'checkable', default=False):
                successors = self._extract_all_children(view_id)
                for successor in successors:
                    if successor != view_id and self.__safe_dict_get(self.views[successor], 'checkable', False):
                        self.views[view_id]['checkable'] = False
                        break
    
    def _get_ancestor_id(self, view, key, default=None):
        if self.__safe_dict_get(view, key=key, default=False):
            return view['temp_id']
        all_views = [view] + [self.views[i] for i in self.get_all_ancestors(view)]
        for v in all_views:
            value = self.__safe_dict_get(v, key)
            if value:
                return v['temp_id']
        return default

    
    def _get_children_checked(self, children_ids):
        for childid in children_ids:
            if self.__safe_dict_get(self.views[childid], 'checked', default=False):
                return True
        return False
    
    def _get_children_checkable(self, children_ids):
        for childid in children_ids:
            if self.__safe_dict_get(self.views[childid], 'checkable', default=False):
                return True
        return False
    
    def _has_clickable_children(self, id):
        children = self._extract_all_children(id)
        # children = 
        for child_view_id in children:
            clickable = self.__safe_dict_get(self.views[child_view_id], 'clickable', default=False)
            checkable = self.__safe_dict_get(self.views[child_view_id], 'checkable', default=False) 
            if clickable or checkable:
                return True
        return False

    def get_described_actions(self, prefix='', remove_time_and_ip=False,
                                merge_buttons =False, add_edit_box = True, add_check_box = True, add_pure_text = True):
        """
        Get a text description of current state
        """
        enabled_view_ids = []
        for view_dict in self.views:
            if self.__safe_dict_get(view_dict, 'visible-to-user') and \
                self.__safe_dict_get(view_dict, 'resource-id') not in \
               ['android:id/navigationBarBackground',
                'android:id/statusBarBackground']:
                enabled_view_ids.append(view_dict['temp_id'])
        
        text_frame = "<p id=@ text='&'>#</p>"
        btn_frame = "<button id=@ text='&'>#</button>"
        checkbox_frame = "<checkbox id=@ checked=$ text='&'>#</checkbox>"
        input_frame = "<input id=@ text='&'>#</input>"

        view_descs = []
        available_actions = []
        removed_view_ids = []

        important_view_ids = []

        for view_id in enabled_view_ids:
            if view_id in removed_view_ids:
                continue
            # print(view_id)
            view = self.views[view_id]
            clickable = self._get_self_ancestors_property(view, 'clickable')
            scrollable = self.__safe_dict_get(view, 'scrollable')
            checkable = self._get_self_ancestors_property(view, 'checkable')
            long_clickable = self._get_self_ancestors_property(view, 'long_clickable')
            editable = self.__safe_dict_get(view, 'editable')
            actionable = clickable or scrollable or checkable or long_clickable or editable
            checked = self.__safe_dict_get(view, 'checked', default=False)
            selected = self.__safe_dict_get(view, 'selected', default=False)
            # content_description = self.__safe_dict_get(view, 'content_description', default='')
            content_description = self.__safe_dict_get(view, 'content-desc', default='')
            view_text = self.__safe_dict_get(view, 'text', default='')
            view_class = self.__safe_dict_get(view, 'class').split('.')[-1]
            if not content_description and not view_text and scrollable == 'false' and clickable == 'false':  # actionable?
                continue
            import re
            focusable = self.__safe_dict_get(view, 'focusable')
            class_name = self.__safe_dict_get(view, 'class')
            package_name = self.__safe_dict_get(view, 'package')
            resource_id = self.__safe_dict_get(view, 'resource-id')
            re_pattern = r':id/([^/]+)'
            match = re.search(re_pattern, resource_id)
            resource_id_text = ''
            if match:
                resource_id_text = match.group(1)
            if re.search(r'systemui', resource_id, re.IGNORECASE) or re.search(r'systemui', package_name, re.IGNORECASE):
                continue
            if re.search(r'edit', class_name, re.IGNORECASE) is not None:
                view_desc = input_frame.replace('@', str(len(view_descs))).replace('#', view_text)
                if content_description:
                    view_desc = view_desc.replace('&', content_description)
                else:
                    view_desc = view_desc.replace('&', resource_id_text)
                    # view_desc = view_desc.replace(" text='&'", "")
                # view_desc = view_desc.replace('*&*', str(view_id))
                view_descs.append(view_desc)
                available_actions.append(SetTextEvent(view=view, text='HelloWorld'))
                important_view_ids.append([content_description + view_text,view_id])

            elif checkable == 'true':
                view_desc = checkbox_frame.replace('@', str(len(view_descs))).replace('#', view_text).replace('$',
                                                                                                              str(checked or selected))
                if content_description:
                    view_desc = view_desc.replace('&', content_description)
                else:
                    view_desc = view_desc.replace(" text='&'", "")
                view_descs.append(view_desc)
                if add_check_box:
                    available_actions.append(TouchEvent(view=view))
                else:
                    available_actions.append(None)
            elif clickable == 'true':  # or long_clickable
                if merge_buttons:
                    # below is to merge buttons, led to bugs
                    clickable_ancestor_id = self._get_ancestor_id(view=view, key='clickable')
                    if not clickable_ancestor_id:
                        clickable_ancestor_id = self._get_ancestor_id(view=view, key='checkable')
                   
                    clickable_children_ids = self._extract_all_children(id=clickable_ancestor_id)

                    if view_id not in clickable_children_ids:
                        clickable_children_ids.append(view_id)

                    view_text, content_description, important_view_ids = self._merge_textv2(clickable_children_ids,
                                                                                            remove_time_and_ip,
                                                                                            important_view_ids)
                    checked = self._get_children_checked(clickable_children_ids)
                    
                view_desc = btn_frame.replace('@', str(len(view_descs))).replace('#', view_text)
                if content_description:
                    view_desc = view_desc.replace('&', content_description)
                else:
                    if resource_id_text:
                        view_desc = view_desc.replace('&', resource_id_text)
                    else:
                        if not view_text:
                            view_desc = None
                            continue

                view_descs.append(view_desc)
                available_actions.append(TouchEvent(view=view))


            elif scrollable == 'true':
                continue
                
            else: 
                view_desc = text_frame.replace('@', str(len(view_descs))).replace('#', view_text)

                if content_description:
                    view_desc = view_desc.replace('&', content_description)
                else:
                    view_desc = view_desc.replace(" text='&'", "")
                view_descs.append(view_desc)

                important_view_ids.append([content_description + view_text,view_id])

                available_actions.append(TouchEvent(view=view))
        view_descs.append(f"<button id={len(view_descs)}>go back</button>")
        available_actions.append(KeyEvent(name='BACK'))
        # state_desc = 'The current state has the following UI elements: \n' #views and corresponding actions, with action id in parentheses:\n '
        state_desc = prefix #'Given a screen, an instruction, predict the id of the UI element to perform the insturction. The screen has the following UI elements: \n'
        # state_desc = 'You can perform actions on a contacts app, the current state of which has the following UI views and corresponding actions, with action id in parentheses:\n'
        state_desc += '\n'.join(view_descs)
        
        views_without_id = self._remove_view_ids(view_descs)
        # print(views_without_id)
        return state_desc, available_actions, views_without_id, important_view_ids
    
    
    def get_action_descv2(self, action, view_desc):
        desc = action.event_type
        if isinstance(action, KeyEvent):
            desc = '- TapOn: ' + view_desc
        if isinstance(action, UIEvent):
            if isinstance(action, LongTouchEvent):
                desc = '- LongTapOn: ' + view_desc
            elif isinstance(action, SetTextEvent):
                desc = '- TapOn: ' + view_desc  + ' InputText: ' + action.text
            elif isinstance(action, ScrollEvent):
                desc = f'- Scroll{action.direction.lower()}: ' + view_desc
            else:
                desc = '- TapOn: ' + view_desc
        return desc
    
    def process_xml(self):
        import xml.etree.ElementTree as ET
        import xml.dom.minidom
        tree = ET.fromstring(self.xml_tree)
        
        def process_element(element, layer, index):
            attrib_text = {
                "text": "text",
                "id": "resource-id",
                "description": "content-desc",
                "class": "class",
                "hint": "hint"
            }

            attrib_bool = {
                "checkable": "checkable",
                "checked": "checked",
                "clickable": "clickable",
                "scrollable": "scrollable",
                "long-clickable": "long-clickable",
                "selected": "selected",
                "NAF": "NAF" 
            }

            attrib_int = {
                "bounds": "bounds",
                "index": "index",
            }

            new_text_attrib = {
                key: element.attrib[value] for key, value in attrib_text.items() if
                value in element.attrib and element.attrib[value] != ""
            }

            new_bool_attrib = {
                key: element.attrib[value] for key, value in attrib_bool.items() if
                value in element.attrib and element.attrib[value] != "false"
            }

            new_int_attrib = {
                key: element.attrib[value] for key, value in attrib_int.items() if value in element.attrib
            }

            if "id" in new_text_attrib:
                new_text_attrib["id"] = new_text_attrib["id"].split("/")[-1]

            new_text_attrib.update(new_bool_attrib)
            new_text_attrib.update(new_int_attrib)

            class_name = element.attrib.get("class", "unknown")
            class_name_short = class_name.split(".")[-1]

            if class_name_short == "EditText" or class_name_short == "AutoCompleteTextView":
                new_element = ET.Element("input", new_text_attrib)

            elif class_name_short in ["FrameLayout", "LinearLayout", "RelativeLayout", "ViewGroup", "ConstraintLayout", 
                                    "LinearLayoutCompat",
                                    "unknown"]:
                new_element = ET.Element("div", new_text_attrib)
                if "index" in new_element.attrib:
                    del new_element.attrib["index"]

            elif class_name_short == "ImageView":
                new_element = ET.Element("img", new_text_attrib)

            elif class_name_short == "TextView":
                new_element = ET.Element("p", new_text_attrib)
                
            elif new_bool_attrib.get("scrollable", "") == "true":
                new_element = ET.Element("scroll", new_text_attrib)
            elif new_text_attrib.get("clickable", "") == "true":
                new_element = ET.Element("button", new_text_attrib)

            elif new_text_attrib.get("checkable", "") == "true":
                new_element = ET.Element("checker", new_text_attrib)
            else:
                new_element = ET.Element(class_name.split(".")[-1], new_text_attrib)
                
            if "index" in new_element.attrib:
                new_element.attrib["index"] = str(index)
            
            layer += 1

            if 'clickable' in new_element.attrib:
                del new_element.attrib['clickable']
            if 'long-clickable' in new_element.attrib:
                del new_element.attrib['long-clickable']
            if 'class' in new_element.attrib:
                del new_element.attrib['class']

            for child in element:
                new_child, index = process_element(child, layer, index + 1)           
                if new_child is not None:
                    new_element.append(new_child)

            return new_element, index

        def simplify_element(elem, parent=None):
            if 'id' in elem.attrib:
                if elem.attrib['id'] in \
                ['navigationBarBackground',
                    'statusBarBackground',
                    'status_bar']:
                    if parent is not None:
                        parent.remove(elem)
                    return
            for child in list(elem):
                simplify_element(child, parent=elem)

            if len(elem) == 0 and all(attr not in elem.attrib for attr in ['id','text', 'description']):
                if parent is not None:
                    parent.remove(elem)

        def reorder_index(element, index):
            element.attrib['index'] = str(index)
            index += 1

            for child in element:
                index = reorder_index(child, index)

            return index
    

        all_list = [] 
        new_tree, _ = process_element(tree, 1, 1)
        simplify_element(new_tree)
        reorder_index(new_tree, 0)
        encoded_xml = ET.tostring(new_tree, encoding='unicode')
        pretty_xml = xml.dom.minidom.parseString(encoded_xml).toprettyxml()
        from lxml import etree
        root = etree.fromstring(pretty_xml)
        minified_xml = etree.tostring(root, encoding='utf-8', pretty_print=False, xml_declaration=False).decode('utf-8').replace("\n","").replace("\r","").replace("\t","")
        return minified_xml, pretty_xml
    
    def extract_info_from_xml(self, xml_string):
        import xml.etree.ElementTree as ET
        import xml.dom.minidom
        tree = ET.fromstring(xml_string)

        important_list = []
        ancestors = []
        leaf_ancestors_map = {}
        all_list = []

        def group_by_position(map_data):
            from collections import defaultdict
            result_map = []
            
            max_length = max(len(values) for values in map_data.values())
            
            for i in range(max_length):
                group_map = defaultdict(list)
                
                for key, values in map_data.items():
                    if i < len(values): 
                        value = values[i] 
                        group_map[value].append(key)
                    else:
                        value = values[-1]
                        group_map[value].append(key)
                if group_map and len(group_map) > 1:
                    result_map.append(dict(group_map))
            
            return result_map
        
        def extract_important_info(element, important_list, ancestors, leaf_ancestors_map, all_list, available_actions, parent_id=None):      
            import re
            class BoundingBox:
                def __init__(self, start_x, start_y, width, height):
                    self.x = start_x
                    self.y = start_y
                    self.width = width
                    self.height = height

                def __repr__(self):
                    return f"BoundingBox(start_x={self.x}, start_y={self.y}, width={self.width}, height={self.height})"
                
            def element_to_string(element):
                tag = element.tag
                attributes_string = " ".join(f'{key}="{value}"' for key, value in element.attrib.items())
                element_string = f"<{tag} {attributes_string}/>"
                return element_string


            children_id_tmp = []
            element_map = {}
            
            if 'id' in element.attrib:
                element_map['resource-id'] = element.attrib["id"]
            
            element_map['parent_id'] = parent_id

            for child in element:
                children_id_tmp.append(int(child.attrib["index"]))
            element_map['children_id'] = children_id_tmp

            all_list.append(element_map)

            ancestors.append(int(element.attrib['index']))
        
            if (element.tag == "input") or ('text' in element.attrib and element.attrib['text'].strip() != "") or ('description' in element.attrib and element.attrib['description'].strip() != ""): # or ('NAF' in element.attrib and element.attrib['NAF'].strip() == "true")
                if element.tag == "input":
                    view = {}
                    bounds_str = element.attrib['bounds']
                    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        width = x2 - x1
                        height = y2 - y1
                        view["bounds"] = BoundingBox(x1, y1, width, height)
                    del element.attrib['bounds']
                    available_actions.append(SetTextEvent(view=view))
                else:
                    view = {}
                    bounds_str = element.attrib['bounds']
                    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds_str)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        width = x2 - x1
                        height = y2 - y1
                        view["bounds"] = BoundingBox(x1, y1, width, height)
                    del element.attrib['bounds']
                    available_actions.append(TouchEvent(view=view))
                important_list.append(element_to_string(element))
                if len(ancestors) <= 1:
                    leaf_ancestors_map[int(element.attrib['index'])] = []
                else:
                    leaf_ancestors_map[int(element.attrib['index'])] = list(ancestors[:-1])
            
            if 'bounds' in element.attrib:
                    del element.attrib['bounds']

            for child in element:
                child_id = element.attrib.get("index")
                extract_important_info(child, important_list, ancestors, leaf_ancestors_map, all_list, available_actions, parent_id=child_id)  
            ancestors.pop()      

        available_actions = []
        extract_important_info(tree, important_list, ancestors, leaf_ancestors_map, all_list, available_actions)
        important_map = {}

        import re
        for i, item in enumerate(important_list):
            match = re.search(r'index="(\d+)"', item)
            if match:
                old_index = int(match.group(1))
                new_index = i
                updated_item = item.replace(f'index="{old_index}"', f'index="{new_index}"')
                important_map[old_index] = updated_item
        print(important_map)

        results = group_by_position(leaf_ancestors_map)

        for step, groups in enumerate(results):
            print(f"Step {step}: {groups}")

        def to_readable_results(results, all_list):
            all_step_results = []
            for one_step in results:
                result = []
                index = 0
                for key, indices in one_step.items():
                    extracted_items = [important_map[index] for index in indices]  
                    if 'resource-id' in all_list[key]:
                        tmp = "Section " + f'{index} with resouce id ' + all_list[key]['resource-id']
                    else:
                        tmp = f"Section {index} with no resource id"
                    index += 1
                    result.append(f"{tmp}:\n" + "\n".join(extracted_items) + "\n")
                all_step_results.append("\n".join(result))
            return all_step_results
        
        readable_results = to_readable_results(results, all_list)

        return all_list, important_map, leaf_ancestors_map, results, readable_results, available_actions
    