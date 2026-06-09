import psycopg2
import sys

try:
    # Trying to connect without PGCLIENTENCODING=UTF8
    psycopg2.connect("postgresql://postgres:admin123@localhost:5432/smart_balance")
    print("Connection successful!")
except Exception as e:
    print(f"Error type: {type(e)}")
    print(f"Error args: {e.args}")
