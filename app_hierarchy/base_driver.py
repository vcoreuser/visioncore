#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import abc
from io import FileIO
import typing
from typing import Iterator, Dict, List, Optional, Tuple, Union
from PIL import Image
from pydantic import BaseModel

class CurrentAppResponse(BaseModel):
    package: str
    activity: Optional[str] = None
    pid: Optional[int] = None

class DeviceInfo(BaseModel):
    serial: str
    model: str = ""
    name: str = ""
    status: str = ""
    enabled: bool = True

class ShellResponse(BaseModel):
    output: str
    error: Optional[str] = ""

class Rect(BaseModel):
    x: int
    y: int
    width: int
    height: int

class Node(BaseModel):
    key: str
    name: str
    bounds: Optional[Tuple[float, float, float, float]] = None
    rect: Optional[Rect] = None
    properties: Dict[str, Union[str, bool]] = {}
    children: List[Node] = []

class WindowSize(typing.NamedTuple):
    width: int
    height: int

class AppInfo(BaseModel):
    packageName: str

class BaseDriver(abc.ABC):
    def __init__(self, serial: str):
        self.serial = serial

    @abc.abstractmethod
    def screenshot(self, id: int) -> Image.Image:
        """Take a screenshot of the device
        :param id: physical display ID to capture (normally: 0)
        :return: PIL.Image.Image
        """
        raise NotImplementedError()
    
    @abc.abstractmethod
    def dump_hierarchy(self) -> Tuple[str, Node]:
        """Dump the view hierarchy of the device
        :return: xml_source, Hierarchy
        """
        raise NotImplementedError()
    
    def shell(self, command: str) -> ShellResponse:
        """Run a shell command on the device
        :param command: shell command
        :return: ShellResponse
        """
        raise NotImplementedError()
    
    def tap(self, x: int, y: int):
        """Tap on the screen
        :param x: x coordinate
        :param y: y coordinate
        """
        raise NotImplementedError()

    def window_size(self) -> WindowSize:
        """ get window UI size """
        raise NotImplementedError()

    def app_install(self, app_path: str):
        """ install app """
        raise NotImplementedError()
    
    def app_current(self) -> CurrentAppResponse:
        """ get current app """
        raise NotImplementedError()
    
    def app_launch(self, package: str):
        """ launch app """
        raise NotImplementedError()
    
    def app_terminate(self, package: str):
        """ terminate app """
        raise NotImplementedError()
    
    def home(self):
        """ press home button """
        raise NotImplementedError()
    
    def back(self):
        """ press back button """
        raise NotImplementedError()

    def app_switch(self):
        """ switch app """
        raise NotImplementedError()
    
    def volume_up(self):
        """ volume up """
        raise NotImplementedError()
    
    def volume_down(self):
        """ volume down """
        raise NotImplementedError()
    
    def volume_mute(self):
        """ volume mute """
        raise NotImplementedError()

    def wake_up(self):
        """ wake up the device """
        raise NotImplementedError()
    
    def app_list(self) -> List[AppInfo]:
        """ list installed packages """
        raise NotImplementedError()
    
    def open_app_file(self, package: str) -> Iterator[bytes]:
        """ open app file """
        raise NotImplementedError()
