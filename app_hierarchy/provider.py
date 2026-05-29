#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import abc
from functools import lru_cache
import adbutils

from app_hierarchy.android_driver import AndroidDriver
from app_hierarchy.base_driver import BaseDriver, DeviceInfo, Node
from app_hierarchy.exceptions import UiautoException
from app_hierarchy.utils.usbmux import MuxDevice, list_devices


class BaseProvider(abc.ABC):
    @abc.abstractmethod
    def list_devices(self) -> list[DeviceInfo]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_device_driver(self, serial: str) -> BaseDriver:
        raise NotImplementedError()
    
    def get_single_device_driver(self) -> BaseDriver:
        """ debug use """
        devs = self.list_devices()
        if len(devs) == 0:
            raise UiautoException("No device found")
        if len(devs) > 1:
            raise UiautoException("More than one device found")
        return self.get_device_driver(devs[0].serial)


class AndroidProvider(BaseProvider):
    def __init__(self):
        pass

    def list_devices(self) -> list[DeviceInfo]:
        adb = adbutils.AdbClient()
        ret: list[DeviceInfo] = []
        for d in adb.list():
            if d.state != "device":
                ret.append(DeviceInfo(serial=d.serial, status=d.state, enabled=False))
            else:
                dev = adb.device(d.serial)
                ret.append(DeviceInfo(serial=d.serial, model=dev.prop.model, name=dev.prop.name))
        return ret

    @lru_cache
    def get_device_driver(self, serial: str) -> AndroidDriver:
        return AndroidDriver(serial)
    
if __name__ == "__main__":
    TEST = False
    TRAVEL = False
    provider = AndroidProvider()
    driver = provider.get_single_device_driver()
    
    from xml.etree import ElementTree
    import time
    if TEST:
        while True:
            xml_data, node = driver.dump_hierarchy()
            root = ElementTree.fromstring(xml_data)
            tree = ElementTree.ElementTree(root)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            with open(f'./output/{timestamp}.xml', "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True)
            with open(f'./output/{timestamp}.txt', "a", encoding="utf-8") as f:
                f.write(f'Timestamp: {timestamp}\n')
                f.write(f'{node}\n')
            time.sleep(10)
    elif TRAVEL:
        xml_data, root_node = driver.dump_hierarchy()
        from utils.common import node_travel
        nodes = []
        for node in node_travel(root_node):
            if "bounds" and "hint" and "drawing-order" in node.properties:
                del node.properties["bounds"]
                del node.properties["hint"]
                del node.properties["drawing-order"]
            node.properties["bounds"] = node.rect
            if "rotation" not in node.properties:
                nodes.append(node.properties)

    else:
        xml_data, root_node = driver.dump_hierarchy()
        nodes_list = []
        def __nodes_to_list(node:Node, nodes_list:list):
            tree_id = len(nodes_list)
            node.properties['temp_id'] = tree_id

            if "bounds" and "hint" and "drawing-order" in node.properties:
                del node.properties["bounds"]
                del node.properties["hint"]
                del node.properties["drawing-order"]
            node.properties["bounds"] = node.rect
            if "rotation" not in node.properties:
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
        __nodes_to_list(root_node, nodes_list)
        for node in nodes_list:
            print(node)