
import psycopg2


def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="Bugflow",
        user="postgres",
        password="3041",
        port="5432"
    )
