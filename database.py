import sqlite3
from typing import NamedTuple


class DataBase():

    def __init__(self, db_name="base.db", *args):
        self.db_name = db_name

    def __enter__(self, *args):
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        return self

    def __exit__(self, *args):
        self.conn.close()

    def fetchone(self, query: str, args=()):
        self.cursor.execute(query, args)
        return self.cursor.fetchone()

    def fetchall(self, query: str, args=()):
        self.cursor.execute(query, args)
        return self.cursor.fetchall()

    def update(self, query: str, args=()) -> bool:
        self.cursor.execute(query, args)
        self.conn.commit()
        return True


class FactoryDateBase(DataBase):
    
    @staticmethod
    def __namedtuple_factory(cursor, row):
        fields = [(str(col[0]).lower(), str) for col in cursor.description]
        Row = NamedTuple("Row", fields)
        return Row(*row)
    
    def __enter__(self, *args):
        self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
        self.conn.row_factory = self.__namedtuple_factory
        self.cursor = self.conn.cursor()
        return self