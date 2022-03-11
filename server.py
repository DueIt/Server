from flask import Flask, jsonify, request, abort, make_response, g
from decouple import config

import mysql.connector
import sys
import os

import hashlib
import binascii

import jwt

ENDPOINT=config('ENDPOINT')
PORT=config('PORT')
USER=config('DB_USER')
DBNAME=config('DBNAME')
PASSWORD=config('PASSWORD')
SECRET=config('SECRET')

def db_connect():
    try:
        conn =  mysql.connector.connect(host=ENDPOINT, user=USER, passwd=PASSWORD, database=DBNAME)
        return conn
    except Exception as e:
        print("Error: {}".format(e))

def get_db():
    if not hasattr(g, 'db'):
        g.db = db_connect()
    return g.db

def get_jwt_from_id(id):
    encoded_jwt = jwt.encode({'id': id}, SECRET, algorithm="HS256")
    return encoded_jwt

def get_id_from_jwt(encoded_jwt):
    try:
        decoded_jwt = jwt.decode(encoded_jwt, SECRET, algorithms=["HS256"])
        return decoded_jwt['id']
    except Exception as e:
        return None


app = Flask(__name__)

@app.teardown_appcontext
def close_db(_):
    if hasattr(g, 'db'):
        g.db.close()

@app.route('/')
def base():
    return ("This is the DueIt App Server. Welcome!", 200)

@app.route('/test-connection', methods=['GET'])
def test_connection():
    try:
        conn = get_db()
        return ('Connected!', 200)
    except Exception as e:
        return ('Error: {}'.format(e), 500)


@app.route('/sign-up', methods=['POST'])
def sign_up():
    if not request.json or not 'password' in request.json or not 'email' in request.json:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    email = request.json['email']
    password = request.json['password']
    salt = os.urandom(32)
    hash_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    hex_pass = hash_password.hex()
    hex_salt = salt.hex()
    try:
        cur.execute("""INSERT INTO Users (Email, Pass, Salt) VALUES ("{}", "{}", "{}")""".format(email, hex_pass, hex_salt))
        conn.commit()
        cur.execute("""SELECT * FROM Users WHERE Email = "{}" """.format(email))
        query_results = cur.fetchall()
        jwt = get_jwt_from_id(query_results[0][0])
        res_dict = {
            'jwt': jwt
        }
        return make_response(jsonify(res_dict), 200)
    except Exception as e:
        print(e)
        return ('Error: {}'.format(e), 401)

    

@app.route('/sign-in', methods=['POST'])
def sign_in():
    if not request.json or not 'password' in request.json or not 'email' in request.json:
        abort(400)
    conn = get_db()
    cur = conn.cursor()
    email = request.json['email']
    password = request.json['password']
    try:
        cur.execute("""SELECT * FROM Users WHERE Email = "{}" """.format(email))
        query_results = cur.fetchall()
        if not query_results or len(query_results) == 0:
            return('Either your email or password is incorrect.', 401)
        query_results = query_results[0]
        check_salt = bytes.fromhex(query_results[3])
        hash_password = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), check_salt, 100000)
        hex_pass = hash_password.hex()
        if query_results[2] == hex_pass:
            jwt = get_jwt_from_id(query_results[0])
            res_dict = {
                'jwt': jwt
            }
            return make_response(jsonify(res_dict), 200)
        else:
            return('Either your email or password is incorrect.', 401)
    except Exception as e:
        return ('Error: {}'.format(e), 500)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)