from db_connect import *
from db_access import *
from secure import *
from game_master import *
#from send_email import *



from flask import Flask, jsonify, make_response, redirect, url_for, request
from flask_cors import CORS
#import threading # Cloud Run automatically increases container instances
# import os # imported in db_connect



app = Flask(__name__)
CORS(app) # enable CORS on all domains




# on scheduler call launch games master to run chess bot games
@app.route("/rungames", methods=["POST"]) # POST
def game_master_run_games():
    """
    Launches chess game master and runs games, uploads player and match data into db
    Receives -> launch_key and launches if validated against secret
    Returns -> nothing
    """
    launch_status = "NOT OK"

    try:
        # try validate call to rungames
        launch_key = request.headers.get("Authorisation")

        if launch_key != os.environ["LAUNCH_KEY"]:
            raise Exception("Launch key is invalid.")

        db = connect_to_db()
        with db.connect() as conn:
            chess_game_master = ChessGameMaster(conn)

            launch_status = chess_game_master.run_games()
            conn.close()
            #threading.Thread(target=chess_game_master.run).start()

    except Exception as e:
        print("Error launching game master:", str(e))
        launch_status = str(e)

    if launch_status == "OK":
        data = {'message': 'Launched', 'code': 'SUCCESS', 'payload':"OK"}
        status_code = 201
    else:
        data = {'message': 'Failed', 'code': 'FAIL', 'payload':launch_status}
        status_code = 500

    response = make_response(jsonify(data), status_code)
    response.headers["Content-Type"] = "application/json"
    return response



# on start game request begin new user vs. bot match and send back first move
@app.route("/startgame", methods=["POST"])
def game_master_start_game():
    """
    On start game request begin new user vs. bot match and send back first move
    """
    launch_status = "NOT OK"

    data_dict = request.form.to_dict()

    try:
        # try validate call to startgame
        bot_player_id = int(data_dict["bot_player_id"])
        fen = data_dict["fen"]
        auth_token = request.headers.get("Authorisation")

        # check that JWT authorisation token is valid, returns player_id or error
        auth_return, auth_status = decode_auth_token(auth_token)

        if auth_status == "OK":
            id_value = auth_return
        else:
            raise Exception(auth_status, "Authorisation token refused: " + str(auth_return))

        db = connect_to_db()
        with db.connect() as conn:
            chess_game_master = ChessGameMaster(conn)

            launch_status, ongoing_match_id, fen = chess_game_master.start_game(bot_player_id, fen)
            conn.close()
            #threading.Thread(target=chess_game_master.run).start()

    except Exception as e:
        print("Error launching game master:", str(e))
        launch_status = str(e)

    if launch_status == "OK":
        data = {'message': 'Launched', 'code': 'SUCCESS', 'payload':{"ongoing_match_id":ongoing_match_id, "fen":fen}}
        status_code = 201
    else:
        data = {'message': 'Failed', 'code': 'FAIL', 'payload':launch_status}
        status_code = 500

    response = make_response(jsonify(data), status_code)
    response.headers["Content-Type"] = "application/json"
    return response



# on next move request relaunch user vs. bot match and return bot's next move
@app.route("/<ongoing_match_id>/nextmove", methods=["POST"])
def game_master_next_move(ongoing_match_id):
    """
    On next move request relaunch user vs. bot match and return bot's next move.
    """
    launch_status = "NOT OK"

    data_dict = request.form.to_dict()

    try:
        # try validate call to startgame
        bot_player_id = data_dict["bot_player_id"]
        fen = data_dict["fen"]
        auth_token = request.headers.get("Authorisation")

        # check that JWT authorisation token is valid, returns player_id or error
        auth_return, auth_status = decode_auth_token(auth_token)

        if auth_status == "OK":
            id_value = auth_return
        else:
            raise Exception(auth_status, "Authorisation token refused: " + str(auth_return))

        db = connect_to_db()
        with db.connect() as conn:
            chess_game_master = ChessGameMaster(conn)

            launch_status, ongoing_match_id, fen = chess_game_master.next_move(bot_player_id, fen, ongoing_match_id)
            conn.close()
            #threading.Thread(target=chess_game_master.run).start()

    except Exception as e:
        print("Error launching game master:", str(e))
        launch_status = str(e)

    if launch_status == "OK":
        data = {'message': 'Runned', 'code': 'SUCCESS', 'payload':{"ongoing_match_id":ongoing_match_id, "fen":fen}}
        status_code = 201
    else:
        data = {'message': 'Failed', 'code': 'FAIL', 'payload':launch_status}
        status_code = 500

    response = make_response(jsonify(data), status_code)
    response.headers["Content-Type"] = "application/json"
    return response



