#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2013-05-29 15:08:04
# @Author  : vfasky (vfasky@gmail.com)
# @Link    : http://vfasky.com
# @Version : $Id$

__all__ = [
    'validators',
    'fields',
    'ValidationError',
    'Form',
]

from tforms import validators, fields, validators
from tforms.forms import TornadoForm as Form
from tforms.validators import ValidationError


if __name__ == '__main__':
    class SignupForm(Form):
        username = fields.TextField(
            'Username', [
                validators.Required(),
                validators.Length(min=4, max=16),
                validators.Regexp(
                    '[a-zA-Z0-9-]',
                    message='Username can only contain characters and digits',
                ),
            ],
            description='Username can only contain English characters and digits'
        )
        email = fields.TextField(
            'Email', [
                validators.Required(),
                validators.Length(min=4, max=30),
                validators.Email(),
            ],
            description='Please active your account after registration'
        )
        password = fields.PasswordField(
            'Password', [
                validators.Required(),
                validators.Length(min=6),
            ],
            description='Password must be longer than 6 characters'
        )
        password2 = fields.PasswordField(
            'Confirm', [
                validators.Required(),
                validators.Length(min=6),
            ]
        )

        def validate_password(form, field):
            if field.data != form.password2.data:
                raise ValidationError("Passwords don't match")
    
    form = SignupForm()
    for field in form:
        print field

    