from game import *
from enum import Enum
import numpy as np
import pandas as pd

class State(object):
    """Object that represents a state of the game from a specific player point of view"""
    def __init__(self, playerName) -> None:
        super().__init__()
        self.colorList = np.array(["red","yellow","green","blue","white"])
        self.numberCards = np.array([3,2,2,2,1])
        self.currentPlayer = 0
        self.playerName = playerName
        self.players = []
        self.playersCard = []
        self.tableCards = {}
        self.discardPile = []
        self.usedNoteTokens = 0
        self.usedStormTokens = 0
        self.cardsToDraw = 50
        self.handSize = 5
        self.cards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.remainingCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.hotCards_ = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.usefullCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.uselessCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.nbTurns = 0
        self.updated = False

    def playCard(self, player, value, color, position):
        """Play a card with given value and color from given player"""
        for p in self.players:
            if p.name == player:
                if len(self.tableCards[color]) == (value-1):
                    self.tableCards[color].append(Card(None, value, color))
                    self.drawCard(player, position, len(p.hand)-1)
                else:
                    self.discardPile.append(Card(None, value, color))
                    self.drawCard(player, position, len(p.hand)-1)
                    self.usedStormTokens += 1
        self.updateCards()

    def discardCard(self, player, value, color, position):
        """Discard a card with given value and color from given player"""
        for p in self.players:
            if p.name == player:
                self.discardPile.append(Card(None, value, color))
                self.drawCard(player, position, len(p.hand)-1)
        self.usedNoteTokens -= 1
        self.updateCards()

    def hintCard(self, destination, type, value, position):
        """Hint a player with given type and value"""
        for ip, p in enumerate(self.players):
            if p.name == destination:
                if p.name == self.playerName:
                    # todo => manage if someone is hinting us
                    if type == "color":
                        for i in position:
                            p.hand[i].color = value
                    elif type == "value":
                        for i in position:
                            p.hand[i].value = value
                else:
                    if type == "color":
                        for i in position:
                            self.playersCard[ip][i][1] = True
                    elif type == "value":
                        for i in position:
                            self.playersCard[ip][i][0] = True
        self.usedNoteTokens += 1
        self.updateCards()

    def addPlayers(self, players):
        """
        Add given players to the game.
        Called once at the start.
        """
        self.handSize = 5 if len(players) < 4 else 4
        for ip, player in enumerate(players):
            self.players.append(Player(player))
            self.playersCard.append([[False,False] for _ in range(self.handSize)])
            if player == self.playerName:
                self.position = ip
                self.fillHand(ip)

    def drawCard(self, player, cardIndex, handLength):
        """
        Simulate the given player drawing a card.
        As it is the from the player point of view, no assumption are made on the card drawn.
        The knowledge of the card at given cardIndex is reset. (Card that has been played or discarded)
        """
        for ip, p in enumerate(self.players):
            if p.name == player and p.name == self.playerName:
                for i in range(cardIndex, handLength):
                    self.players[self.position].hand[i] = self.players[self.position].hand[i+1]
                    self.playersCard[self.position][i][0] = self.playersCard[self.position][i+1][0]
                    self.playersCard[self.position][i][1] = self.playersCard[self.position][i+1][1]
                self.playersCard[self.position][handLength][0] = False
                self.playersCard[self.position][handLength][1] = False
                if self.cardsToDraw > 0:
                    self.players[self.position].hand[handLength] = Card(None, None, None)
                    self.cardsToDraw -= 1
                else:
                    self.players[self.position].hand.pop(handLength)
            elif p.name == player:
                for i in range(cardIndex, handLength):
                    self.playersCard[ip][i][0] = self.playersCard[ip][i+1][0]
                    self.playersCard[ip][i][1] = self.playersCard[ip][i+1][1]
                self.playersCard[ip][handLength][0] = False
                self.playersCard[ip][handLength][1] = False

    def fillHand(self, position):
        """Simulate player drawing."""
        for _ in range(self.handSize):
            self.players[position].hand.append(Card(None, None, None))
            self.cardsToDraw -= 1

    def updateCards(self):
        """Update several array counting multiple types of things"""
        self.cards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.remainingCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.hotCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.hotCards.loc[4,:] = 1
        self.usefullCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.uselessCards = pd.DataFrame(np.zeros((5,5)),columns=self.colorList,dtype='i4')
        self.cardsToDraw = 50
        
        for color in self.colorList:
            self.remainingCards[color] = self.numberCards
        
        for player in self.players:
            for card in player.hand:
                self.cardsToDraw -= 1
                if (card.color and card.value) != None:
                    self.cards[card.color][card.value-1] += 1
        for pile in self.tableCards:
            for card in self.tableCards[pile]:
                self.cardsToDraw -= 1
                self.cards[card.color][card.value-1] += 1
        for card in self.discardPile:
            self.cardsToDraw -= 1
            self.cards[card.color][card.value-1] += 1
            self.remainingCards[card.color][card.value-1] -= 1
            
        for pile in self.tableCards:
            if len(self.tableCards[pile]) < 5:
                self.hotCards[pile][len(self.tableCards[pile])] = 1
                self.usefullCards[pile][len(self.tableCards[pile]):] = 1
                if len(self.tableCards[pile]) > 0:
                    self.uselessCards[pile][:len(self.tableCards[pile])] = 1
            else:
                self.uselessCards[pile][:] = 1
        
        for color in self.remainingCards:
            for ic, card in enumerate(self.remainingCards[color]):
                if card == 1:
                    self.hotCards[color][ic] = 1

    def toString(self):
        print("Current player: " + self.currentPlayer)
        print("Player hands: ")
        for p in self.players:
            print(p.toClientString())
        print("Table cards: ")
        for pos in self.tableCards:
            print(pos + ": [ ")
            for c in self.tableCards[pos]:
                print(c.toClientString() + " ")
            print("]")
        print("Discard pile: ")
        for c in self.discardPile:
            print("\t" + c.toClientString())            
        print("Note tokens used: " + str(self.usedNoteTokens) + "/8")
        print("Storm tokens used: " + str(self.usedStormTokens) + "/3")

    def toLog(self):
        log = "\n"
        log = log+"Current player: " + self.currentPlayer + "\n"
        for i,p in enumerate(self.players):
            log = log+p.toClientString()+"\n"
            log = log+"Hinted cards: \n"
            for c in self.playersCard[i]:
                log = log+"Value: " + str(c[0]) + "; Color : " + str(c[1]) + "\n"
        log = log+"\n"+"Table cards: "
        for pos in self.tableCards:
            log = log+"\n"+pos + ": [ "
            for c in self.tableCards[pos]:
                log = log+"\n"+c.toClientString() + " "
            log = log+"\n"+"]"
        log = log+"\n"+"Discard pile: "
        for c in self.discardPile:
            log = log+"\n"+"\t" + c.toClientString()
        log = log+"\n"+"Known cards: "
        for color in self.cards:
            log = log+"\n"+color + ": [ "
            for card in self.cards[color]:
                log = log+" "+ str(card) + " "
            log = log+" ]"
        log = log+"\n"+"Remaining cards: "
        for color in self.remainingCards:
            log = log+"\n"+color + ": [ "
            for card in self.remainingCards[color]:
                log = log+" "+ str(card) + " "
            log = log+" ]"
        log = log+"\n"+"Hot cards: "
        for color in self.hotCards:
            log = log+"\n"+color + ": [ "
            for card in self.hotCards[color]:
                log = log+" "+ str(card) + " "
            log = log+" ]"
        # log = log+"\n"+"Usefull cards: "
        # for color in self.usefullCards:
        #     log = log+"\n"+color + ": [ "
        #     for card in self.usefullCards[color]:
        #         log = log+" "+ str(card) + " "
        #     log = log+" ]"
        # log = log+"\n"+"Useless cards: "
        # for color in self.uselessCards:
        #     log = log+"\n"+color + ": [ "
        #     for card in self.uselessCards[color]:
        #         log = log+" "+ str(card) + " "
        #     log = log+" ]"
        log = log+"\n"+"Note tokens used: " + str(self.usedNoteTokens) + "/8"
        log = log+"\n"+"Storm tokens used: " + str(self.usedStormTokens) + "/3"
        return log
    
    def checkFinishedFirework(self):
        """Check if a firework has been completed"""
        finishedFirework = 0
        for pile in self.tableCards:
            if len(self.tableCards[pile]) == 5:
                finishedFirework = finishedFirework+1
        return finishedFirework
    
    def checkNumberOfCards(self):
        """Check the number of cards placed on the table"""
        cards = 0
        for pile in self.tableCards:
            cards = cards + len(self.tableCards[pile])
        return cards

    def checkHintedCards(self):
        """Check the number of cards hinted"""
        fullHintedCard = 0
        hintedCard = 0
        for player in self.playersCard:
            for card in player:
                if card[0] and card[1]:
                    fullHintedCard += 1
                elif card[0] or card[1]:
                    hintedCard += 1
        return fullHintedCard, hintedCard

    def checkNumberCards(self):
        """Check the cards that have been drawn and that are either on the hands, on the table or in the discard pile"""
        known = 0
        for ip, player in enumerate(self.players):
            for ic, card in enumerate(player.hand):
                if self.playersCard[ip][ic][0]:
                    known += 1
        return known

    def checkHotCards(self):
        """Check the number of hot cards discovered"""
        known = 0
        partiallyKnown = 0
        discarded = 0
        for ip, player in enumerate(self.players):
            for ic, card in enumerate(player.hand):
                if card.color != None and card.value != None:
                    if self.hotCards[card.color][card.value-1]:
                        if self.playersCard[ip][ic][0] and self.playersCard[ip][ic][1]:
                            known += 1
                        elif self.playersCard[ip][ic][0] or self.playersCard[ip][ic][1]:
                            partiallyKnown += 1

        for color in self.hotCards:
            for ic, card in enumerate(self.hotCards[color]):
                if card:
                    for discardedCard in self.discardPile:
                        if discardedCard.color == color and ic+1 == discardedCard.value:
                            discarded += 1
        return known, partiallyKnown, discarded

    def checkUsefullCards(self):
        """Check the number of usefull cards discovered"""
        known = 0
        partiallyKnown = 0
        discarded = 0
        for ip, player in enumerate(self.players):
            for ic, card in enumerate(player.hand):
                if card.color != None and card.value != None:
                    if self.usefullCards[card.color][card.value-1]:
                        if self.playersCard[ip][ic][0] and self.playersCard[ip][ic][1]:
                            known += 1
                        elif self.playersCard[ip][ic][0] or self.playersCard[ip][ic][1]:
                            partiallyKnown += 1

        for color in self.usefullCards:
            for ic, card in enumerate(self.usefullCards[color]):
                if card:
                    for discardedCard in self.discardPile:
                        if discardedCard.color == color and ic+1 == discardedCard.value:
                            discarded += 1
        return known, partiallyKnown, discarded

    def checkUselessCards(self):
        """Check the number of usesless cards discovered"""
        known = 0
        partiallyKnown = 0
        discarded = 0
        for ip, player in enumerate(self.players):
            for ic, card in enumerate(player.hand):
                if card.color != None and card.value != None:
                    if self.uselessCards[card.color][card.value-1]:
                        if self.playersCard[ip][ic][0] and self.playersCard[ip][ic][1]:
                            known += 1
                        elif self.playersCard[ip][ic][0] or self.playersCard[ip][ic][1]:
                            partiallyKnown += 1

        for color in self.uselessCards:
            for ic, card in enumerate(self.uselessCards[color]):
                if card:
                    for discardedCard in self.discardPile:
                        if discardedCard.color == color and ic+1 == discardedCard.value:
                            discarded += 1
        return known, partiallyKnown, discarded