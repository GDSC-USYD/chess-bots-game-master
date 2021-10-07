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



# on next move request relaunch user vs. bot match and return bot's next move
@app.route("/botmove", methods=["POST"])
def game_master_bot_move():
    """
    On bot move request launch user vs. bot and return bot's next move.
    """
    launch_status = "NOT OK"

    data_dict = request.form.to_dict()

    try:
        # try validate call to startgame
        bot_player_id = data_dict["bot_player_id"]
        fen = data_dict["fen"]

        db = connect_to_db()
        with db.connect() as conn:
            chess_game_master = ChessGameMaster(conn)

            launch_status, fen = chess_game_master.bot_move(bot_player_id, fen)
            conn.close()
            #threading.Thread(target=chess_game_master.run).start()

    except Exception as e:
        print("Error launching game master:", str(e))
        launch_status = str(e)

    if launch_status == "OK":
        data = {'message': 'Runned', 'code': 'SUCCESS', 'payload':fen}
        status_code = 201
    else:
        data = {'message': 'Failed', 'code': 'FAIL', 'payload':launch_status}
        status_code = 500

    response = make_response(jsonify(data), status_code)
    response.headers["Content-Type"] = "application/json"
    return response





def main():
    #run app
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))



if __name__ == "__main__":
    main()
