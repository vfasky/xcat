#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2013-05-29 15:08:04
# @Author  : vfasky (vfasky@gmail.com)
# @Link    : http://vfasky.com
# @Version : $Id$

'''
表单
'''
# Python 2/3 compat
def with_metaclass(meta, base=object):
    return meta("NewBase", (base,), {})

class BaseForm(type):
    """表单基类"""

    _fields = []

    def __new__(cls, name, bases):
        if not bases:
            return super(BaseForm, cls).__new__(cls, name, bases)
         
        print cls.__dict__.items()

class Form(with_metaclass(BaseForm)):
    name = 'test'
    dd = 'sd'
    z = 'sdf'
    a = 'sd'

    def __init__(self, *args, **kwargs):
        pass

if __name__ == '__main__':
    

    f = Form()
    