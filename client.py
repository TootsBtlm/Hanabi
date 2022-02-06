from sys import stdout
from threading import Thread
import GameData
import socket  
from constants import *
import os
from state import State
import math
import logging
import copy
import time
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--ip', type=str, default=HOST, help='IP address')
parser.add_argument('--port', type=int, default=PORT, help='Port')
mode = parser.add_mutually_exclusive_group()
mode.add_argument('--manual', action='store_true', help='Play manually')
mode.add_argument('--ai', action='store_true', default=True, help='Play with the agent (default)')
parser.add_argument('--name', type=str, default="default_name", help='Name of the player')
parser.add_argument('--debug', action='store_true', default=False, help='Create log')
args = parser.parse_args()

ip = args.ip
port = args.port
playerName = args.name
mode = "manual" if args.manual else "ai"
debug = args.debug

run = True
statuses = ["Lobby", "Game", "GameHint"]
status = statuses[0]
colorList = ["red","yellow","green","blue","white"]
nbCardsValue = [3,2,2,2,1]
state = State(playerName)
startPlayer = None

def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s', datefmt="%I:%M:%S")
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

# Debug purpose
if debug:
    open("log/agent_"+playerName+".log", 'w').close()
    open("log/reward_"+playerName+".log", 'w').close()
    debugLog = setup_logger("Debug","log/agent"+playerName+".log",logging.WARNING)
    rewardLog = setup_logger("Reward","log/reward_"+playerName+".log",logging.DEBUG)
else:
    debugLog = None
    rewardLog = None
def valid_actions(state: State):
    """Return a list of valid actions for a given state"""
    actions = list()
    hints = [[[False for _ in range(5)] for _ in range(2)] for __ in range(len(state.players))]
    for index, card in enumerate(state.players[state.position].hand):
        actions.append(GameData.ClientPlayerPlayCardRequest(playerName, index))
        if state.usedNoteTokens > 0:
            actions.append(GameData.ClientPlayerDiscardCardRequest(playerName, index))
    if state.usedNoteTokens < 8:
        for ip,player in enumerate(state.players):
            if playerName != player.name:
                for ic,card in enumerate(player.hand):
                    if not state.playersCard[ip][ic][1] and not hints[ip][1][colorList.index(card.color)]:
                        hints[ip][1][colorList.index(card.color)] = True
                        actions.append(GameData.ClientHintData(playerName, player.name, "color", card.color))
                    if not state.playersCard[ip][ic][0] and not hints[ip][0][card.value-1]:
                        hints[ip][0][card.value-1] = True
                        actions.append(GameData.ClientHintData(playerName, player.name, "value", card.value))
    return actions

def reward(state: State, log=False):
    """Return the reward (evaluation) for the given state"""
    finishedFirework = 10_000        
    usedStormToken = 500
    cardPlayed = 5_000   
    usedNoteToken = 2.3 
    fullHintedCardReward = 20 
    hintedCardReward = 15  
    fullKnownHotCardReward = 800  
    knownHotCardReward = 325  
    discardedHotCardReward = 800  
    fullKnownUsefullCardReward = 150
    partiallyKnownUsefullCardReward = 35
    discardedUsefullCardReward = 200
    fullKnownUselessCardReward = 400
    partiallyKnownUselessCardReward = 100
    discardedUselessCardReward = 500
    knownNumberReward = 2

    reward = 0
    reward += (finishedFirework * state.checkFinishedFirework())
    if state.usedStormTokens > 0:
        reward -= (math.pow(usedStormToken,state.usedStormTokens) + 20_000*state.usedStormTokens)
    reward += (cardPlayed * state.checkNumberOfCards())
    if state.usedNoteTokens > 0:
        reward -= (math.pow(usedNoteToken,state.usedNoteTokens) + 10 * state.usedNoteTokens)
    fullHintedCard, hintedCard = state.checkHintedCards()
    reward += (fullHintedCardReward * fullHintedCard) + (hintedCardReward * hintedCard)
    fullKnownHotCard, partiallyKnownHotCard, discardedHotCard = state.checkHotCards()
    fullKnownUsefullCard, partiallyKnownUsefullCard, discardedUsefullCard = state.checkUsefullCards()
    fullKnownUselessCard, partiallyKnownUselessCard, discardedUselessCard = state.checkUselessCards()
    knownNumberCard = state.checkNumberCards()
    reward += fullKnownHotCard * fullKnownHotCardReward
    reward += partiallyKnownHotCard * knownHotCardReward
    reward -= (discardedHotCard * discardedHotCardReward)
    reward += fullKnownUsefullCard * fullKnownUsefullCardReward
    reward += partiallyKnownUsefullCard * partiallyKnownUsefullCardReward
    reward -= discardedUsefullCard * discardedUsefullCardReward
    reward += fullKnownUselessCard * fullKnownUselessCardReward
    reward += partiallyKnownUselessCard * partiallyKnownUselessCardReward
    reward += discardedUselessCard * discardedUselessCardReward
    return reward

