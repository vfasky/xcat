#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date: 2013-05-02 16:22:09
# @Author: vfasky (vfasky@gmail.com)
# @Version: $Id$

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.options import parse_command_line
from tornado.web import asynchronous, RequestHandler, Application

import mopee
import peewee

database = mopee.PostgresqlAsyncDatabase('test',
    user = 'vfasky',
    host = '192.168.2.146',
    password = '19851024',
    size = 20,
)

    

syncdatabase = peewee.PostgresqlDatabase('test', 
    user='vfasky', 
    host = '192.168.2.146',
    port='5432',
    password='19851024')





database.connect()

#def _callback(exists):
    #if not exists:
        #User.create_table()

#User.table_exists(callback=_callback)


class AsyncHandler(RequestHandler):
    @asynchronous
    @gen.engine
    def get(self):
        
        class User(mopee.AsyncModel):
            class Meta:
                database = database

            name = mopee.CharField()
            password = mopee.CharField(max_length = 255)

        exists =  yield gen.Task(User.table_exists)
        if not exists:
            User.create_table()

        #user = User(
            #name = 'vfasky',
            #password = '1233',
        #)
        #pk = yield gen.Task(user.save)
        #print pk

        user = yield gen.Task(User.select().where(User.name == 'vfasky').get)
        self.write(user.name)
        self.finish()

class SyncHandler(RequestHandler):
    def get(self):
        class User(peewee.Model):
            class Meta:
                database = syncdatabase

            name = mopee.CharField()
            password = mopee.CharField(max_length = 255)

        user = User.select().where(User.name == 'vfasky').get()
        self.write(user.name)


if __name__ == '__main__':
 
    application = Application([
        (r'/', AsyncHandler),
        (r'/sync/', SyncHandler),
    ], debug=True)

    http_server = HTTPServer(application)
    http_server.listen(8181, 'localhost')
    IOLoop.instance().start()
