#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2013-05-27 16:54:47
# @Author  : vfasky (vfasky@gmail.com)
# @Link    : http://vfasky.com
# @Version : $Id$

__all__ = [
    'acl',
    'route',
    'session',
    'Application',
    'RequestHandler'
]
import time
import functools
import session as Xsession
import utils
import plugins
import cache
import uuid
import re
from tornado.web import url, RequestHandler, \
     StaticFileHandler, Application
from tornado.escape import linkify
from tornado import gen
from tornado.options import options, define
from jinja2 import Environment, FileSystemLoader

def session(method):
    '''
    异步 session 的绑定
    '''

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        settings = self.settings.get('session', {})\
                                .get(self.settings['run_mode'], {})

        session_name = settings.get('name', 'PYSESSID')
        session_storage = settings.get('storage', 'Mongod')
        session_config  = settings.get('config', {})

        if hasattr(Xsession, session_storage):
            Session = getattr(Xsession, session_storage)

            if self.get_secure_cookie(session_name):
                self._session = Session(self.get_secure_cookie(session_name), **session_config)
            else:
                session = Session(**session_config)
                self.set_secure_cookie(session_name , session.id)
                self._session = session

            def none_callback(*args, **kwargs):
                pass

            def finish(self, *args, **kwargs):
                """
                This is a monkey patch finish which will save or delete
                session data at the end of a request.
                """
                super(self.__class__, self).finish(*args, **kwargs)

                if self.session:
                    self._session.storage.set(self.session, none_callback)
                else:
                    self._session.clear()

            def _callback(data):
                self.session = data
                self.finish = functools.partial(finish, self)

                method(self, *args, **kwargs)

            self._session.get_all(_callback)


    return wrapper



def acl(method):
    '''
    访问控制
    ==========

    ## 特殊标识:

     - ACL_NO_ROLE 没有角色用户
     - ACL_HAS_ROLE 有角色用户

    '''

    # 检查
    def check(rule, roles):

        if rule.get('deny', False):
            for r in roles:
                if r in rule['deny']:
                    return False

        if rule.get('allow', False):
            for r in roles:
                if r in rule['allow']:
                    return True

        return False

    # 取当前用户角色
    def get_roles(self):
        # 当前用户
        current_user = self.current_user

        # 格式化角色
        roles = []
        if None == current_user:
            roles.append('ACL_NO_ROLE')

        elif utils.Validators.is_dict(current_user):
            if False == ('roles' in current_user) \
                    or 0 == len(current_user['roles']):

                roles.append('ACL_NO_ROLE')
            else:
                roles.append('ACL_HAS_ROLE')

                for r in current_user['roles']:
                    roles.append(r)
        return roles


    @functools.wraps(method)
    def wrapper(self, transforms, *args, **kwargs):
        # 告诉浏览器不要缓存
        self.set_header('Pragma', 'no-cache')
        self.set_header('Expires', -1)

        # 唯一标识
        URI = self.__class__.__module__ + '.' + self.__class__.__name__
        # 访问规则
        rules = self.settings.get('acls', [])

        if len(rules) == 0:
            return method(self, transforms, *args, **kwargs)

        roles = False
        
        for r in rules:
            if r['URI'] == URI:
                if False == roles:
                    roles = get_roles(self)
                if False == check(r, roles):
                    self._transforms = transforms
                    self.on_access_denied()
                    return #self.finish()


        return method(self, transforms, *args, **kwargs)

    return wrapper

class _404Handler(RequestHandler):
    '''404 的处理'''

    def get(self, url):
        if hasattr(self,'is_reload'):
            return self.redirect(url)

        return self.write_error(404)

    def post(self, url):
        return self.get(url)



