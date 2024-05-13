import pymysql
import os

class MySQLConnection:
    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
    
    def connect(self) -> None:
        try:
            self.connection = pymysql.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print("Connection successfully established")
        except Exception as e:
            print(f"An error occured while connecting to the database: {e}")
    
    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None
            print(f"Successfully disconnected database: {self.database}")
        else:
            print(f"There is no current connection to database: {self.database}")

    def query(self, query: str) -> tuple[tuple] | None:
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                result = cursor.fetchall()
                return result
        
        except Exception as e:
            print(f"An error occured while executing the query: {e}")
            return None
