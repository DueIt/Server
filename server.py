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
import json
from datetime import datetime, timedelta, timezone
import time
import itertools
import pytz

from schedule import schedule, datetime_from_utc_to_local
from task import Task
from ga import Cluster, GA

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

def get_google_token(id):
    conn = get_db()
    cur = conn.cursor()
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
                temp = creds.to_json()
                credsJson1 = json.loads(temp)
                cur.execute("""UPDATE GoogleOauth 
                SET 
                token = "{}", 
                refresh_token = "{}", 
                token_uri = "{}", 
                client_id = "{}", 
                client_secret = "{}", 
                scopes = "{}", 
                expiry = "{}" WHERE UserID = "{}" """.format(credsJson1['token'], credsJson1['refresh_token'],credsJson1['token_uri'], credsJson1['client_id'], credsJson1['client_secret'], credsJson1['scopes'], credsJson1['expiry'], id))
                conn.commit()
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentialsoauth.json', SCOPES)
                creds = flow.run_local_server(port=0)
                temp = creds.to_json()
                credsJson = json.loads(temp)
                cur.execute("""INSERT INTO GoogleOauth (UserID, token, refresh_token, token_uri, client_id, client_secret, scopes, expiry) VALUES ("{}", "{}", "{}", "{}", "{}", "{}", "{}", "{}")""".format(id, credsJson['token'], credsJson['refresh_token'],credsJson['token_uri'], credsJson['client_id'], credsJson['client_secret'], credsJson['scopes'], credsJson['expiry']))
                conn.commit()
        return creds
    except Exception as e:
        print(e)
        return ('Error: {}'.format(e), 401)

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


def get_task_request(id):
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
        return (True, json_return)
    except Exception as e:
        return (False, e)

@app.route('/get-tasks', methods=['GET'])
def get_tasks():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        res = get_task_request(id)
        if res[0]:
            return make_response(jsonify(res[1]), 200)
        else:
            return ('Error: {}'.format(res[1]), 500)
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

@app.route('/get-recent-events', methods=['GET'])
def getgooglecalevents():
    jwt = request.headers['Token']
    calID = request.headers['CalID']
    id = get_id_from_jwt(jwt)
    if id:
        creds = get_google_token(id)
        ev_list = []
        try:
            service = build('calendar', 'v3', credentials=creds)

            # Call the Calendar API
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            aWeekFromNow = (datetime.utcnow() + datetime.timedelta(days=7)).isoformat() + 'Z'
            print(now, aWeekFromNow)
            events_result = service.events().list(calendarId=calID, timeMin=now,
                                                timeMax=aWeekFromNow, singleEvents=True,
                                                orderBy='startTime').execute()
            events = events_result.get('items', [])

            if not events:
                print('No upcoming events found.')
                json_return = {
                    'events' : ev_list
                }
                return make_response(jsonify(json_return), 200)

            # Prints the start and name of the next 10 events
            
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                ev = {
                        'event_id' : event['etag'],
                        'summary' : event['summary'],
                        'start_time': start,
                }
                ev_list.append(copy.deepcopy(ev))
                ev.clear()
                json_return = {
                    'events' : ev_list
                }
            print(ev_list)
            return make_response(jsonify(json_return), 200)
                

        except HttpError as error:
            print('An error occurred: %s' % error)

    else:
        abort(400)

@app.route('/getcalendarlist', methods=['GET'])
def get_cal_list():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        creds = get_google_token(id)
        try:
            service = build('calendar', 'v3', credentials=creds)

            # Call the Calendar API
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
                    'user_id' : query_results[i][2],
                    'type_id' : query_results[i][3],
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

