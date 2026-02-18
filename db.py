import pymssql
import os

def get_connection():
    return pymssql.connect(
        server=os.environ["DB_SERVER"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"]
    )
