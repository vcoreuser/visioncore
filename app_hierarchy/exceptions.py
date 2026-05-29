#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class UiautoException(Exception):
    pass


class IOSDriverException(UiautoException):
    pass


class AndroidDriverException(UiautoException):
    pass


class AppiumDriverException(UiautoException):
    pass


class MethodError(UiautoException):
    pass


class ElementNotFoundError(MethodError):
    pass


class RequestError(UiautoException):
    pass