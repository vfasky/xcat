#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date: 2013-05-02 17:13:37
# @Author: vfasky (vfasky@gmail.com)
# @Version: $Id$
# peewee for Momoko

__all__ = [
    'BigIntegerField',
    'BlobField',
    'BooleanField',
    'CharField',
    'DateField',
    'DateTimeField',
    'DecimalField',
    'DoubleField',
    'Field',
    'FloatField',
    'fn',
    'ForeignKeyField',
    'IntegerField',
    'TextField',
    'TimeField',
    'PostgresqlAsyncDatabase',
    'WaitAllOps',
    'AsyncModel',
]

'''
Momoko ORM(peewee)
==================

## demo

``` python
import mopee

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.web import asynchronous, RequestHandler, Application

database = mopee.PostgresqlAsyncDatabase('test',
    user = 'vfasky',
    password = '',
    size = 20,
)

database.connect()

class User(mopee.AsyncModel):
    class Meta:
        database = database

    name = mopee.CharField()
    password = mopee.CharField(max_length = 255)

class AsyncHandler(RequestHandler):
    @asynchronous
    @gen.engine
    def get(self):
        # 判断表是否存在
        exists =  yield gen.Task(User.table_exists)
        # 如果不存在，创建表
        if not exists:
            User.create_table()

        # 添加数据    
        user = User(
            name = 'vfasky',
            password = '1233',
        )
        pk = yield gen.Task(user.save)

        # 查询表
        user = yield gen.Task(User.select().where(User.id == pk).get)
        self.write(user.name)

        self.finish()

if __name__ == '__main__':
 
    application = Application([
        (r'/', AsyncHandler),
    ], debug=True)

    http_server = HTTPServer(application)
    http_server.listen(8181, 'localhost')
    IOLoop.instance().start()
```

'''

from tornado import gen
from peewee import PostgresqlDatabase, Query, \
                   SelectQuery, UpdateQuery, InsertQuery, \
                   DeleteQuery, Model, QueryResultWrapper, \
                   RawQuery, DictQueryResultWrapper, \
                   NaiveQueryResultWrapper, \
                   ModelQueryResultWrapper, \
                   ModelAlias, with_metaclass, \
                   BaseModel, CharField, DateTimeField, \
                   DateField, TimeField, DecimalField, \
                   ForeignKeyField, PrimaryKeyField, \
                   TextField, IntegerField, BooleanField, \
                   FloatField, DoubleField, BigIntegerField, \
                   DecimalField, BlobField, fn, Field
import momoko
#import logging
#logger = logging.getLogger('mopee')    

WaitAllOps = momoko.WaitAllOps

