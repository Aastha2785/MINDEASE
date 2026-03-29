import mysql.connector
import pymysql
def get_connection():

    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="aastha@2785gupta",
        database="mindEase",
        cursorclass=pymysql.cursors.DictCursor
    )

    return conn