# @app.route('/forgotpass', methods=["POST"]) # POST
# def player_reset_password():
#     """
#     Sends email reminder to player email address to regain password
#     Recieves form dict -> {"name":name, "email", email}
#     """
#     data_dict = request.form.to_dict()
#
#     # try import and validate given values
#     try:
#         name = data_dict["name"].replace("\'", "‘") #change single quotes
#         email_recv = data_dict["email"].replace("\'", "‘")
#         table_name = "players"
#
#         if len(name) < 1:
#             raise Exception(name, "Name is too short.")
#
#     except Exception as e:
#         if len(e.args) > 1:
#             credentials_message = f"Error with value: {e.args[0]}. {e.args[1]}"
#         else:
#             credentials_message = str(e)
#         data = {'message': 'Error', 'code': 'FAIL', "payload": str(credentials_message)}
#         status_code = 400
#         return make_response(jsonify(data), status_code)
#
#     # passed initial check, try retrieve from db
#     db = connect_to_db()
#     with db.connect() as conn:
#         db_player = db_retrieve_entry_data(conn, "players", "name", name)
#         conn.close()
#
#     if db_player != None:
#         db_check_message = "OK"
#
#         #extract password
#         password = db_player[6]
#
#         # send reminder email
#         email_send_message = send_reminder_email(email_recv, password)
#
#
#     else: # error finding player in db
#         db_check_message = "Could not find player."
#
#     if db_check_message != "OK": # if db check failed
#         data = {'message': 'Denied', 'code': 'FAIL', "payload": str(db_check_message)}
#         status_code = 400
#     elif email_send_message != "OK": # if email error
#         data = {'message': 'Error', 'code': 'FAIL', "payload": str(email_send_message)}
#         status_code = 400
#     else:
#         data = {'message': 'Approved', 'code': 'SUCCESS', "payload": str(email_send_message)}
#         status_code = 201
#
#     return make_response(jsonify(data), status_code)
#
#
#
# @app.route('/login', methods=["POST"]) # POST
# def player_login():
#     """
#     Accepts or refuses player login request into db
#     Recieves dict form -> {"name":name, "password":password}
#     Returns -> JWT | nothing
#     """
#
#     # read form data
#     data_dict = request.form.to_dict()
#
#     # try import and validate given values
#     try:
#         name = data_dict["name"].replace("\'", "‘") #change single quotes
#         password = data_dict["password"].replace("\'", "‘") #change single quotes
#         table_name = "players"
#
#         if len(password) < 8:
#             raise Exception(password, "Password is too short.")
#         elif len(name) < 1:
#             raise Exception(name, "Name is too short.")
#
#     except Exception as e:
#         if len(e.args) > 1:
#             credentials_message = f"Error with value: {e.args[0]}. {e.args[1]}"
#         else:
#             credentials_message = str(e)
#         data = {'message': 'Error', 'code': 'FAIL', "payload": str(credentials_message)}
#         status_code = 400
#         return make_response(jsonify(data), status_code)
#
#     # passed initial check, try search in db
#     db = connect_to_db()
#     with db.connect() as conn:
#         db_check_message, player_id = db_confirm_player_credentials(conn, table_name, name, password)
#         conn.close()
#
#     # if found + OK
#     if db_check_message == "OK":
#
#         # create JWT for header
#         auth_token = encode_auth_token(player_id)
#
#         data = {'message': 'Approved', 'code': 'SUCCESS', "payload": auth_token}
#         status_code = 201
#     else: #if error
#         auth_token = None
#         data = {'message': 'Denied', 'code': 'FAIL', "payload": str(db_check_message)}
#         status_code = 400
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response