@app.route('/get-apple-calendars', methods=['GET'])
def get_apple_calendars():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""SELECT * FROM Calendars WHERE UserID = "{}" AND TypeID = 0""".format(id))
            query_results = cur.fetchall()
            res_list = []
            for i in range(len(query_results)):
                res_list.append(query_results[i][1])
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
    if not request.json or not 'ref_id' in request.json or not 'cal_type' in request.json:
        abort(400)
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        RefID = request.json['ref_id']
        CalType = request.json['cal_type']
        try:
            cur.execute("""INSERT INTO Calendars (RefID,UserID,TypeID)
                VALUES ("{}", "{}", {})""".format(RefID, id, CalType))
            conn.commit()
            return {'status' : 200}
        except mysql.connector.Error as err:
            if err.errno == 1062:
                return {'status': 200, }
            return ('Error: {}'.format(err), 500)
    else:
        abort(400)


@app.route('/get-events', methods=['GET'])
def get_events():
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""SELECT * FROM Calendars WHERE UserID = "{}" AND TypeID = 0""".format(id))
            query_results = cur.fetchall()
            res_list = []
            for i in range(len(query_results)):
                res_list.append(query_results[i][1])
            json_return = {
                'AppleCalendarIDs' : res_list
            }
            
            cur.execute("""SELECT * FROM Calendars WHERE UserID = "{}" AND TypeID = 1""".format(id))
            query_results = cur.fetchall()
            google_events = []
            res_list = []
            for i in range(len(query_results)):
                calID = query_results[i][1]
                events = get_google_events(id, calID)
                if len(events) > 0:
                    google_events = google_events + events
            json_return["GoogleEvents"] = google_events
            return make_response(jsonify(json_return), 200)
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)


def get_google_events(id, calID):

    creds = get_google_token(id)
    ev_list = []

    try:
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        aWeekFromNow = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
        # print(now, aWeekFromNow)
        events_result = service.events().list(calendarId=calID, timeMin=now,
                                            timeMax=aWeekFromNow, singleEvents=True,
                                            orderBy='startTime').execute()
        events = events_result.get('items', [])
        if events:
        
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start =  datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z').astimezone(pytz.utc)
                end = event['end'].get('dateTime', event['end'].get('date'))
                end =  datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z').astimezone(pytz.utc)
                ev = {
                        'title' : event['summary'],
                        'start': start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        'end': end.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                }
                ev_list.append(copy.deepcopy(ev))
                ev.clear()
        return ev_list

    except HttpError as error:
        print("WTF:", error)
        return []


@app.route('/generate-schedule', methods=['POST'])
def generate_schedule():
    if not request.json or not 'startDate' in request.json:
        abort(400)

    # All events combined
    events = []

    # Apple Calendar events
    if 'events' in request.json:
        events = request.json['events']

    # Google Calendar events
    jwt = request.headers['Token']
    id = get_id_from_jwt(jwt)
    if id:
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute("""SELECT * FROM Calendars WHERE UserID = "{}" AND TypeID = 1""".format(id))
            query_results = cur.fetchall()
            google_events = []
            res_list = []
            for i in range(len(query_results)):
                calID = query_results[i][1]
                events = get_google_events(id, calID)
                if len(events) > 0:
                    google_events = google_events + events
            events = events + google_events
        except Exception as e:
            return ('Error: {}'.format(e), 500)
    else:
        abort(400)
    
    # Get the tasks
    tasks = []
    if id:
        res = get_task_request(id)
        if res[0]:
            tasks = res[1]["tasks"]
        else:
            return ('Error: {}'.format(res[1]), 500)
    else:
        abort(400)

    # Generate schedule
    def event_string_to_date(windows):
        date_windows = []
        for window in windows:
            date_windows.append(
                (datetime.strptime(window['start'], "%Y-%m-%dT%H:%M:%S.%fZ"),
                datetime.strptime(window['end'], "%Y-%m-%dT%H:%M:%S.%fZ"))
            )
        return date_windows
    processed_events = event_string_to_date(events)
    startDate = datetime.strptime(request.json['startDate'], "%Y-%m-%dT%H:%M:%S.%fZ")

    # TODO: Use the user working hours here instead of hard coded hours
    cal = schedule(processed_events, startDate, ["14:00", "22:00"])

    processed_tasks = []
    for task in tasks:
        new_task = Task(
            task["task_id"],
            task["title"],
            task["total_time"],
            task["importance"],
            task["difficulty"],
            task["due_date"],
        )
        processed_tasks.append(new_task)

    ga = GA(cal, processed_tasks)
    res = ga.optimize(max_iteraions=1000)
    if not res:
        return ('No Tasks to schedule!', 200) 
    task_dicts = []
    for task in res[0].tasks:
        task_dicts = task_dicts + task.to_json()

    json_return = {
        'quality': res[1],
        'tasks': task_dicts
    }
    response = make_response(jsonify(json_return), 200)
    response.headers["Content-Type"] = "application/json"
    return response



@app.route('/update-time/<task_id>', methods=['POST'])
def update_time(task_id):
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
