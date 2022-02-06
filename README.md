# Computational Intelligence 2021-2022

Exam of computational intelligence 2021 - 2022. It requires teaching the client to play the game of Hanabi (rules can be found [here](https://www.spillehulen.dk/media/102616/hanabi-card-game-rules.pdf)).

## Server

The server accepts passing objects provided in GameData.py back and forth to the clients.
Each object has a ```serialize()``` and a ```deserialize(data: str)``` method that must be used to pass the data between server and client.

Watch out! I'd suggest to keep everything in the same folder, since serialization looks dependent on the import path (thanks Paolo Rabino for letting me know).

Server closes when no client is connected.

To start the server:

```bash
python server.py <minNumPlayers>
```

Arguments:

+ minNumPlayers, __optional__: game does not start until a minimum number of player has been reached. Default = 2


Commands for server:

+ exit: exit from the server

## Client

To start the client:

```bash
python client.py <-h> <--ip IP> <--port PORT> (<--manual> | <--ai>) <--name NAME> <--debug>
```

Arguments:

+ ip: IP address of the server (for localhost: 127.0.0.1)
+ port: server TCP port (default: 1024)
+ manual OR ai: mode of the player (default: ai)
+ name: the name of the player (default: "default_name")
+ debug: creates log for debug purpose

Commands for client in manual mode:

+ exit: exit from the game
+ ready: set your status to ready (lobby only)
+ show: show cards
+ hint \<type> \<destinatary>:
  + type: 'color' or 'value'
  + destinatary: name of the person you want to ask the hint to
+ discard \<num>: discard the card *num* (\[0-4]) from your hand


## Strategy

The strategy of the agent is based on the function `reward` that evaluates a given state.
At each turn, the agent will simulate every play possible among play, discard and hint actions. The action with the best expected reward will be picked.

### Reward


## Results

After playing 100 games with the agent in different configurations, the results are :
+ 2 players : 14.69
+ 3 players : 15.72
+ 4 players : 15.14
+ 5 players : 14.20