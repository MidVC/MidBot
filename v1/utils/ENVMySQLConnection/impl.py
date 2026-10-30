import os
from utils.MySQLConnection import MySQLConnection

class ENVMySQLConnection(MySQLConnection):
    def __init__(self):

        host = os.getenv('MYSQLHOST')
        user = os.getenv('MYSQLUSER')
        password = os.getenv('MYSQLPSWD')
        database = os.getenv('MYSQLDB')

        super().__init__(host, user, password, database)

