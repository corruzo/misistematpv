import os
import pyodbc

server = os.getenv('DB_SERVER', 'localhost')
db = os.getenv('DB_NAME', 'misistema_db')
user = os.getenv('DB_USER', '')
pwd = os.getenv('DB_PASSWORD', '')
trusted = os.getenv('DB_TRUSTED', 'false').lower() in ('1','true','yes')

def test_conn():
    if trusted or not user:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={db};Trusted_Connection=yes"
    else:
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={db};UID={user};PWD={pwd}"
    print('Trying:', conn_str)
    try:
        cn = pyodbc.connect(conn_str, timeout=5)
        print('Connection OK')
        cn.close()
    except Exception as e:
        print('Connection ERROR:', e)

if __name__ == '__main__':
    test_conn()
