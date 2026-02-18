import pymssql
import os

def get_connection():
    return pymssql.connect(
        server="voting01.database.windows.net",
        user=os.environ["Julphar_Admin"],
        password=os.environ["Bashayer01"],
        database="Voting"
    )