class PostgresqlAsyncDatabase(PostgresqlDatabase):
    
    def _connect(self, database, **kwargs):
        return momoko.Pool(
            dsn='dbname=%s user=%s password=%s host=%s port=%s' % (
                database,
                kwargs.get('user'),
                kwargs.get('password'),
                kwargs.get('host', 'localhost'),
                kwargs.get('port', '5432'),
            ),
            size=kwargs.get('size', 10)
        ) 
    
    @gen.engine
    def last_insert_id(self, cursor, model, callback=None):
        seq = model._meta.primary_key.sequence
        if seq:
            sql = "SELECT CURRVAL('\"%s\"')" % (seq)
            cursor = yield momoko.Op(self.get_conn().execute, sql)
            callback(cursor.fetchone()[0])
            return
        elif model._meta.auto_increment:
            sql = "SELECT CURRVAL('\"%s_%s_seq\"')" % (
                  model._meta.db_table, model._meta.primary_key.db_column)
            cursor = yield momoko.Op(self.get_conn().execute, sql)
            callback(cursor.fetchone()[0])
            return

        callback(None)
        return

    def create_table(self, model_class, safe=False, callback=None):
        qc = self.compiler()
        return self.execute_sql(qc.create_table(model_class, safe), callback=callback)

    def create_index(self, model_class, fields, unique=False, callback=None):
        qc = self.compiler()
        if not isinstance(fields, (list, tuple)):
            raise ValueError('fields passed to "create_index" must be a list or tuple: "%s"' % fields)
        field_objs = [model_class._meta.fields[f] if isinstance(f, basestring) else f for f in fields]
        return self.execute_sql(qc.create_index(model_class, field_objs, unique), callback=callback)

    def create_foreign_key(self, model_class, field, callback=None):
        if not field.primary_key:
            return self.create_index(model_class, [field], field.unique, callback=callback)

    def create_sequence(self, seq, callback=None):
        if self.sequences:
            qc = self.compiler()
            return self.execute_sql(qc.create_sequence(seq), callback=callback)

    def drop_table(self, model_class, fail_silently=False, callback=None):
        qc = self.compiler()
        return self.execute_sql(qc.drop_table(model_class, fail_silently), callback=callback)

    def drop_sequence(self, seq, callback=None):
        if self.sequences:
            qc = self.compiler()
            return self.execute_sql(qc.drop_sequence(seq), callback=callback)



    def rows_affected(self, cursor):
        return cursor.rowcount


    def get_indexes_for_table(self, table, callback=None):
        def _callback(res):
            callback(sorted([(r[0], r[1]) for r in res.fetchall()]))

        self.execute_sql("""
            SELECT c2.relname, i.indisprimary, i.indisunique
            FROM pg_catalog.pg_class c, pg_catalog.pg_class c2, pg_catalog.pg_index i
            WHERE c.relname = %s AND c.oid = i.indrelid AND i.indexrelid = c2.oid
            ORDER BY i.indisprimary DESC, i.indisunique DESC, c2.relname""", (table,), callback=_callback)
       
    @gen.engine
    def execute_sql(self, sql, params=None, require_commit=True, callback=None):
        params = params or ()
        if require_commit and self.get_autocommit():
            cursors = yield momoko.Op(self.get_conn().transaction, [(sql, params)])
            for i, cursor in enumerate(cursors):
                pass
        else:
            cursor = yield momoko.Op(self.get_conn().execute, sql, params )
        
        if callback and cursor:
            #print cursor
            callback(cursor)
     
    def get_tables(self, callback=None):
        def _callback(res):
            if callback:
                callback([row[0] for row in res.fetchall()])

        self.execute_sql("""
            SELECT c.relname
            FROM pg_catalog.pg_class c
            LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'v', '')
                AND n.nspname NOT IN ('pg_catalog', 'pg_toast')
                AND pg_catalog.pg_table_is_visible(c.oid)
            ORDER BY c.relname""", callback=_callback)

    def sequence_exists(self, sequence, callback=None):
        def _callback(res):
            callback(bool(res.fetchone()[0]))

        self.execute_sql("""
            SELECT COUNT(*)
            FROM pg_class, pg_namespace
            WHERE relkind='S'
                AND pg_class.relnamespace = pg_namespace.oid
                AND relname=%s""", (sequence,), callback=_callback)
    
    def set_search_path(self, *search_path):
        path_params = ','.join(['%s'] * len(search_path))
        self.execute_sql('SET search_path TO %s' % path_params, search_path)

class AsyncQuery(Query):
    def _execute(self, callback=None):
        sql, params = self.sql()
        return self.database.execute_sql(sql, params, self.require_commit, callback=callback)

class AsyncUpdateQuery(UpdateQuery):
    def _execute(self, callback=None):
        sql, params = self.sql()
        return self.database.execute_sql(sql, params, self.require_commit, callback=callback)

    def execute(self, callback=None):
        def _callback(cursor):
            ret = self.database.rows_affected(cursor)
            callback(ret)
        self._execute(callback=_callback)

class AsyncDeleteQuery(DeleteQuery):
    def _execute(self, callback=None):
        sql, params = self.sql()
        return self.database.execute_sql(sql, params, self.require_commit, callback=callback)

    def execute(self, callback=None):
        def _callback(cursor):
            callback(self.database.rows_affected(cursor))
        self._execute(callback=_callback)

class AsyncInsertQuery(InsertQuery):
    def _execute(self, callback=None):
        sql, params = self.sql()
        return self.database.execute_sql(sql, params, self.require_commit, callback=callback)

    def execute(self, callback=None):
        def _callback(cursor):
            self.database.last_insert_id(cursor, self.model_class, callback)
        self._execute(callback=_callback)


class AsyncRawQuery(RawQuery):
    def _execute(self, callback=None):
        sql, params = self.sql()
        return self.database.execute_sql(sql, params, self.require_commit, callback=callback)

    def execute(self, callback=None):
        if self._qr is None:
            if self._tuples:
                ResultWrapper = QueryResultWrapper
            elif self._dicts:
                ResultWrapper = DictQueryResultWrapper
            else:
                ResultWrapper = NaiveQueryResultWrapper
            
            def _callback(cursor):
                self._qr = ResultWrapper(self.model_class, cursor, None)
                callback(self._qr)

            self._execute(callback=_callback)
        else:
            callback(self._qr)

    def scalar(self, as_tuple=False, callback=None):
        def _callback(cursor):
            row = cursor.fetchone()
            if row and not as_tuple:
                row = row[0]
            callback(row)
        self._execute(callback=_callback)


