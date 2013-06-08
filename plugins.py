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
from tornado.web import UIModule

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

        database = settings.get('database',{})\
                           .get('run_model')

        if database:
            Plugins._meta.database = database
            #database.connect()

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
    if _application:
        _application.sync_ping()
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
               
    
    @staticmethod
    def on_init(method):
        '''
          控制器初始化时执行
        '''

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

# 安装插件
@gen.engine
def install(plugin_name):
    global _application
    register = import_object(plugin_name.strip() + '.register')
    
    name = register._handler.__module__ + \
           '.' + register._handler.__name__

    count = yield gen.Task(Plugins.select().where(Plugins.name == name).count)
    if count == 0 :       
        plugin = import_object(name)()
        plugin.install()

        # 尝试自加加载 ui_modules.py
        try:
            ui_modules = import_object(plugin_name + '.uimodules')
            for v in dir(ui_modules):
                if issubclass(getattr(ui_modules,v), UIModule) \
                and v != 'UIModule':
                    plugin.add_ui_module(v)
        except Exception, e:
            pass

        # 尝试自加加载 handlers.py
        try:
            handlers = import_object(plugin_name + '.handlers')
            reload(handlers)
            for v in dir(handlers):
              
                if issubclass(getattr(handlers,v), RequestHandler) \
                and v != 'RequestHandler':

                    plugin.add_handler(v)
        except Exception, e:
            pass


        handlers = []
        for v in plugin._handlers:
            handlers.append(
                v.__module__ + '.' + v.__name__
            )

        ui_modules = []
        for v in plugin._ui_modules:
            ui_modules.append(
                v.__module__ + '.' + v.__name__
            )

        pl = Plugins()
        pl.name        = name
        pl.bind        = Json.encode(register._targets)
        pl.handlers    = Json.encode(handlers)
        pl.ui_modules  = Json.encode(ui_modules)

        #TODO form 部分重构
        # if plugin.get_form() :
        #     pl.config = Json.encode(plugin.get_form().get_default_values())
        yield gen.Task(pl.save)

        # 通知 application 同步
        if _application:
            _application.sync_ping()


# 卸载插件
@gen.engine
def uninstall(plugin_name):
    register = import_object(plugin_name.strip() + '.register')
    
    name = register._handler.__module__ + \
           '.' + register._handler.__name__

    ar = Plugins.select().where(Plugins.name == name)
    count = yield gen.Task(ar.count)
    if count == 1 :
        plugin = import_object(name)()
        plugin.uninstall()

        ret = yield gen.Task(Plugins.delete()\
                                    .where(Plugins.name == name)\
                                    .execute)

        # 通知 application 同步
        if ret and _application:
            _application.sync_ping()

class Register(object):
    '''
    插件注册表
    '''
    
    def __init__(self):
        self._handler = False
        self._targets = {}
        self._events  = (
            'on_init' , 
            'before_execute' , 
            'before_render' ,
            'on_finish' ,
        )

    # 注册对象
    def handler(self):
        def decorator(handler):
            self._handler = handler
            return handler
        return decorator

    # 绑定事件
    def bind(self, event, targets):
        def decorator(func):
            if event in self._events:
                self._targets.setdefault(event,[])
                for v in targets :
                    self._targets[event].append({
                        'target' : v ,
                        'callback' : func.__name__
                    })
            return func
        return decorator


class Base(object):
    """
      插件的基类
    """

    def __init__(self):

        self.module = self.__class__.__module__

        self.full_name = self.module + '.' + self.__class__.__name__

  
        # 运行时的上下文
        self._context = {}

        # 插件的控制器
        self._handlers = []

        # ui modules
        self._ui_modules = []


    '''
      安装时执行

    '''
    def install(self):
        pass

    '''
      卸载时执行
    '''
    def uninstall(self):
        pass

    def get_form(self):
        return False

    # 取配置
    @property
    def config(self):
        return get_config(self.full_name , {})

    def set_config(self, config):
        set_config(self.full_name, config)

    '''
      添加控制器
    '''
    def add_handler(self, handler):
        handler = self.module + '.handlers.' + handler
        handler = import_object(handler)
        if handler not in self._handlers:
            self._handlers.append(handler)

    '''
      添加 UI models
    '''
    def add_ui_module(self, ui_module):
        ui_module = self.module + '.uimodules.' + ui_module
        ui_module = import_object(ui_module)
        if ui_module not in self._ui_modules:
            self._ui_modules.append(ui_module)

