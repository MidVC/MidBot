import pymysql
import os


dbHost = os.getenv('MYSQLHOST')
dbUser = os.getenv('MYSQLUSER')
dbPswd = os.getenv('MYSQLPSWD')
dbName = os.getenv('MYSQLDB')


connection = pymysql.connect(
    host = dbHost,
    user = dbUser,
    password = dbPswd,
    database = dbName
)

def getData(tableName: str, keyName):
    return None

def closeConnection():
    connection.close()
    print('MySQL connection closed')
