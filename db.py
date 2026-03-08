import pymssql
import os

conn = pymssql.connect(
    server=os.environ["DB_SERVER"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    charset="UTF-8"
)

def get_connection():
    return conn