class AsyncSelectQuery(SelectQuery):
    def _execute(self, callback=None):
        sql, params = self.sql()
        self.database.execute_sql(sql, params, self.require_commit, callback=callback)

    def scalar(self, as_tuple=False, callback=None):
        def _callback(cursor):
            row = cursor.fetchone()
            if row and not as_tuple:
                row = row[0]
            callback(row)
        self._execute(callback=_callback)

    def execute(self, callback=None):
        if self._dirty or not self._qr:
            query_meta = None
            if self._tuples:
                ResultWrapper = QueryResultWrapper
            elif self._dicts:
                ResultWrapper = DictQueryResultWrapper
            elif self._naive or not self._joins or self.verify_naive():
                ResultWrapper = NaiveQueryResultWrapper
            else:
                query_meta = [self._select, self._joins]
                ResultWrapper = ModelQueryResultWrapper
            
            def _callback(cursor):
                self._qr = ResultWrapper(self.model_class, cursor, query_meta)
                self._dirty = False
                callback(self._qr)

            self._execute(callback=_callback)
        else:
            callback(self._qr)

    def wrapped_count(self, callback=None):
        clone = self.order_by()
        clone._limit = clone._offset = None

        sql, params = clone.sql()
        wrapped = 'SELECT COUNT(1) FROM (%s) AS wrapped_select' % sql
        rq = AsyncRawQuery(self.model_class, wrapped, *params)

        def _callback(row):
            callback(row or 0)

        rq.scalar(callback=_callback)

    def aggregate(self, aggregation=None, callback=None):
        return self._aggregate(aggregation).scalar(callback=callback)

    def count(self, callback=None):
        def _callback(row):
            callback(row or 0)

        if self._distinct or self._group_by:
            return self.wrapped_count(callback=_callback)

        # defaults to a count() of the primary key
        return self.aggregate(callback=_callback)

    def exists(self, callback=None):
        clone = self.paginate(1, 1)
        clone._select = [self.model_class._meta.primary_key]
        def _callback(row):
            callback(bool(row))
            
        clone.scalar(callback=_callback)

    @gen.engine
    def first(self, callback=None):
        res = yield gen.Task(self.execut)
        res.fill_cache(1)
        try:
            if callback:
                callback(res._result_cache[0])
            return 
        except IndexError:
            pass
        if callback:
            callback(None)
        

    @gen.engine
    def get(self, callback=None):
        clone = self.paginate(1, 1)

        try:
            cursor = yield gen.Task(clone.execute)
            if callback:
                callback(cursor.next())
        except StopIteration:
            raise self.model_class.DoesNotExist('instance matching query does not exist:\nSQL: %s\nPARAMS: %s' % (
                self.sql()
            ))
    
