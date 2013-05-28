#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date: 2013-05-10 14:36:13
# @Author: vfasky (vfasky@gmail.com)
# @Version: $Id$

'''
session
'''

__all__ = [
    'Base',
    'Mongod',
]

import uuid 
import time
import asyncmongo

from tornado import gen


class Base(object):
    '''
    异步 session 基类
    '''


    def __init__(self, session_id = False, **settings):
        if False == session_id:
            session_id = str(uuid.uuid4())

        self.settings = settings
        self.session_id = session_id
        self.left_time = int(settings.get('left_time', 1800))
        self.storage = self.get_storage()
        
        
    @property
    def id(self):
        # 返回 session id
        return self.session_id

    def get_storage(self):
        pass

    def get_all(self, callback=None):
        def _remove_callback():
            callback({})

        def _update_callback(value):
            data = value.get('data', {})
            callback(data)

        def _callback(value):
            if not value:
                return callback({})

            this_time = int(time.time())
            cache_life = value.get('time', 0) + self.left_time
            if cache_life < this_time:
                # 缓存已经失效
                self.remove(callback=_remove_callback)
            elif (cache_life - this_time) > (self.left_time / 2):
                # 缓存周期已经超过生存周期的一半，更新时间周期
                self.storage.set(value.get('data', {}), callback=_update_callback)
            else:
                data = value.get('data', {})
                callback(data)

        self.storage.get(callback=_callback)

    def set(self, key, value, callback=None):
        def _callback(data):
            data[key] = value
            self.storage.set(data, callback)

        self.get_all(_callback)

    def get(self, key, default=None, callback=None):
        def _callback(data):
         
            if not data:
                return callback(default)
     
            callback(data.get(key, default))

        self.get_all(callback=_callback)

    def remove(self, key, callback=None):
        def _set_callback(data):
            if data:
                callback(True)
            else:
                callback(False)

        def _callback(data):
            if not data:
                return callback(False)

            if data.has_key(key):
                del data[key]
                self.storage.set(data, _set_callback)
            else:
                callback(False)

        self.get_all(callback=_callback)

    def clear(self, callback=None):
        self.storage.remove(callback)

class Mongod(Base):
    """"基于Mongod的session"""

    class Storage(object):

        def __init__(self, conn, table, session_id, left_time):
            self._conn = conn
            self._table = self._conn[table]
            self.session_id = session_id
            self.left_time = left_time
            self.where = {'session_id': session_id}

        def get(self, callback=None):
            def _callback(value, error):
                if error:
                    raise Error(error)
                if value:
                    callback(value)
                else:
                    callback(None)

            self._table.find_one(self.where, callback=_callback)   

        def remove(self, callback):
            def _callback(data, error):
                if error:
                    raise Error(error)

                if callback:
                    callback(len(data) == 1)

            self._table.remove(self.where, callback=_callback)


        @gen.engine
        def set(self, value, callback):
            session_data = {
                'session_id' : self.session_id,
                'data' : value,
                'time' : int(time.time())
            }

            def _callback(data, error):
                if error:
                    raise Error(error)

                if callback:
                    callback(session_data)

            ret, error = yield gen.Task(self._table.find_one, self.where)
            data = ret[0]
            
            if not data or len(data) == 0:
                self._table.insert(session_data, callback=_callback)
            else:
                self._table.update({
                    '_id' : data['_id']
                }, session_data, upsert=True, safe=True, callback=_callback)
                
    def get_storage(self):
        kwargs = self.settings
        conn = asyncmongo.Client(
            pool_id = kwargs.get('pool_id', 'xcat.session.Mongod'), 
            host = kwargs.get('host', '127.0.0.1'), 
            port = kwargs.get('port', 27017), 
            maxcached = kwargs.get('maxcached', 10), 
            maxconnections = kwargs.get('maxconnections', 50), 
            dbname = kwargs.get('dbname', 'session')
        )

        table = kwargs.get('table', 'sessions')

        return self.Storage(conn, table, self.session_id, self.left_time)
        
'''
测试 and 用法
'''
if __name__ == '__main__':
    from tornado.ioloop import IOLoop
    from tornado.httpserver import HTTPServer
    #from tornado.options import parse_command_line
    from tornado.web import asynchronous, RequestHandler, Application

    class Handler(RequestHandler):

        def initialize(self):
            key = 'PYSESSID'
            
            if self.get_secure_cookie(key):
                self.session = Mongod(self.get_secure_cookie(key))
            else:
                session = Mongod(str(uuid.uuid4()))
                self.set_secure_cookie(key , session.id)
                self.session = session
            

        @asynchronous
        @gen.engine
        def get(self):
            ret = yield gen.Task(self.session.set, 'test2', {'hello': 'word'})
            print ret
            data = yield gen.Task(self.session.get, 'test2')
            print data 
            ret = yield gen.Task(self.session.remove, 'test2')
            print ret
            ret = yield gen.Task(self.session.clear)
            print ret

            self.finish()
            
    application = Application([
        (r'/', Handler),
    ], debug=True, cookie_secret="fsfwo#@(sfk")

    http_server = HTTPServer(application)
    http_server.listen(8181)
    IOLoop.instance().start()