def playCard(state: State, player, value, color, position):
    """Return the next state when agent plays the card with given value and color"""
    newState = copy.deepcopy(state)
    newState.playCard(player, value, color, position)
    return newState

def discardCard(state: State, player, value, color, position):
    """Return the next state when agent discards the card with given value and color"""
    newState = copy.deepcopy(state)
    newState.discardCard(player, value, color, position)
    return newState

def hintCard(state: State, destination, type, value, position):
    """Return the next state when agent hints the given player with given type and value"""
    newState = copy.deepcopy(state)
    newState.hintCard(destination, type, value, position)
    return newState

def restart():
    """Reset the state object to start a new game"""
    state = State(playerName)
    state.currentPlayer = None
    state.addPlayers(startPlayer)
    return state

def play_action(state: State, player, action):
    """Return the next state when agent plays the given `action` in the given `state`"""
    newStates = []
    probas = []
    cards = []
    if type(action) is GameData.ClientPlayerPlayCardRequest:
        position = action.handCardOrdered
        cardsProba = probaCardPlay(state, action)
        for color in cardsProba:
            for i,value in enumerate(cardsProba[color]):
                if value != 0:
                    newState = playCard(state, player, i+1, color, position)
                    newStates.append(newState)
                    probas.append(value)
                    cards.append([i+1, color])
    elif type(action) is GameData.ClientPlayerDiscardCardRequest:
        position = action.handCardOrdered
        cardsProba = probaCardPlay(state, action)
        for color in cardsProba:
            for i,value in enumerate(cardsProba[color]):
                if value != 0:
                    newState = discardCard(state, player, i+1, color, position)
                    newStates.append(newState)
                    probas.append(value)
                    cards.append([i+1, color])
    elif type(action) is GameData.ClientHintData:
        destination = action.destination
        _type = action.type
        value = action.value
        position = []
        for p in state.players:
            if p.name == destination:
                if _type == "color":
                    for ic, card in enumerate(p.hand):
                        if card.color == value:
                            position.append(ic)
                elif _type == "value":
                    for ic, card in enumerate(p.hand):
                        if card.value == value:
                            position.append(ic)
        newState = hintCard(state, destination, _type, value, position)
        newStates.append(newState)
        probas.append(1.)

    return newStates, probas, cards

def probaCardPlay(state: State, action):
    """Return an array of the probabilities of each card to be played by the given action in the given state"""
    proba = {"red" : [0,0,0,0,0],
            "yellow" : [0,0,0,0,0], 
            "green" : [0,0,0,0,0],
            "blue" : [0,0,0,0,0], 
            "white" : [0,0,0,0,0]}
    if type(action) is GameData.ClientPlayerPlayCardRequest or GameData.ClientPlayerDiscardCardRequest:
        for player in state.players:
            if player.name == state.currentPlayer:
                value = player.hand[action.handCardOrdered].value
                color = player.hand[action.handCardOrdered].color
        if color == None:
            if value == None:
                cardsPlayed = 0
                for color in colorList:
                    cardsPlayed += sum(state.cards[color])
                cardsLeft = 50 - cardsPlayed
                for value in range(5):
                    for i,color in enumerate(colorList):
                        proba[color][value] = (nbCardsValue[value] - state.cards[color][value]) / cardsLeft
                return proba
            else:
                cardsPlayed = [0,0,0,0,0]
                for i,color in enumerate(colorList):
                    cardsPlayed[i] = state.cards[color][value-1]
                cardsLeft = (nbCardsValue[value-1]*5) - sum(cardsPlayed)
                for i,color in enumerate(colorList):
                    proba[color][value-1] = (nbCardsValue[value-1]-cardsPlayed[i])/cardsLeft
                return proba
        else:
            if value == None:
                cardsPlayed = [0,0,0,0,0]
                for i in range(5):
                    cardsPlayed[i] = state.cards[color][i]
                cardsLeft = 0
                for i in range(5):
                    cardsLeft += nbCardsValue[i] - cardsPlayed[i]
                for i in range(5):
                    proba[color][i] = (nbCardsValue[i]-cardsPlayed[i])/cardsLeft
                return proba
            else:
                proba[color][value-1] = 1
                return proba