class Route(object):
    """
    extensions.route

    Example:

    @route(r'/', name='index')
    class IndexHandler(tornado.web.RequestHandler):
        pass

    class Application(tornado.web.Application):
        def __init__(self):
            handlers = [
            # ...
            ] + Route.routes()

    @link https://github.com/laoqiu/pypress-tornado/blob/master/pypress/extensions/routing.py
    """

    # 路由信息
    _routes = {}
    # 访问规则
    _acl = []
    
    def __init__(self, pattern, name=None, host='.*$', allow=None, deny=None, **kwargs):
        self.pattern = pattern
        self.kwargs = kwargs
        self.name = name
        self.host = host
        self.allow = allow
        self.deny  = deny

    def __call__(self, handler_class):
      
        URI   = handler_class.__module__ + '.' + handler_class.__name__
        name  = self.name or URI.split('.handlers.').pop()

        # acl
        allow = self.allow 
        deny  = self.deny 
        
        if allow or deny:
            index = False
            for acl in self._acl:
                if acl['URI'] == URI:
                    index = self._acl.index(acl)
                    break
     
            if False == index:
                item = {'URI' : URI, 'allow' : [], 'deny' : []}
                self._acl.append(item)
                index = self._acl.index(item)
    
            if allow:
                for r in allow:
                    if r not in self._acl[index]['allow']:
                        self._acl[index]['allow'].append(r)
                        
            if deny:
                for r in deny:
                    if r not in self._acl[index]['deny']:
                        self._acl[index]['deny'].append(r)
                    
        spec = url(self.pattern, handler_class, self.kwargs, name=name)

        self._routes.setdefault(self.host, [])
        if spec not in self._routes[self.host]:
            self._routes[self.host].append(spec)

        # 存放路由规则
        if False == hasattr(handler_class, 'routes'):
            handler_class.routes = []

        if len(handler_class.routes) > 0:
            if handler_class.routes[0]['URI'] != URI:
                handler_class.routes = []

        handler_class.routes.append({
            'name': name,
            'spec': spec,
            'URI': URI
        })
        return handler_class

    @classmethod
    def reset(cls):
        cls._acl = []
        cls._routes = {}

    @classmethod
    def reset_handlers(cls,application):
        settings = application.settings

        # 重置 handlers
        if settings.get("static_path") :
            path = settings["static_path"]
         
            static_url_prefix = settings.get("static_url_prefix",
                                             "/static/")
            static_handler_class = settings.get("static_handler_class",
                                                StaticFileHandler)
            static_handler_args = settings.get("static_handler_args", {})
            static_handler_args['path'] = path
            for pattern in [re.escape(static_url_prefix) + r"(.*)",
                            r"/(favicon\.ico)", r"/(robots\.txt)"]:

                item = url(pattern, static_handler_class, static_handler_args)
                cls._routes.setdefault('.*$', [])
                if item not in cls._routes['.*$'] :
                    cls._routes['.*$'].insert(0, item) 

        # 404
        item = url(r"/(.+)$", _404Handler)

        if cls._routes.get('.*$') and item not in cls._routes['.*$'] :
            cls._routes['.*$'].append(item) 
         
        application.handlers = []
        application.named_handlers = {}


    @classmethod
    def acl(cls, application=None):
        if application:
            application.settings['acls'] = cls._acl
        else:
            return cls._acl
    
    @classmethod
    def routes(cls, application=None):
        if application:
            cls.reset_handlers(application)
            for host, handlers in cls._routes.items():
                application.add_handlers(host, handlers)

        else:
            return reduce(lambda x,y:x+y, cls._routes.values()) if cls._routes else []

    @classmethod
    def url_for(cls, name, *args):
        named_handlers = dict([(spec.name, spec) for spec in cls.routes() if spec.name])
        if name in named_handlers:
            return named_handlers[name].reverse(*args)
        raise KeyError("%s not found in named urls" % name)

route = Route

def sync_app(method):
    '''
    同步各个app
    '''

    @functools.wraps(method)
    @gen.engine
    def wrapper(self, request):
        if self.cache:
            sync_id = yield gen.Task(self.cache.get, self._sync_key, 0)
            if sync_id != self._sync_id:
                #print '同步'
                ret = yield gen.Task(self.sync, sync_id)
        method(self, request)

    return wrapper


class Application(Application):
   
    def __init__(self, handlers=None, default_host="", transforms=None,
                 wsgi=False, **settings):

        if settings.get('template_path'):
            # 配置 jinja2
            self.jinja_env = Environment(
                loader = FileSystemLoader(settings['template_path']),
                auto_reload = settings['debug'],
                autoescape = settings['autoescape']
            )

        # 初始化 app 缓存
        self.cache = False

        cache_cfg = settings.get('cache',{}).get(settings['run_mode'])
        if cache_cfg and hasattr(cache, cache_cfg.get('storage', 'Mongod')):
            Cache = getattr(cache, cache_cfg.get('storage', 'Mongod'))
            self.cache = Cache(**cache_cfg.get('config', {}))
            self._sync_key = settings.get('sync_key', 'xcat.web.Application.id')
            

        ret = super(Application,self).__init__(
            handlers,
            default_host,
            transforms,
            wsgi,
            **settings
        )

        route.acl(self)
        route.routes(self)

        self.initialize(**settings)

        return ret

    def sync_ping(self):
        # 更新同步信号 
        if self.cache:
            self._sync_id = str(uuid.uuid4())
            # 同步 id
            self.sync(self._sync_id)

    @gen.engine
    def sync(self, sync_id, callback=None):
        route.acl(self)
        route.routes(self)

        # 重新加载 app handlers
        app_handlers = self.settings['app_path'].split(os.path.sep).pop() + '.handlers'
        handlers = import_object(app_handlers)
     
        for name in handlers.__all__:
            handler_module = import_object(app_handlers + '.' + name)
            reload(handler_module)
            for v in dir(handler_module):
                o = getattr(handler_module,v)
                if type(o) is types.ModuleType:
                    reload(o)

        self.initialize()

        # 标记已同步
        yield gen.Task(self.cache.set, self._sync_key, sync_id)

        if callback:
            callback(True)

    @sync_app
    def __call__(self, request):
        return super(Application, self).__call__(request)

    @plugins.init
    @gen.engine
    def initialize(self, **settings):
        if self.cache:
            self._sync_id = yield gen.Task(self.cache.get, self._sync_key, 0) 


