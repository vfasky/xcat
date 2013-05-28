#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2013-05-28 11:38:23
# @Author  : vfasky (vfasky@gmail.com)
# @Link    : http://vfasky.com
# @Version : $Id$
 
__all__ = [
    'get_work_names',
    'get_list',
    'get_config',
    'init',
    'reset',
]

import functools
from mopee import AsyncModel, CharField, TextField
from utils import Json, Date
from tornado import gen
from tornado.util import import_object 

# 绑定的 app 对象
_application = None
# 激活的插件
_work_plugins = []
# 插件配置
_config = {}
# 可用插件列表
_list = {}

class Plugins(AsyncModel):
    '''
    插件模型
    '''
    name        = CharField(max_length=100,unique=True)
    bind        = TextField()
    handlers    = TextField(default='[]') # 控制器
    ui_modules  = TextField(default='[]') # ui_modules
    config      = TextField(default='{}') # 配置


def init(method):
    # 插件初始化
    
    @functools.wraps(method)
    @gen.engine
    def wrapper(self, **settings):
        global _application 
        _application = self

        database = settings.get('database')

        if database:
            Plugins._meta.database = database
            database.connect()

            exists = yield gen.Task(Plugins.table_exists)

            if not exists:
                yield gen.Task(Plugins.create_table)

            yield gen.Task(reset)

        method(self, **settings)

    return wrapper

@gen.engine
def reset(callback=None):
    # 重置插件
    global _list , _config , _work_plugins, _application

    _work_plugins = []
    _config       = {}
    _list         = {}

    plugins = yield gen.Task(Plugins.select().order_by(Plugins.id.desc()).execute)
    
    for plugin_ar in plugins:
        _work_plugins.append(plugin_ar.name)
        _config[plugin_ar.name] = Json.decode(plugin_ar.config)
        plugin = import_object(str(plugin_ar.name))

        if _application:
            # 绑定 ui_modules
            for v in Json.decode(plugin_ar.ui_modules):
                _application.ui_modules[v.__name__] = import_object(str(v))
            
            # 绑定 header
            for v in Json.decode(plugin_ar.handlers):
                plugin_module = v.split('.handlers.')[0] + '.handlers'
                
                if plugin_module not in sys.modules.keys() :
                    import_object(str(plugin_module))
                else:
                    reload(import_object(str(plugin_module)))

        binds = Json.decode(plugin_ar.bind,{})
        for event in binds:
            _list.setdefault(event,[])
            for v in binds[event]:
                v['handler'] = plugin
                v['name'] = plugin_ar.name
                _list[event].append(v)

    if callback:
        callback(True)



# 取激活的插件名
def get_work_names():
    return _work_plugins

# 取可用插件列表
def get_list():
    return _list

# 取插件的配置
def get_config(plugin_name, default = {}):
    return _config.get(plugin_name,default)

# 设置插件配置
@gen.engine
def set_config(plugin_name, config, callback=None):
    global _config
    pl_ar = yield gen.Task(Plugins.get, Plugins.name == plugin_name)
    pl_ar.config = Json.encode(config)
    yield gen.Task(pl_ar.save)
    _config[plugin_name] = config
    #TODO , 是否需要 reset app
    if None:
        callback()

'''
  调用对应的插件
'''
def call(event, that):
    target   = that.__class__.__module__ + '.' + that.__class__.__name__
    handlers = []
    target   = target.split('handlers.').pop()

    for v in get_list().get(event,[]):
        if v['target'].find('*') == -1 and v['target'] == target:
            handlers.append(v)
        else:
            key = v['target'].split('*')[0]
            if target.find(key) == 0 or v['target'] == '*' :
                handlers.append(v)
    return handlers

class Events(object):
    '''
    handler 事件绑定
    '''
               
    '''
      控制器初始化时执行

        注： 这时数据库连接还未打开
    '''
    @staticmethod
    def on_init(method):

        @functools.wraps(method)
        @gen.engine
        def wrapper(self):
            handlers = call('on_init', self)
            is_run = True
            for v in handlers:
                plugin = v['handler']()
                # 设置上下文
                plugin._context = {
                    'self' : self ,
                }
                ret = yield gen.Task(getattr(plugin,v['callback']))
                if False == ret:
                    is_run = False
                    break
            
            if is_run:
                method(self)

        return wrapper

    # 控制器执行前调用
    @staticmethod
    def before_execute(method):

        @functools.wraps(method)
        @gen.engine
        def wrapper(self, transforms, *args, **kwargs):
            self._transforms = transforms

            handlers = call('before_execute', self)
            is_run = True
            for v in handlers:
                plugin = v['handler']()
                # 设置上下文
                plugin._context = {
                    'transforms' : transforms,
                    'args'       : args,
                    'kwargs'     : kwargs,
                    'self'       : self
                }
           
                ret = yield gen.Task(getattr(plugin,v['callback']))
                if False == ret:
                    is_run = False
                    break

                transforms = plugin._context['transforms']
                args       = plugin._context['args']
                kwargs     = plugin._context['kwargs']

            if is_run:
                method(self, transforms, *args, **kwargs)

        return wrapper

    # 渲染模板前调用
    @staticmethod
    def before_render(method):

        @functools.wraps(method)
        @gen.engine
        def wrapper(self, template_name, **kwargs):
            handlers = call('before_render', self)
            is_run = True
            for v in handlers:
                plugin = v['handler']()
                # 设置上下文
                plugin._context = {
                    'template_name' : template_name ,
                    'kwargs'        : kwargs ,
                    'self'          : self
                }
                ret = yield gen.Task(getattr(plugin,v['callback']))
                if False == ret:
                    is_run = False
                    break

                template_name = plugin._context['template_name']
                kwargs        = plugin._context['kwargs']
            
            if is_run:
                method(self, template_name, **kwargs)

        return wrapper

    # 完成http请求时调用
    @staticmethod
    def on_finish(method):

        @functools.wraps(method)
        @gen.engine
        def wrapper(self):
            handlers = call('on_finish', self)
            is_run = True
            for v in handlers:
                plugin = v['handler']()
                # 设置上下文
                plugin._context = {
                    'self' : self ,
                }
                ret = yield gen.Task(getattr(plugin,v['callback']))
                if False == ret:
                    is_run = False
                    break

            if is_run:
                method(self)

        return wrapper