# @app.route('/register', methods=["POST"]) # POST
# def register_new_player():
#     """
#     # Inserts new player into db
#     # Receives dict form -> {"name":name, "password":password, "email", email}
#     # Returns -> JWT
#     """
#
#     data_dict = request.form.to_dict()
#
#     # try import and validate given values
#     try:
#         table_name = "players"
#         name = data_dict["name"].replace("\'", "‘") #change single quotes
#         password = data_dict["password"].replace("\'", "‘")
#         email = data_dict["email"].replace("\'", "‘")
#
#         if len(password) < 8:
#             raise Exception(password, "Password is too short.")
#         elif len(name) < 1:
#             raise Exception(name, "Name is too short.")
#         elif check_valid_email(email) == False:
#             raise Exception(email, "Email is invalid.")
#
#     except Exception as e:
#         if len(e.args) > 1:
#             credentials_message = f"Error with value: {e.args[0]}. {e.args[1]}"
#         else:
#             credentials_message = str(e)
#         data = {'message': 'Error', 'code': 'FAIL', "payload": str(credentials_message)}
#         status_code = 400
#         return make_response(jsonify(data), status_code)
#
#     # passed initial check, try upload to db
#     db = connect_to_db()
#     with db.connect() as conn:
#         if db_retrieve_entry_data(conn, table_name, "name", name) is not None:
#             db_upload_message = "Name is already taken."
#         else:
#             db_upload_message, player_id = db_insert_new_player(conn, table_name, name, password, email)
#         conn.close()
#
#     # if created + OK
#     if db_upload_message == "OK":
#
#         # create JWT for header
#         auth_token = encode_auth_token(player_id)
#
#         data = {'message': 'Created', 'code': 'SUCCESS', "payload": auth_token}
#         status_code = 201
#     else: #if error
#
#         auth_token = None
#         data = {'message': 'Error', 'code': 'FAIL', "payload": str(db_upload_message)}
#         status_code = 400
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     response.headers["Authorisation"] = auth_token
#     return response



# @app.route('/<player_id>/model_url', methods=["GET"]) # GET e.g /2/model_url
# def return_model_url(player_id):
#     """
#     Retrieves player model_url given -> player_id
#     Returns -> model_url
#     """
#     db = connect_to_db()
#
#     with db.connect() as conn:
#         db_player = db_retrieve_entry_data(conn, "players", "player_id", int(player_id))
#         conn.close()
#
#     if db_player == None:
#         # player doesn't exist / error retrieving from DB
#         model_url = None
#     else:
#         # retrieve player model_url
#         model_url = db_player[3]
#
#     # if found
#     if model_url != None:
#         data = {'message': 'Found', 'code': 'SUCCESS', "payload": model_url}
#         status_code = 200
#     else:
#         data = {'message': 'Unfound', 'code': 'FAIL', "payload": model_url}
#         status_code = 404
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response



# @app.route('/<match_id>/pgn', methods=["GET"]) # GET e.g /2/pgn
# def return_pgn(match_id):
#     """
#     Retrieves and returns match pgn given -> match_id
#     Returns -> png
#     """
#     db = connect_to_db()
#
#     with db.connect() as conn:
#         db_match = db_retrieve_entry_data(conn, "matches", "match_id", int(match_id))
#         conn.close()
#
#     if db_match == None:
#         # Match doesn't exist / error retrieving from DB
#         pgn = None
#     else:
#         pgn = db_match[5]
#
#     # if found
#     if pgn != None:
#         data = {'message': 'Found', 'code': 'SUCCESS', "payload": pgn}
#         status_code = 200
#     else:
#         data = {'message': 'Unfound', 'code': 'FAIL', "payload": None}
#         status_code = 404
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response



