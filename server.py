from __future__ import print_function
from flask import Flask, jsonify, request, abort, make_response, g
from decouple import config
import mysql.connector
import sys
import os
import copy
import hashlib
import binascii
import jwt


import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

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


@app.route('/get-tasks', methods=['GET'])
def get_tasks():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""SELECT * FROM Tasks WHERE UserID = "{}" """.format(id))
            query_results = cur.fetchall()
            res_list = []
            task = {}
            for i in range(len(query_results)):
                task = {
                    'task_id' : query_results[i][0],
                    'title' : query_results[i][1],
                    'total_time' : query_results[i][2],
                    'remaining_time' : query_results[i][3],
                    'due_date' : query_results[i][4],
                    'importance' : query_results[i][5],
                    'difficulty' : query_results[i][6],
                    'location' : query_results[i][7]
                }
                res_list.append(copy.deepcopy(task))
                task.clear()
                json_return = {
                    'tasks' : res_list
                }
            return make_response(jsonify(json_return), 200)
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(401)


@app.route('/remove-tasks/<task_id>', methods=['DELETE'])
def remove_tasks(task_id):
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""DELETE FROM Tasks where TaskID = "{}" """.format(task_id))
            conn.commit()
            return {'status' : 200}
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)

@app.route('/getrecentevents', methods=['GET'])
def getgooglecalevents():
    # jwt = request.headers['Token']
    # id = get_id_from_jwt(jwt)
    # if id:
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None

    cur.execute("""SELECT * FROM GoogleOauth WHERE UserID = "{}" """.format(id))
    query_results = cur.fetchall()
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentialsoauth.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                            maxResults=10, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
            return

        # Prints the start and name of the next 10 events
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

    except HttpError as error:
        print('An error occurred: %s' % error)

    return {'status' : 200}

@app.route('/getcalendarlist', methods=['GET'])
def get_cal_list():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        print(id)
        creds = None
        try:
            cur.execute("""SELECT * FROM GoogleOauth WHERE UserID = "{}" """.format(id))
            query_results = cur.fetchall()
            if len(query_results) > 0:
                for i in range(len(query_results)):
                    tokenJson = {
                        'token' : query_results[i][1],
                        'refresh_token' : query_results[i][2],
                        'token_uri' : query_results[i][3],
                        'client_id' : query_results[i][4],
                        'client_secret' : query_results[i][5],
                        'scopes' : query_results[i][6],
                        'expiry' : query_results[i][7]
                    }
                    # what to do with this?
                    creds = Credentials.from_authorized_user_info(tokenJson, SCOPES)
                    tokenJson.clear()
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'credentialsoauth.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                credsJson = creds.to_json()
                cur.execute("""INSERT INTO GoogleOauth (UserID, token, refresh_token, token_uri, client_id, client_secret, scopes, expiry) VALUES ("{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}")""".format(id, credsJson['token'], credsJson['refresh_token'],credsJson['token_uri'], credsJson['client_id'], credsJson['client_secret'], credsJson['scopes'], credsJson['expiry']))
                conn.commit()
        except Exception as e:
            print(e)
            return ('Error: {}'.format(e), 401)

        try:
            service = build('calendar', 'v3', credentials=creds)

            # Call the Calendar API
            now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            print('Getting your calendars')

            calendar_list = service.calendarList().list().execute()
            cal_list = calendar_list.get('items', [])

            if not cal_list:
                print('No calendars found.')
                return

            res_list = []
            for cal in cal_list:
                # print(cal)
                print(cal['summary'], cal['id'])
                cal = {
                        'cal_id' : cal['id'],
                        'summary' : cal['summary'],
                }
                res_list.append(copy.deepcopy(cal))
                cal.clear()
                json_return = {
                    'calendars' : res_list
                }
            return make_response(jsonify(json_return), 200)

        except HttpError as error:
            print('An error occurred: %s' % error)

        # return {'status' : 200}
    else:
        abort(400)

@app.route('/add-tasks', methods=['POST'])
def add_tasks():
    if (not request.json or not 'title' in request.json
        or not 'total_time' in request.json
        or not 'remaining_time' in request.json
        or not 'due_date' in request.json
        or not 'importance' in request.json
        or not 'difficulty' in request.json
        or not 'location' in request.json):
        abort(400)
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        Title = request.json['title']
        TotalTime = request.json['total_time']
        RemainingTime = request.json['remaining_time']
        DueDate = request.json['due_date']
        Importance = request.json['importance']
        Difficulty = request.json['difficulty']
        Location = request.json['location']
        try:
            cur.execute("""INSERT INTO Tasks (Title, TotalTime, RemainingTime, DueDate, Importance, Difficulty, Location, UserID)
                VALUES ("{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}")""".format(Title, TotalTime, RemainingTime, DueDate, Importance, Difficulty, Location, id))
            conn.commit()

            return {'status' : 200}
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)

@app.route('/get-calendar', methods=['GET'])
def get_calendar():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""SELECT * FROM Calendars WHERE UserID = "{}" """.format(id))
            query_results = cur.fetchall()
            res_list = []
            calendar = {}
            for i in range(len(query_results)):
                calendar = {
                    'calendar_id' : query_results[i][0],
                    'ref_id' : query_results[i][1],
                    'user_id' : query_results[i][2]
                }
                res_list.append(copy.deepcopy(calendar))
                calendar.clear()
            json_return = {
                'calendars' : res_list
            }
            return make_response(jsonify(json_return), 200)
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)

@app.route('/add-calendar', methods=['POST'])
def add_calendar():
    if not request.json or not 'ref_id' in request.json:
        abort(400)
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        RefID = request.json['ref_id']
        try:
            cur.execute("""INSERT INTO Calendars (RefID,UserID)
                VALUES ("{}", "{}")""".format(RefID, id))
            conn.commit()
            return {'status' : 200}
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)

@app.route('/update-time/<task_id>', methods=['POST'])
def update_time(task_id) :
    if not request.json or not 'remaining_time' in request.json:
        abort(400)
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        RemainingTime = request.json['remaining_time']
        try:
            cur.execute("""UPDATE Tasks SET RemainingTime = "{}" WHERE TaskID = "{}" """.format(RemainingTime, task_id))
            conn.commit()
            return {'status' : 200}
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
