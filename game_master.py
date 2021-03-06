# Chess Game Master functions and classes launched by scheduler
#
# 1. Requests all player GDrive links from DB
# 2. Downloads all player models from GDrive link
#   i. checks/handles file error cases and sets flags if invalid
# 3. Creates game schedule where all players verse each other once
# 4. Verses the players/models according to schedule
#    i. tracks/calculates game data such as num moves, pieces, player scores, etc
# 5. Updates game data and player data for this batch into DB

from db_access import *
import os
import re
import requests
from datetime import datetime, timedelta, timezone
import chess
import chess.pgn
import random
from tensorflow import keras
import numpy
import threading
#import pickle



#### put in own functions file


def download_gdrive_file(id, destination):
    def get_confirm_token(response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value

        return None

    def save_response_content(response, destination):
        CHUNK_SIZE = 32768

        with open(destination, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)

    URL = "https://docs.google.com/uc?export=download"

    try:
        session = requests.Session()

        response = session.get(URL, params = { 'id' : id }, stream = True)
        token = get_confirm_token(response)

        if token:
            params = { 'id' : id, 'confirm' : token }
            response = session.get(URL, params = params, stream = True)

        response.raise_for_status()

        save_response_content(response, destination)

        return destination

    except requests.exceptions.RequestException as e:
        #print(e)
        return None

#### put in own file functions ^^^


class Match:
    """
    Instance of a chess match. Just used as storage for now.
    """
    def __init__(self, player_1_id, player_1_score, player_2_id, player_2_score, pgn, batch_id, winner_id, status_flag):
        self.player_1_id = player_1_id
        self.player_1_score = player_1_score
        self.player_2_id = player_2_id
        self.player_2_score = player_2_score
        self.pgn = pgn
        if batch_id != None:
            self.batch_id = batch_id
        else:
            self.batch_id = None
        self.date, self.time = self.get_date_time()
        if winner_id != None:
            self.winner_id = winner_id
        else:
            self.winner_id = None
        self.status_flag = status_flag
        # status flags:
        # 0 not used
        # 1 match OK (Has winner)
        # 2 match TIED (No winner)
        # -1 match error -> player has status flag -1 (bad model_url)
        # -2 match error -> player has status flag -2 (bad model)
        # -3 other error


    def get_date_time(self):
        """
        Returns date in format DATE and time in format TIME that db can accept
        """
        now = datetime.now(timezone.utc) + timedelta(hours=10)
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        return (date, time)



class Player:
    """
    Instance of a player. Just used as storage for now.
    """
    def __init__(self, player_id, name, elo_score, model_url, status_flag):
        self.player_id = player_id
        self.name = name
        self.elo_score = elo_score
        self.model_url = model_url
        self.status_flag = status_flag # reset to zero every new VM instance?
        self.model_path = None
        self.scores = [] # list of their match scores (used to calculate elo)
        self.model = None # entire model downloaded and stored
        self.colour = None # set to "white" or "black" each game
        # status flags:
        # 0 just created (no model link provided)
        # 1 model link added
        # 2 model link valid and loaded without error (ready to verse)
        # -1 model could not be downloaded
        # -2 problem with loading model for chess match
        # -3 other error



class ChessGameMaster:
    """
    Downloads player AI models, conducts chess games and records game data
    """
    def __init__(self, conn):
        self.conn = conn
        self.players = None
        self.matches = []
        self.batch_id = None
        self.match_schedule = None
        self.round = 0
        self.game_threads = []


    def initialise_players(self):
        """
        Store players as objects in list and returns list.
        Tries to download models for players also.
        """

        players_data_list = self.get_players_data()

        # instantiate player objects with downloaded player data
        players = []
        for p in players_data_list:
            players.append(Player(p["player_id"], p["name"], p["elo_score"], p["model_url"], p["status_flag"]))

        for player in players:
            #player.status_flag = 0

            if player.status_flag >= 1: # just inserted new model link
                # try download model for each player (even if link hasnt changed)
                self.download_model(player)
            if player.model_path != None: # download succeeded but not loaded
                # try load model for each player from downloaded file
                #print("loading")
                self.load_model(player)

        return players


    def get_players_data(self):
        """
        Calls database retrieval function and returns list of player data dictionaries

        Returns -> [list of dicts{key:value}] -> [{player_id:x, name:x, elo_score:x, model_url:x, status_flag:x, email:x, password:x},...]
        """

        players_data = db_retrieve_table_list(self.conn, "players")

        return players_data


    def download_model(self, player):
        """
        Downloads model for player from their model_url.
        Sets player status_flag -> 1 (success) | -1 (fail).
        """
        if not os.path.exists('models'):
            os.makedirs('models')

        #print("extracting")
        #print(player.model_url)
        if player.model_url != None:

            url_id = self.extract_url_id(player.model_url) #e.g "1vTnYdYU5tJOOYlWVG1ct9Lb9aTTYON1A"

            destination = "models/" + str(player.player_id) + ".h5"

            player.model_path = download_gdrive_file(url_id, destination)
        # set status flag for model download
        if player.model_path == None:
            player.status_flag = -1 # error downloading model file
        else:
            player.status_flag = 1 # downloaded model file ok


    def load_model(self, player):
        """
        Loads keras model from downloaded model file.
        Sets player status_flag -> 2 (success) | -2 (fail).
        """
        try:
            #print(player.model_path)
            #print(keras.backend.image_data_format())
            player.model = keras.models.load_model(player.model_path)
            #print(player.model)
            player.status_flag = 2 # set model load error flag
        except Exception as e:
            #print(e)
            player.status_flag = -2 # set model load error flag


    def extract_url_id(self, url):
        # returns extracted url_id from given url
        # e.g "1vTnYdYU6TJOOYlWVG1ct9Lb9aTTYON1A"
        # from "https://drive.google.com/file/d/1vTnYdYU6TJOOYlWVG1ct9Lb9aTTYON1A/view?usp=sharing"
        url_id = None

        x = re.search("/[-\w]{25,}/?", url)
        #print(x)
        if x:
            url_id = re.sub('/', '', x[0])
        return url_id


    def print_players(self):
        for player in self.players:
            print(f"Name: {player.name}, ID: {player.player_id}, ELO score: {player.elo_score}, Model Path: {player.model_path}, Status: {player.status_flag}")


    def update_players_data(self):
        """
        Called at end of all chess games.

        Calls db function to upload new player data to database
        """
        for player in self.players:
            db_upload_message = db_update_player_data(self.conn, player)
            if db_upload_message != "OK":
                #print("Error uploading player.")
                #print(db_upload_message)
                break

        return db_upload_message


    def update_matches_data(self):
        """
        Called at end of all chess games.

        Calls db function to upload new matches data to database
        """
        for match in self.matches:
            db_upload_message = db_insert_new_match(self.conn, match)
            if db_upload_message != "OK":
                #print("Error uploading match.")
                #print(db_upload_message)
                break

        return db_upload_message


    def get_batch_id(self):
        """
        Calls database retrieval function and returns batch_id.
        Returns -> int | None.
        """
        latest_batch_id = db_latest_batch_id(self.conn)

        if latest_batch_id == None:
            return 1
        else:
            return latest_batch_id + 1


    def create_match_schedule(self):
        """
        Creates a tuple of unique player pairings which gives match schedule of players.
        """
        #print("running")
        match_schedule_list = []

        # create unique pairings of all ready players
        i = 0
        j = 0
        while i < len(self.players):
            for j in range(i + 1, len(self.players)):
                match_schedule_list.append([self.players[i], self.players[j]])
            i += 1

        match_schedule_tuple = tuple(match_schedule_list)
        return match_schedule_tuple #iter(match_schedule_tuple)


    def check_status_flags(self, object_list):
        for object in object_list:
            if object.status_flag < 0: # something errored
                return "Error"
        return "OK"


    def play_chess(self, player_1, player_2, fen=None):
        """
        Plays a game of chess between two provided players.

        Should create a new Match object for this chess match
        Should also calculate a score for the players (adds to Match object and player.scores list)

        anything else important
        """

        """Utility Functions"""
        ## split dimensions of board to translate move to the model
        squares_index = {
            'a': 0,
            'b': 1,
            'c': 2,
            'd': 3,
            'e': 4,
            'f': 5,
            'g': 6,
            'h': 7
        }

        def square_to_index(square):
            letter = chess.square_name(square)
            return 8 - int(letter[1]), squares_index[letter[0]]

        def split_dims(board):
            # this is the 3d matrix
            # 14: 6 for white chess pieces, 6 for black chess pieces, 2 for valid attacks and moves for white and black
            # 8:8 is the chess board size
            # order is (pawns, knights, bishops, rooks, queen,king)

            board3d = numpy.zeros((14, 8, 8), dtype=numpy.int8)

            # here we add the pieces's view on the matrix
            for piece in chess.PIECE_TYPES:
                for square in board.pieces(piece, chess.WHITE):
                    idx = numpy.unravel_index(square, (8, 8))
                    board3d[piece - 1][7 - idx[0]][idx[1]] = 1
                for square in board.pieces(piece, chess.BLACK):
                    idx = numpy.unravel_index(square, (8, 8))
                    board3d[piece + 5][7 - idx[0]][idx[1]] = 1

            # add attacks and valid moves too
            # so the network knows what is being attacked
            aux = board.turn
            board.turn = chess.WHITE
            for move in board.legal_moves:
                i, j = square_to_index(move.to_square)
                board3d[12][i][j] = 1
            board.turn = chess.BLACK
            for move in board.legal_moves:
                i, j = square_to_index(move.to_square)
                board3d[13][i][j] = 1
            board.turn = aux

            return board3d


        # this is the function that gets the move from the neural network
        def get_ai_move(board, depth, model):
            max_move = None
            # set max to -infinity
            max_eval = -numpy.inf

            for move in board.legal_moves:
                board.push(move)
                eval = minimax(board, depth - 1, -numpy.inf, numpy.inf, False, model)
                board.pop()
                if eval > max_eval:
                    max_eval = eval
                    max_move = move

            return max_move


        # used for the minimax algorithm
        def minimax_eval(board, player):
            board3d = split_dims(board)
            board3d = numpy.expand_dims(board3d, 0)
            #print(model.predict(board3d)[0][0])
            #if player.colour == "white":
            return player.model.predict(board3d)[0][0]
            #elif player.colour == "black":
              #return 1 - player.model.predict(board3d)[0][0]


        def minimax(board, depth, alpha, beta, player, maximising):
            if depth == 0 or board.is_game_over():
                return minimax_eval(board, player)

            if maximising == True: # maximizing_player
                max_eval = -numpy.inf
                for move in board.legal_moves:
                    board.push(move)
                    eval = minimax(board, depth - 1, alpha, beta, player, False)
                    board.pop()
                    max_eval = max(max_eval, eval)
                    alpha = max(alpha, eval)
                    if beta <= alpha:
                        break
                return max_eval

            elif maximising == False: # minimising_player
                min_eval = numpy.inf
                for move in board.legal_moves:
                    board.push(move)
                    eval = minimax(board, depth - 1, alpha, beta, player, True)
                    board.pop()
                    min_eval = min(min_eval, eval)
                    beta = min(beta, eval)
                    if beta <= alpha:
                        break
                return min_eval


        # This is the actual function that gets the move from the neural network
        def get_ai_move(board, depth, player):
            # White player tries to maximize score
            if player.colour == "white":
              max_move = None
              # set max to -infinity
              max_eval = -numpy.inf

              for move in board.legal_moves:
                  board.push(move)
                  eval = minimax(board, depth - 1, -numpy.inf, numpy.inf, player, maximising=False)
                  board.pop()
                  if eval > max_eval:
                      max_eval = eval
                      max_move = move

              return max_move

            # Black player tries to minimize score
            elif player.colour == "black":
              min_move = None
              # set min to infinity
              min_eval = numpy.inf

              for move in board.legal_moves:
                  board.push(move)
                  eval = minimax(board, depth - 1, -numpy.inf, numpy.inf, player, maximising=True)
                  board.pop()
                  if eval < min_eval:
                      min_eval = eval
                      min_move = move
              return min_move


        """
        Chess Match
        """

        if player_1 == "Human":
            ### INITIALISE HUMAN VS. BOT MATCH ###




            ## create board with fen
            board = chess.Board(fen)
            print("board \n", board)
            game = chess.pgn.Game()
            ## apply fen as starting board
            game.setup(board)
            node = game

            if board.is_game_over():
                status = "Error"
                # error: stop playing
                return status, fen

            #print("game\n", game)

            print(f"Starting Match Between Human and Bot: {player_2.player_id}")
            # try get ai move
            minmax_depth = 1
            try:
                move = get_ai_move(board, minmax_depth, player_2)
            except Exception as e:
                print("Error getting move from player 2:", str(e))
                # error: stop playing
                status = str(e)
                return status, fen

            board.push(move)
            # save in PGN
            node = node.add_variation(move)
            #print(f'\n{board}')
            status = "OK"
            # convert new board to fen
            fen = board.fen()
            # return status and fen
            return status, fen


        else:
            ### INITIALISE BOT VS. BOT MATCH ###

            ## define pgn attributes
            now = datetime.now(timezone.utc) + timedelta(hours=10)
            board = chess.Board()
            game = chess.pgn.Game()
            game.headers["Event"] = "Bot VS Bot"
            game.headers["Site"] = "Sydney"
            game.headers["Date"] = now.strftime("%d/%m/%Y")
            game.headers["Round"] = str(self.get_round())

            ##Should be changed to players Ids/names
            game.headers["White"] = player_1.name
            game.headers["Black"] = player_2.name
            player_1.colour = "white"
            player_2.colour = "black"

            game.setup(board)
            node = game

            ### START MATCH ###
            print(f"Starting Match Between {player_1.name} and {player_2.name}")
            iteration = 0
            minmax_depth = 1
            while True:
                # Player 1 move
                # set random starting point everytime
                if iteration == 0:
                    move = random.choice([move for move in board.legal_moves])
                else:
                    try:
                        move = get_ai_move(board, minmax_depth, player_1)
                    except:
                        # error getting move from player 1
                        player_1.status_flag = -3
                        # add match information with error flag
                        status_flag = -3
                        self.matches.append(Match(player_1.player_id, None, player_2.player_id, None, None, self.batch_id, None, status_flag))
                        # stop playing
                        return

                iteration += 1
                board.push(move)
                # save in PGN
                node = node.add_variation(move)
                #print(f'\n{board}')
                if board.is_game_over():
                    break

                # Player 2 move
                try:
                    move = get_ai_move(board, minmax_depth, player_2)
                except:
                    # error getting move from player 2
                    player_2.status_flag = -3
                    # add match information with error flag
                    status_flag = -3
                    self.matches.append(Match(player_1.player_id, None, player_2.player_id, None, None, self.batch_id, None, status_flag))
                    # stop playing
                    return

                board.push(move)
                # save in PGN
                node = node.add_variation(move)
                #print(f'\n{board}')
                if board.is_game_over():
                    break

            game.headers["Result"] = board.result()

            ##PGN should be stored here (game)
            #print(game) # pgn
            #print(game, file=open("/content/drive/MyDrive/Chess/pgnMatch.txt", "w"), end="\n\n")


            #Compute Score (based on winner loser and length of the match)
            #the shorter the match the better the score for the winner
            #Should be normalized first
            #If you apply a 50-move limit, the longest possible chess game is 5898.5 moves long.

            if game.headers["Result"] =='1-0':
                #player1_score = ((400 *1/iteration)-(0))/(400-0)
                #player2_score = ((-400 *iteration)-(-400*5898.5))/((0)-((-400*5898.5)))
                # Using ELO calculations
                player1_score = (player_2.elo_score + 400)
                player2_score = (player_1.elo_score - 400)
                winner_id = player_1.player_id
                status_flag = 1 # OK
            elif game.headers["Result"] =='0-1':
                #player1_score = ((-400 *iteration)-(-400*5898.5))/((0)-((-400*5898.5)))
                #player2_score = ((400 *1/iteration)-(0))/(400-0)
                player1_score = (player_2.elo_score - 400)
                player2_score = (player_1.elo_score + 400)
                winner_id = player_2.player_id
                status_flag = 1 # OK
            else:
                #player1_score = ((200 *iteration)-(0))/((200*5898.5)-(0))
                #player2_score = ((200 *iteration)-(0))/((200*5898.5)-(0))
                player1_score = player_2.elo_score
                player2_score = player_1.elo_score
                winner_id = None
                status_flag = 2 # OK BUT Tied Match

            player_1.scores.append(player1_score)
            player_2.scores.append(player2_score)

            #print(f"Player 1 score: {player1_score}")
            #print(f"Player 2 score: {player2_score}")

            # create a match object and add it to the matches list!
            self.matches.append(Match(player_1.player_id, player1_score, player_2.player_id, player2_score, game, self.batch_id, winner_id, status_flag))
            print(f"Completed Match Between {player_1.name} and {player_2.name}")


    def get_round(self):
        self.round += 1
        return self.round


    def calculate_elo_score(self, player):
        """
        Given player with list of scores calculate elo_score
        """
        if len(player.scores) > 0:
            player.elo_score = (player.elo_score + (sum(player.scores)/len(player.scores))) // 2
            if player.elo_score < 0:
                player.elo_score = 0


    def run_games(self):
        """
        After init calls game functions and database functions
        """
        print("Running")
        # initialise
        self.players = self.initialise_players()
        self.batch_id = self.get_batch_id()
        self.match_schedule = self.create_match_schedule()

        # pick two players from match schedule
        for player_1, player_2 in self.match_schedule:

            # check if players are ready
            if self.check_status_flags([player_1, player_2]) == "OK":
                # ready to play game
                try:
                    # launch game between two players in its own thread
                    t = threading.Thread(target=self.play_chess, args=(player_1, player_2, None,))
                    t.start()
                    self.game_threads.append(t)

                except:
                    # other error flag
                    status_flag = -3
                    self.matches.append(Match(player_1.player_id, None, player_2.player_id, None, None, self.batch_id, None, status_flag))

            else: # known error with one of the players
                # return a match object with status_flag set appropriately
                # collect status flags of players showing an error
                player_error_flags = [p.status_flag for p in [player_1, player_2] if p.status_flag < 0]
                if len(player_error_flags) > 0:
                    # set match status flag the first occuring of the player errors
                    status_flag = max(player_error_flags)
                    self.matches.append(Match(player_1.player_id, None, player_2.player_id, None, None, self.batch_id, None, status_flag))

        elo_status = "OK"

        # wait for games to finish
        for t in self.game_threads:
            t.join()

        try:
            # finished games
            for player in self.players:
                self.calculate_elo_score(player)
        except Exception as e:
            elo_status = f"Error calculating elo: {str(e)}"

        if elo_status == "OK":
            # update database
            db_upload_message = self.update_players_data() #uploads all player object data to db
            if db_upload_message == "OK":
                db_upload_message = self.update_matches_data() #uploads all matches object data to db

            # end VM instance
            launch_status = str(db_upload_message)
        else:
            launch_status = str(elo_status)

        return launch_status


    def get_ai_move_from_fen(self, fen, bot_player):
        status = "OK"

        try:
            # get ai move, ai is always black
            status, fen = self.play_chess("Human", bot_player, fen)

        except Exception as e:
            print("Error:", str(e))
            status = str(e)

        return status, fen


    def bot_move(self, bot_player_id, fen):

        db_check_message = "OK"
        # get locally saved model path
        filename = f"{bot_player_id}.h5"
        model_path = os.path.join(os.path.join(os.getcwd(), "final_models"), filename)

        try:
            # try locate model locally
            #with open(model_path, 'rb') as f:
            #if os.path.isfile(model_path):
            if not os.path.exists('final_models'):
                os.makedirs('final_models')
            bot_model = keras.models.load_model(model_path)
            print("Loaded model")
        except Exception as e:
            print(str(e))
            # download model and save locally
            with open(model_path, 'wb') as f:
                # get bot_player_id model
                db_check_message, binary_bot_model = db_get_player_model(self.conn, bot_player_id)
                #print(binary_bot_model)
                if db_check_message == "OK":
                    f.write(binary_bot_model)
                    #pickle.dump(pickled_bot_model, f, pickle.HIGHEST_PROTOCOL)
                    bot_model = keras.models.load_model(model_path)
                else:
                    print("Error loading bot model from db:", db_check_message)


        # do something to the fen
        if db_check_message == "OK":
            player_id = bot_player_id
            status_flag = 2
            bot_player = Player(bot_player_id, None, None, None, None)
            bot_player.model = bot_model
            bot_player.colour = "black"

            status, fen = self.get_ai_move_from_fen(fen, bot_player)


            if status == "OK":
                print("Move OK")
            else:
                # Error or game already completed
                print("Error:", status)

            return status, fen

        return db_check_message, fen


if __name__ == "__main__":
    from db_connect import *
    from db_access import *

    db = connect_to_db()
    with db.connect() as conn:
        chess_game_master = ChessGameMaster(conn)
        chess_game_master.run_games()
