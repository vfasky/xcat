#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2013-08-23 16:47:02
# @Author  : vfasky (vfasky@gmail.com)
# @Link    : http://vfasky.com
# @Version : $Id$

'''
框架全局配置文件的读写
'''
__all__ = [
    'load',
    'set',
    'get',
]

import copy

_config = {
    'run_mode': 'devel',
    'acls': [], 
    'login_url': '/login',
    'version': '1.0.0', 
    'app_path': '',
    'root_path': '',
    'static_path': '',
    'template_path': '',
    'locale_path': '',
    'debug': True,
    'gzip': True,
    'cookie_secret': 'this-Xcat-app',
    'xsrf_cookies': True,  
    'autoescape': None,
    'sync_key': 'xcat.web.Application.id',
    'devel': {
        'database': None,
        'session': None,
        'cache': None,   
    },
    'deploy': {
        'database': None,
        'session': None,
        'cache': None,   
    },
}
# 运行模式类型
_model_type = ('devel', 'deploy')
# 当前运行模式
_run_mode = 'devel'

# 设置配置
def load(config):
    global _config, _run_mode

    if config.has_key('run_mode')\
    and config['run_mode'] in _model_type\
    and config.has_key(config['run_mode']):
        _run_mode = config['run_mode']
        _evn_cfg = copy.copy(_config[_run_mode])
        _evn_cfg.update(config[_run_mode])
        
        _config.update(config)
        _config.update(_evn_cfg)
    else:
        raise NameError, 'config syntax'

# 设置配置
def set(key, value):
    global _config
    _config[key] = value

# 设置配置
def get(key=None, default=None):
    if None == key:
        return _config
    elif _config.has_key(key):
        return _config[key]
    elif _config[_run_mode].has_key(key):
        return _config[_run_mode].has_key(key)
    return default

# 测试
if __name__ == '__main__':
    set({
        'static_path' : 'test',
        'run_mode': 'devel',
        'devel': {
            'test' : 'ok?'
        }
    })
    print get()
    print '======'
    print get('test')