class AsyncModel(Model):

    @classmethod
    def select(cls, *selection):
        query = AsyncSelectQuery(cls, *selection)
        if cls._meta.order_by:
            query = query.order_by(*cls._meta.order_by)
        return query

    @classmethod
    def update(cls, **update):
        fdict = dict((cls._meta.fields[f], v) for f, v in update.items())
        return AsyncUpdateQuery(cls, fdict)

    @classmethod
    def insert(cls, **insert):
        fdict = dict((cls._meta.fields[f], v) for f, v in insert.items())
        return AsyncInsertQuery(cls, fdict)

    @classmethod
    def delete(cls):
        return AsyncDeleteQuery(cls)

    @classmethod
    def raw(cls, sql, *params):
        return AsyncRawQuery(cls, sql, *params)

    @classmethod
    def create(cls, **query):
        callback = query.pop('callback', None)
        
        inst = cls(**query)
        inst.save(force_insert=True, callback=callback)
       

    # @classmethod
    # def get(cls, *query, **kwargs):
    #     sq = cls.select().naive()
    #     if query:
    #         sq = sq.where(*query)
    #     if kwargs:
    #         sq = sq.filter(**kwargs)
    #     return sq.get

    @classmethod
    def get_or_create(cls, **kwargs):
        callback = kwargs.pop('callback', None)

        sq = cls.select().filter(**kwargs)
        try:
            return sq.get(callback=callback)
        except cls.DoesNotExist:
            return cls.create(callback=callback, **kwargs)


    @classmethod
    @gen.engine
    def table_exists(cls, callback=None):
    
        tables = yield gen.Task(cls._meta.database.get_tables)

        if callback:
            callback(cls._meta.db_table in tables)

    @classmethod
    @gen.engine
    def create_table(cls, fail_silently=False, callback=None):

        # yiele
        exists = yield gen.Task(cls.table_exists)
        if fail_silently and exists:
            return

        db = cls._meta.database
        pk = cls._meta.primary_key
        if db.sequences and pk.sequence and not db.sequence_exists(pk.sequence):
            db.create_sequence(pk.sequence)

        cursor = yield gen.Task(db.create_table, cls)

        for field_name, field_obj in cls._meta.fields.items():
            if isinstance(field_obj, ForeignKeyField):
                yield gen.Task(db.create_foreign_key, cls, field_obj)
            elif field_obj.index or field_obj.unique:
                yield gen.Task(db.create_index, cls, [field_obj], field_obj.unique)
      
        if cls._meta.indexes:
            for fields, unique in cls._meta.indexes:
                count = count + 1
                yield gen.Task(db.create_index, cls, fields, unique)
        
        if callback:
            callback(cursor)
        

    @classmethod
    def drop_table(cls, fail_silently=False, callback=None):
        cls._meta.database.drop_table(cls, fail_silently, callback=callback)

    @gen.engine
    def save(self, force_insert=False, only=None, callback=None):
        field_dict = dict(self._data)
        pk = self._meta.primary_key
        if only:
            field_dict = self._prune_fields(field_dict, only)
        
        if self.get_id() is not None and not force_insert:
            field_dict.pop(pk.name, None)
            update = self.update(
                **field_dict
            ).where(pk == self.get_id())

            yield gen.Task(update.execute)
            if callback:
                callback(self.get_id())

        else:
            if self._meta.auto_increment:
                field_dict.pop(pk.name, None)
            insert = self.insert(**field_dict)
            
            new_pk = yield gen.Task(insert.execute)
            if self._meta.auto_increment:
                self.set_id(new_pk)

            if callback:
                callback(new_pk)
            
        
    @gen.engine
    def delete_instance(self, recursive=False, delete_nullable=False, callback=None):
        if recursive:
            for query, fk in reversed(list(self.dependencies(delete_nullable))):
                if fk.null and not delete_nullable:
                    yield genTask(fk.model_class.update(**{fk.name: None}).where(query).execute)
                else:
                    yield genTask(fk.model_class.delete().where(query).execute)
        yield genTask(self.delete().where(self._meta.primary_key == self.get_id()).execute)
        
        if callback:
            callback()

# test
if __name__ == '__main__':
    from tornado import gen
    from tornado.ioloop import IOLoop
    from tornado.httpserver import HTTPServer
    from tornado.web import asynchronous, RequestHandler, Application

    database = PostgresqlAsyncDatabase('test',
        user = 'vfasky',
        host = '127.0.0.1',
        password = '19851024',
        size = 20,
    )

    class User(AsyncModel):
        class Meta:
            database = database

        name = CharField()
        password = CharField(max_length = 255)

    database.connect()


    class AsyncHandler(RequestHandler):
        @asynchronous
        @gen.engine
        def get(self):
            exists =  yield gen.Task(User.table_exists)
            if not exists:
                yield gen.Task(User.create_table)

            # add
            user = User()
            user.name = 'test3'
            user.password = '5677'
            
            yield gen.Task(user.save)
            print user.id
            
            # edit
            user = yield gen.Task(User.get(User.id == 9))
            user.name = 'test03'
            ret = yield gen.Task(user.save)
            print ret

            # count
            count = yield gen.Task(User.select(User.name).where(User.name == 'test03').count)
            print count 

            # delete
            ret = yield gen.Task(User.delete().where(User.name % 'test%').execute)
            print ret 

            # user = yield gen.Task(User.select().where(User.name == 'wing').get)
            # self.write(user.name)
            self.finish()

    application = Application([
        (r'/', AsyncHandler),
    ], debug=True)

    http_server = HTTPServer(application)
    http_server.listen(8181)
    IOLoop.instance().start()