# @app.route("/matches", methods=["GET"]) # GET
# def return_matches():
#     """
#     Returns a dict of all matches and match data
#     Returns -> [{...match key value pairs...},...]
#     """
#     db = connect_to_db()
#
#     with db.connect() as conn:
#         db_matches = db_retrieve_table_list(conn, "matches")
#         conn.close()
#
#     # if found
#     if db_matches != None:
#         data = {'message': 'Found', 'code': 'SUCCESS', "payload": db_matches}
#         status_code = 201
#     else: #if not found
#         data = {'message': 'Unfound', 'code': 'FAIL', "payload": None}
#         status_code = 404
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response



# @app.route("/players", methods=["GET"]) # GET
# def return_players():
#     """
#     Returns the list of dictionaries with player data
#     Returns -> [{...player data key value pairs...},...]
#     """
#     db = connect_to_db()
#
#     with db.connect() as conn:
#         db_players = db_retrieve_table_list(conn, "players")
#         conn.close()
#
#     # remove unnecessary key:value pairs
#     to_remove = ["model_url", "email", "password"]
#     for player_dict in db_players:
#         for key in to_remove:
#             del player_dict[key]
#
#     # if found
#     if db_players != None:
#         data = {'message': 'Found', 'code': 'SUCCESS', "payload": db_players}
#         status_code = 201
#     else: #if not found
#         data = {'message': 'Unfound', 'code': 'FAIL', "payload": None}
#         status_code = 404
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response



# @app.route("/elo", methods=["GET"]) # GET
# def return_elo():
#     """
#     Returns a list of of shortened player dictionaries with elo_scores
#     Returns -> [{"player_id":player_id, "name":name, "elo_score":elo_score},...]
#     """
#     db = connect_to_db()
#
#     with db.connect() as conn:
#         db_players = db_retrieve_table_list(conn, "players")
#         conn.close()
#
#     # remove unnecessary key:value pairs
#     to_remove = ["model_url", "status_flag", "email", "password"]
#     for player_dict in db_players:
#         for key in to_remove:
#             del player_dict[key] # just keep player_id, name and elo_score
#
#     # if found
#     if db_players != None:
#         data = {'message': 'Found', 'code': 'SUCCESS', "payload": db_players}
#         status_code = 201
#     else: #if not found
#         data = {'message': 'Unfound', 'code': 'FAIL', "payload": None}
#         status_code = 404
#
#     response = make_response(jsonify(data), status_code)
#     response.headers["Content-Type"] = "application/json"
#     return response





# # returns a html string of db contents to display on page + db table descriptions
# @app.route("/database", methods=["GET"]) # GET
# def print_db():
#
#     # connect to db
#     db = connect_to_db()
#
#     # create returned html string
#     html_string = "<!DOCTYPE html><html><body>"
#
#     # populate html body with database table contents & desciptions
#     with db.connect() as conn:
#
#         # show entries of database tables
#         db_players = db_retrieve_table_data(conn, "players")
#         db_players = (x[:-1] for x in db_players) # removes last password coloumn
#
#         html_string += "<h1>Players\n</h1>"
#
#         for x in db_players:
#             html_string += f"<p>{x}\n</p>"
#
#         html_string += "<h1>Matches\n</h1>"
#
#         db_matches = db_retrieve_table_data(conn, "matches")
#
#         for x in db_matches:
#             html_string += f"<p>{x}\n</p>"
#
#         # describe database tables
#         html_string += "<h1>Players Description\n</h1>"
#
#         db_describe_players = db_describe_table(conn, "players")
#         for x in db_describe_players:
#             html_string += f"<p>{x}\n</p>"
#
#         html_string += "<h1>Matches Description\n</h1>"
#
#         db_describe_matches = db_describe_table(conn, "matches")
#         for x in db_describe_matches:
#             html_string += f"<p>{x}\n</p>"
#
#         batch_id = db_latest_batch_id(conn)
#         html_string += f"<p>Latest Batch ID: {batch_id}\n</p>"
#         conn.close()
#
#     # close off returned html string
#     html_string += "</body></html>"
#
#     return html_string



# @app.route("/")
# def home():
#     return redirect("database")



def main():
    #run app
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



if __name__ == "__main__":
    main()