class RequestHandler(RequestHandler):

    # 存放路由
    routes = []

    def finish(self, chunk=None):
        super(RequestHandler, self).finish(chunk)
        self._on_finish()

    def prepare(self):
        if not hasattr(options, ('tforms_locale')):
            define('tforms_locale', default=self._)
        #options.tforms_locale = self._

    @plugins.Events.on_finish
    def _on_finish(self):
        # 关闭数据库连接
        # database = self.settings.get('database')
        # if database:
        #     database.close()
        pass
        
    # 没有权限时的处理
    def on_access_denied(self):
        self.write_error(403)

    @plugins.Events.on_init
    def initialize(self):
        # 记录开始时间
        self._start_time = time.time()

        # 打开数据库连接
        # database = self.settings.get('database')
        # if database:
        #     database.connect()


    def is_ajax(self):
        return "XMLHttpRequest" == self.request.headers.get("X-Requested-With")

    # 多国语言
    def _(self, txt, plural_message=None, count=None):
        if txt == None:
            return txt
        return self.locale.translate(unicode(str(txt),'utf8'),plural_message,count)

    @plugins.Events.before_execute
    @acl
    def _execute(self, transforms, *args, **kwargs):
        return super(RequestHandler,self)._execute(transforms, *args, **kwargs)

    @plugins.Events.before_render
    def render(self, template_name, **kwargs):
        return super(RequestHandler,self).render(template_name, **kwargs)

    def render_string(self, template_name, **kwargs):
        context = {
            'Date' : utils.Date ,
            'url_for' : route.url_for ,
            '_' : self._ ,
            'handler' : self ,
            'request' : self.request ,
            'current_user' : self.current_user,
            'locale' : self.locale,
            'static_url' : self.static_url,
            'xsrf_form_html' : self.xsrf_form_html,
            'json_encode': utils.Json.encode,
            'linkify': linkify,
        }
        context.update(self.ui)

        context.update(kwargs)

        template = self.application.jinja_env.get_template(
            template_name,
            parent=self.get_template_path()
        )
        return template.render(**context)

    @session
    def set_current_user(self,session):
        self.session['current_user'] = session

    @session
    def get_current_user(self):
        return self.session.get('current_user', {})

    def get_error_html(self, status_code = 'tip', **kwargs):
        return self.render_string('error/%s.html' % status_code, **kwargs)

    def write_error(self, status_code = 'tip', **kwargs):
        if self.is_ajax() and kwargs.get('msg',False) :
            return self.write({
                'success' : False ,
                'msg' : kwargs.get('msg')
            })
        return super(RequestHandler,self).write_error(status_code, **kwargs)

    # 取运行时间
    def get_run_time(self):
        return round(time.time() - self._start_time , 3)

'''

测试 and 用法
===============

``` sh 

This is ApacheBench, Version 2.3 <$Revision: 655654 $>
Copyright 1996 Adam Twiss, Zeus Technology Ltd, http://www.zeustech.net/
Licensed to The Apache Software Foundation, http://www.apache.org/

Benchmarking 192.168.0.135 (be patient).....done


Server Software:        TornadoServer/3.0.1
Server Hostname:        192.168.0.135
Server Port:            8181

Document Path:          /
Document Length:        0 bytes

Concurrency Level:      10
Time taken for tests:   0.033 seconds
Complete requests:      10
Failed requests:        0
Write errors:           0
Total transferred:      3950 bytes
HTML transferred:       0 bytes
Requests per second:    307.60 [#/sec] (mean)
Time per request:       32.510 [ms] (mean)
Time per request:       3.251 [ms] (mean, across all concurrent requests)
Transfer rate:          118.65 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        1    1   0.4      1       2
Processing:    18   27   5.3     31      31
Waiting:       17   26   5.3     30      31
Total:         19   28   5.3     32      32

Percentage of the requests served within a certain time (ms)
  50%     32
  66%     32
  75%     32
  80%     32
  90%     32
  95%     32
  98%     32
  99%     32
 100%     32 (longest request)

'''
if __name__ == '__main__':
    from tornado.ioloop import IOLoop
    from tornado.httpserver import HTTPServer
    #from tornado.options import parse_command_line
    from tornado.web import asynchronous
    import mopee

    @route(r'/')
    class Handler(RequestHandler):

        @asynchronous
        @session
        def get(self):
            if self.session.get('test2'):
                print self.session['test2'] 
            else:
                self.session['test2'] = {'test': 1233}
                print 'write'
            # 清空
            #self.session = None
            self.finish()

    database = mopee.PostgresqlAsyncDatabase('test',
        user = 'vfasky',
        host = '127.0.0.1',
        password = '19851024',
        size = 20,
    )

    settings = dict(
        debug=True, 
        database=database,
        cache={},
        cookie_secret="fsfwo#@(sfk"
    )
                        
    application = Application([], **settings)

    http_server = HTTPServer(application)
    http_server.listen(8181)
    IOLoop.instance().start()
