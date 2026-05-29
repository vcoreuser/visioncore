#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from app_hierarchy.exceptions import IOSDriverException


class NotPairedError(IOSDriverException):
    pass



class MuxException(IOSDriverException):
    pass


class MuxVersionError(MuxException):
    pass


class BadCommandError(MuxException):
    pass


class BadDevError(MuxException):
    pass


class ConnectionFailedError(MuxException):
    pass


class ConnectionFailedToUsbmuxdError(ConnectionFailedError):
    pass


class ArgumentError(IOSDriverException):
    pass