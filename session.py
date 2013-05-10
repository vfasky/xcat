#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date: 2013-05-10 14:36:13
# @Author: vfasky (vfasky@gmail.com)
# @Version: $Id$

'''
session
'''
import uuid 

class Base(object):

    def __init__(self, session_id = False, left_time = 1800, **settings):
        if False == session_id:
            session_id = str(uuid.uuid4())

        self.session_id = session_id
        self.left_time  = int(left_time)
        self.storage    = self.get_storage()

    def get_storage(self):
        pass

    # 返回 session id
    def id(self):
        return self.session_id

    # 设置session
    #def set(self, key, value, callback=None):
        #self.storage.set(key, value, callback)

    # 取值
    def get(self, key, default=None):
        return self.storage.get(key, default)

    ## 删除值
    #def delete(self , key):
        #if self.data.has_key(key):
            #del self.data[key]
            #self.__class__.set_data(self.session_id, self.data, self.left_time, self)

    ## 清空
    #def clear(self):
        #self.data = {}
        #self.__class__.delete_data(self.session_id,self)

    #def __getitem__(self, key):
        #return self.get(key)

    #def __setitem__(self, key, value):
        #return self.set(key , value)

    #def __delitem__(self, key):
        #return self.delete(key)

