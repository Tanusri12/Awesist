import psycopg2
from psycopg2.pool import SimpleConnectionPool

from repositories.db_config import DB_CONFIG


# --------------------------------------------------
# Connection Pool
# --------------------------------------------------

connection_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    **DB_CONFIG
)


# --------------------------------------------------
# Get Connection
# --------------------------------------------------

def get_connection():
    return connection_pool.getconn()


# --------------------------------------------------
# Return Connection
# --------------------------------------------------

def release_connection(conn):
    connection_pool.putconn(conn)