def policy(state, actions):
    """
    Return the action to be played among the possible actions in the given state.
    It simulates each action and evaluate the expected reward (evaluation) of the next state.
    It chooses the action that has biggest cumulative expected reward.
    """
    actionPossible = [any(type(t) is GameData.ClientPlayerPlayCardRequest for t in actions),
                        any(type(t) is GameData.ClientPlayerDiscardCardRequest for t in actions),
                            any(type(t) is GameData.ClientHintData for t in actions)]

    totalPlayReward = [0,0,0,0,0]
    playActions = [None,None,None,None,None]

    totalDiscardReward = [0,0,0,0,0]
    discardActions = [None,None,None,None,None]

    totalHintReward = [[[None for _ in range(5)] for _ in range(2)] for _ in range(len(state.players))]
    
    for ia, action in enumerate(actions):
        newStates, probas, cards = play_action(state, playerName, action)
        if type(action) is GameData.ClientPlayerPlayCardRequest:
            position = action.handCardOrdered
            playActions[position] = action
            for i,newState in enumerate(newStates):
                newStateReward = reward(newState, True)
                totalPlayReward[position] += probas[i] * newStateReward
        elif type(action) is GameData.ClientPlayerDiscardCardRequest:
            position = action.handCardOrdered
            discardActions[position] = action
            for i,newState in enumerate(newStates):
                newStateReward = reward(newState, True)
                totalDiscardReward[position] += probas[i] * newStateReward
        elif type(action) is GameData.ClientHintData:
            for i,newState in enumerate(newStates):
                for ip, p in enumerate(state.players):
                    if action.destination == p.name:
                        if action.type == "color":
                            for ic, c in enumerate(colorList):
                                if c == action.value:
                                    totalHintReward[ip][0][ic] = reward(newState, True)
                        elif action.type == "value":
                            totalHintReward[ip][1][action.value-1] = reward(newState, True)

    maxPlay = [max(totalPlayReward), totalPlayReward.index(max(totalPlayReward))] if actionPossible[0] else [None,None]
    maxDiscard = [max(totalDiscardReward), totalDiscardReward.index(max(totalDiscardReward))] if actionPossible[1] else [None,None]
    
    maxHint = [None,None,None,None]
    if actionPossible[2]:
        totalHintReward = np.array(totalHintReward,dtype=np.float64)
        ip, it, iv = np.where(totalHintReward == np.nanmax(totalHintReward))
        ip, it, iv = ip[0], it[0], iv[0]
        maxHint[0] = totalHintReward[ip][it][iv]
        maxHint[1] = ip
        maxHint[2] = it
        maxHint[3] = iv

    maxActions = [maxPlay[0],maxDiscard[0],maxHint[0]]
    maxAction = max(m for m in maxActions if m is not None)
        
    if maxAction == maxPlay[0]: return playActions[maxPlay[1]]
    elif maxAction == maxDiscard[0]: return discardActions[maxDiscard[1]]
    elif maxAction == maxHint[0]:
        player = state.players[maxHint[1]].name
        if maxHint[2] == 0:
            _type = "color"
            _value = colorList[maxHint[3]]        
        else:
            _type = "value"
            _value = maxHint[3]+1
        return GameData.ClientHintData(state.currentPlayer,player,_type,_value)

