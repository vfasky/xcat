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
]

import functools
import session as Xsession
import utils
from tornado.web import url, RequestHandler

def session(method):
    '''
    异步 session 的绑定
    '''

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        settings = self.settings.get('session', {})
        session_name = settings.get('name', 'PYSESSID')
        session_storage = settings.get('storage', 'Mongod')
        session_config  = settings.get('config', {})

        if hasattr(Xsession, session_storage):
            Session = getattr(Xsession, session_storage)

            if self.get_secure_cookie(session_name):
                self._session = Session(self.get_secure_cookie(session_name), **session_config)
            else:
                session = Session(**session_config)
                self.set_secure_cookie(key , session.id)
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

        for r in rules:
            if r['URI'] == URI:
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

        handler_class.routes.append({
            'name': name ,
            'spec': spec
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
        if item not in cls._routes['.*$'] :
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


'''
测试 and 用法
'''
if __name__ == '__main__':
    from tornado.ioloop import IOLoop
    from tornado.httpserver import HTTPServer
    #from tornado.options import parse_command_line
    from tornado.web import asynchronous, RequestHandler, Application

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
                        
   
    application = Application([
        (r'/', Handler),
    ], debug=True, 
    cookie_secret="fsfwo#@(sfk")

    http_server = HTTPServer(application)
    http_server.listen(8181)
    IOLoop.instance().start()
