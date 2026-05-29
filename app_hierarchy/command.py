import enum
from typing import Callable, Dict, List, Optional, Union
from pydantic import BaseModel
import time
import typing

from app_hierarchy.base_driver import Node, AppInfo, BaseDriver
from app_hierarchy.exceptions import ElementNotFoundError
from app_hierarchy.utils.common import node_travel

class Command(str, enum.Enum):
    TAP = "tap"
    TAP_ELEMENT = "tapElement"
    APP_INSTALL = "installApp"
    APP_CURRENT = "currentApp"
    APP_LAUNCH = "appLaunch"
    APP_TERMINATE = "appTerminate"
    APP_LIST = "appList"

    GET_WINDOW_SIZE = "getWindowSize"
    HOME = "home"
    DUMP = "dump"
    WAKE_UP = "wakeUp"
    FIND_ELEMENTS = "findElements"
    CLICK_ELEMENT = "clickElement"

    LIST = "list"

    # 0.4.0
    BACK = "back"
    APP_SWITCH = "appSwitch"
    VOLUME_UP = "volumeUp"
    VOLUME_DOWN = "volumeDown"
    VOLUME_MUTE = "volumeMute"

class TapRequest(BaseModel):
    x: Union[int, float]
    y: Union[int, float]
    isPercent: bool = False

class InstallAppRequest(BaseModel):
    url: str

class InstallAppResponse(BaseModel):
    success: bool
    id: Optional[str] = None

class CurrentAppResponse(BaseModel):
    package: str
    activity: Optional[str] = None
    pid: Optional[int] = None

class AppLaunchRequest(BaseModel):
    package: str
    stop: bool = False

class AppTerminateRequest(BaseModel):
    package: str

class WindowSizeResponse(BaseModel):
    width: int
    height: int

class DumpResponse(BaseModel):
    value: str

class By(str, enum.Enum):
    ID = "id"
    TEXT = "text"
    XPATH = "xpath"
    CLASS_NAME = "className"

class FindElementRequest(BaseModel):
    by: str
    value: str
    timeout: float = 10.0

class FindElementResponse(BaseModel):
    count: int
    value: List[Node]



COMMANDS: Dict[Command, Callable] = {}

def register(command: Command):
    def wrapper(func):
        COMMANDS[command] = func
        return func

    return wrapper

def get_command_params_type(command: Command) -> Optional[BaseModel]:
    func = COMMANDS.get(command)
    if func is None:
        return None
    type_hints = typing.get_type_hints(func)
    return type_hints.get("params")

def send_command(driver: BaseDriver, command: Union[str, Command], params=None):
    if command not in COMMANDS:
        raise NotImplementedError(f"command {command} not implemented")
    func = COMMANDS[command]
    params_model = get_command_params_type(command)
    if params_model:
        if params is None:
            raise ValueError(f"params is required for {command}")
        if isinstance(params, dict):
            params = params_model.model_validate(params)
        elif isinstance(params, params_model):
            pass
        else:
            raise TypeError(f"params should be {params_model}", params)
    if not params:
        return func(driver)
    return func(driver, params)

@register(Command.TAP)
def tap(driver: BaseDriver, params: TapRequest):
    """Tap on the screen
    :param x: x coordinate
    :param y: y coordinate
    """
    x = params.x
    y = params.y
    if params.isPercent:
        wsize = driver.window_size()
        x = int(wsize[0] * params.x)
        y = int(wsize[1] * params.y)
    driver.tap(x, y)

@register(Command.APP_INSTALL)
def app_install(driver: BaseDriver, params: InstallAppRequest):
    """install app"""
    driver.app_install(params.url)
    return InstallAppResponse(success=True, id=None)

@register(Command.APP_CURRENT)
def app_current(driver: BaseDriver) -> CurrentAppResponse:
    """get current app"""
    return driver.app_current()

@register(Command.APP_LAUNCH)
def app_launch(driver: BaseDriver, params: AppLaunchRequest):
    if params.stop:
        driver.app_terminate(params.package)
    driver.app_launch(params.package)

@register(Command.APP_TERMINATE)
def app_terminate(driver: BaseDriver, params: AppTerminateRequest):
    driver.app_terminate(params.package)

@register(Command.GET_WINDOW_SIZE)
def window_size(driver: BaseDriver) -> WindowSizeResponse:
    wsize = driver.window_size()
    return WindowSizeResponse(width=wsize[0], height=wsize[1])

@register(Command.HOME)
def home(driver: BaseDriver):
    driver.home()

@register(Command.BACK)
def back(driver: BaseDriver):
    driver.back()

@register(Command.APP_SWITCH)
def app_switch(driver: BaseDriver):
    driver.app_switch()

@register(Command.VOLUME_UP)
def volume_up(driver: BaseDriver):
    driver.volume_up()

@register(Command.VOLUME_DOWN)
def volume_down(driver: BaseDriver):
    driver.volume_down()

@register(Command.VOLUME_MUTE)
def volume_mute(driver: BaseDriver):
    driver.volume_mute()

@register(Command.DUMP)
def dump(driver: BaseDriver) -> DumpResponse:
    source, _ = driver.dump_hierarchy()
    return DumpResponse(value=source)

@register(Command.WAKE_UP)
def wake_up(driver: BaseDriver):
    driver.wake_up()

def node_match(node: Node, by: By, value: str) -> bool:
    if by == By.ID:
        return node.properties.get("resource-id") == value
    if by == By.TEXT:
        return node.properties.get("text") == value
    if by == By.CLASS_NAME:
        return node.name == value
    raise ValueError(f"not support by {by!r}")

@register(Command.FIND_ELEMENTS)
def find_elements(driver: BaseDriver, params: FindElementRequest) -> FindElementResponse:
    _, root_node = driver.dump_hierarchy()
    # TODO: support By.XPATH
    nodes = []
    for node in node_travel(root_node):
        if node_match(node, params.by, params.value):
            nodes.append(node)
    return FindElementResponse(count=len(nodes), value=nodes)

@register(Command.CLICK_ELEMENT)
def click_element(driver: BaseDriver, params: FindElementRequest):
    node = None
    deadline = time.time() + params.timeout
    while time.time() < deadline:
        result = find_elements(driver, params)
        if result.value:
            node = result.value[0]
            break
        time.sleep(.5) # interval
    if not node:
        raise ElementNotFoundError(f"element not found by {params.by}={params.value}")
    center_x = (node.bounds[0] + node.bounds[2]) / 2
    center_y = (node.bounds[1] + node.bounds[3]) / 2
    tap(driver, TapRequest(x=center_x, y=center_y, isPercent=True))

@register(Command.APP_LIST)
def app_list(driver: BaseDriver) -> List[AppInfo]:
    # added in v0.5.0
    return driver.app_list()