def manageInput():
    global run
    global status
    global state
    while run:
        if mode == "ai":
            if status == statuses[0]:
                print("-- Agent -- Ready up")
                s.send(GameData.ClientPlayerStartRequest(playerName).serialize())
                while status == statuses[0]:
                    pass
            elif status == statuses[1]:
                if state.currentPlayer == playerName and run:
                    state.updated = False
                    s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
                    while not state.updated:
                        pass
                    actions = valid_actions(state)
                    action = policy(state,actions)
                    try:
                        if type(action) is GameData.ClientPlayerPlayCardRequest:
                            state.players[state.position].hand[action.handCardOrdered].value = None
                            state.players[state.position].hand[action.handCardOrdered].color = None
                        elif type(action) is GameData.ClientPlayerDiscardCardRequest:
                            state.players[state.position].hand[action.handCardOrdered].value = None
                            state.players[state.position].hand[action.handCardOrdered].color = None
                        s.send(action.serialize())
                        state.currentPlayer = None
                    except Exception as e:
                        print("-- Agent -- Error on playing action from policy")
                        print(e)
                        continue
        else:
            command = input()
            if command == "exit":
                run = False
                os._exit(0)
            elif command == "ready" and status == statuses[0]:
                s.send(GameData.ClientPlayerStartRequest(playerName).serialize())
            elif command == "show" and status == statuses[1]:
                s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
            elif command.split(" ")[0] == "discard" and status == statuses[1]:
                try:
                    cardStr = command.split(" ")
                    cardOrder = int(cardStr[1])
                    s.send(GameData.ClientPlayerDiscardCardRequest(playerName, cardOrder).serialize())
                except:
                    print("Maybe you wanted to type 'discard <num>'?")
                    continue
            elif command.split(" ")[0] == "play" and status == statuses[1]:
                try:
                    cardStr = command.split(" ")
                    cardOrder = int(cardStr[1])
                    s.send(GameData.ClientPlayerPlayCardRequest(playerName, cardOrder).serialize())
                except:
                    print("Maybe you wanted to type 'play <num>'?")
                    continue
            elif command.split(" ")[0] == "hint" and status == statuses[1]:
                try:
                    destination = command.split(" ")[2]
                    t = command.split(" ")[1].lower()
                    if t != "colour" and t != "color" and t != "value":
                        print("Error: type can be 'color' or 'value'")
                        continue
                    value = command.split(" ")[3].lower()
                    if t == "value":
                        value = int(value)
                        if int(value) > 5 or int(value) < 1:
                            print("Error: card values can range from 1 to 5")
                            continue
                    else:
                        if value not in ["green", "red", "blue", "yellow", "white"]:
                            print("Error: card color can only be green, red, blue, yellow or white")
                            continue
                    s.send(GameData.ClientHintData(playerName, destination, t, value).serialize())
                except:
                    print("Maybe you wanted to type 'hint <type> <destinatary> <value>'?")
                    continue
            elif command == "":
                print("[" + playerName + " - " + status + "]: ", end="")
            else:
                print("Unknown command: " + command)
                continue
            stdout.flush()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    request = GameData.ClientPlayerAddData(playerName)
    s.connect((HOST, PORT))
    s.send(request.serialize())
    data = s.recv(DATASIZE)
    data = GameData.GameData.deserialize(data)
    if type(data) is GameData.ServerPlayerConnectionOk:
        print("Connection accepted by the server. Welcome " + playerName)
    print("[" + playerName + " - " + status + "]: ", end="")
    Thread(target=manageInput).start()
    while run:
        dataOk = False
        data = s.recv(DATASIZE)
        if not data:
            continue
        data = GameData.GameData.deserialize(data)
        if type(data) is GameData.ServerPlayerStartRequestAccepted:
            dataOk = True
            print("Ready: " + str(data.acceptedStartRequests) + "/"  + str(data.connectedPlayers) + " players")
            data = s.recv(DATASIZE)
            data = GameData.GameData.deserialize(data)
        if type(data) is GameData.ServerStartGameData:
            dataOk = True
            print("Game start!")
            if mode == "ai":
                startPlayer = data.players
                state.addPlayers(data.players)
                s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
            s.send(GameData.ClientPlayerReadyData(playerName).serialize())
            status = statuses[1]
        if type(data) is GameData.ServerGameStateData:
            dataOk = True
            if mode == "ai":
                state.currentPlayer = data.currentPlayer
                for index, player in enumerate(data.players):
                    if playerName != player.name:
                        state.players[index] = player
                state.tableCards = data.tableCards
                state.discardPile = data.discardPile
                state.usedNoteTokens = data.usedNoteTokens
                state.usedStormTokens = data.usedStormTokens
                state.updateCards()
                state.updated = True
            else:
                print("Current player: " + data.currentPlayer)
                print("Player hands: ")
                for p in data.players:
                    print(p.toClientString())
                print("Cards in your hand: " + str(data.handSize))
                print("Table cards: ")
                for pos in data.tableCards:
                    print(pos + ": [ ")
                    for c in data.tableCards[pos]:
                        print(c.toClientString() + " ")
                    print("]")
                print("Discard pile: ")
                for c in data.discardPile:
                    print("\t" + c.toClientString())            
                print("Note tokens used: " + str(data.usedNoteTokens) + "/8")
                print("Storm tokens used: " + str(data.usedStormTokens) + "/3")
        if type(data) is GameData.ServerActionInvalid:
            dataOk = True
            if mode == "ai":
                s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
            else:
                print("Invalid action performed. Reason:")
                print(data.message)
        if type(data) is GameData.ServerActionValid:
            dataOk = True
            if mode == "ai":
                for ip,player in enumerate(state.players):
                    if player.name == data.lastPlayer:
                        state.playersCard[ip][data.cardHandIndex][0] = False
                        state.playersCard[ip][data.cardHandIndex][1] = False
                state.drawCard(data.lastPlayer, data.cardHandIndex, data.handLength-1)
                state.currentPlayer = data.player
            else:
                print("Action valid!")
                print("Current player: " + data.player)
        if type(data) is GameData.ServerPlayerMoveOk:
            dataOk = True
            if mode == "ai":
                for ip,player in enumerate(state.players):
                    if player.name == data.lastPlayer:
                        state.playersCard[ip][data.cardHandIndex][0] = False
                        state.playersCard[ip][data.cardHandIndex][1] = False
                state.drawCard(data.lastPlayer, data.cardHandIndex, data.handLength-1)
                state.currentPlayer = data.player
            else:
                print("Nice move!")
                print("Current player: " + data.player)
        if type(data) is GameData.ServerPlayerThunderStrike:
            dataOk = True
            if mode == "ai":
                for ip,player in enumerate(state.players):
                    if player.name == data.lastPlayer:
                        state.playersCard[ip][data.cardHandIndex][0] = False
                        state.playersCard[ip][data.cardHandIndex][1] = False
                state.drawCard(data.lastPlayer, data.cardHandIndex, data.handLength-1)
                state.currentPlayer = data.player
            else:
                print("OH NO! The Gods are unhappy with you!")
        if type(data) is GameData.ServerHintData:
            dataOk = True
            if mode == "ai":
                position = data.positions.copy()
                if data.destination == playerName:
                    for i in position:
                        if data.type == "color":
                            state.players[state.position].hand[i].color = data.value
                        elif data.type == "value":
                            state.players[state.position].hand[i].value = data.value
                for index,player in enumerate(state.players):
                    if data.destination == player.name:
                        for i in position:
                            if data.type == "color":
                                state.playersCard[index][i][1] = True
                            elif data.type == "value":
                                state.playersCard[index][i][0] = True
                state.currentPlayer = data.player
            else:
                print("Hint type: " + data.type)
                print("Player " + data.destination + " cards with value " + str(data.value) + " are:")
                for i in data.positions:
                    print("\t" + str(i))
        if type(data) is GameData.ServerInvalidDataReceived:
            dataOk = True
            if mode == "ai":
                s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
            else:
                print(data.data)
        if type(data) is GameData.ServerGameOver:
            dataOk = True
            print(data.message)
            print(data.score)
            print(data.scoreMessage)
            if mode == "ai":
                #run = False
                state = restart()
                time.sleep(1)
                s.send(GameData.ClientGetGameStateRequest(playerName).serialize())
            else:
                
                stdout.flush()
                #run = False
                print("Ready for a new game!")
        if not dataOk:
            print("Unknown or unimplemented data type: " +  str(type(data)))
        if mode == "manual":
            print("[" + playerName + " - " + status + "]: ", end="")
        stdout.flush()