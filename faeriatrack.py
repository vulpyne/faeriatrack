#!env python3

#   Copyright 2017 Vulpyne

#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


# === REQUIREMENTS:
# 1. Requires Faeria cards.csv in current directory from: https://raw.githubusercontent.com/abrakam/Faeria_Cards/master/CardExport/English/cards.csv
# 2. Requires tcpflow (1.4.5 or later ideally): https://github.com/simsong/tcpflow
# 3. Requires Python package colorama: https://pypi.python.org/pypi/colorama
# 4. Requires Python package blessings: https://pypi.python.org/pypi/blessings
# 5. Requires Python 3+.

# === NOTES:
# 1. Must be run before the game client logs in.
# 2. Will create/overwrite faeriatrack_net.log in the current directory.
# 3. Will create/overwrite faeriatrack_commands.log in the current directory.
# 4. Will create/append to logs/faeriatrack_gamelog_YYYYMMDD.log - directory must exist.

# === KNOWN ISSUES:
# 1. Does not work with resuming games.
# 2. Does not work with decks created while the tracker is running. Workaround: Edit and save the deck after creating it.
# 3. Does not respect terminal width/height so make sure the window is big enough.


import colorama
colorama.init()

import copy
import collections
import subprocess
import blessings
import time
import sys
import re
import binascii
import json
import os.path

term = blessings.Terminal()

version = '0.0.8a'


def tg(x, y):
  sys.stdout.write(term.move(x, y))


def tc():
  sys.stdout.write(term.clear())


def p(*args):
  print(*args, end = '')


def percent(amount, total):
  if total < 1:
    return 0
  return (float(amount) / float(total)) * 100.0


class Card(object):
  def __init__(self, cardid, name = None, text = None):
    self.cardid = cardid
    self.name = name
    self.text = text

  def __repr__(self):
    return '<Card({0}): name={1}, text={2}>'.format(self.cardid, self.name, self.text)


class DeckCard(object):
    def __init__(self, card, quantity):
        self.card = card
        self.quantity = quantity
        self.hquantity = 0
        self.generated = False

    def __repr__(self):
        card = self.card
        return '<DeckCard({0}): name={1}, quantity={2}>'.format(card.cardid, card.name, self.quantity)


class Deck(object):
  def __init__(self, deckid, name = None):
    self.deckid = deckid
    self.name = name
    self.cards = collections.OrderedDict()

  def cardcount(self):
    result = 0
    for dc in self.cards.values():
        result += dc.quantity
    return result

  def __repr__(self):
    return ('<Deck({0}): name={1}, cards={2}>').format(self.deckid, self.name, self.cards)



class Game(object):
  def __init__(self, deck):
    self.mypnum = None
    self.oname = None
    self.inideck = copy.deepcopy(deck)
    self.players = {}
    self.gamecards = {}
    self.turn = 0
    self.currpnum = None
    self.selfmode = '?'
    self.oppmode = '?'
    self.opprank = '?'
    self.oppgrank = '?'
    self.oppname = None

class Lands(object):
  def __init__(self):
    self.human = 0
    self.red = 0
    self.blue = 0
    self.green = 0
    self.yellow = 0
  def todict(self):
    return { 'neutral': self.human, 'red': self.red, 'blue': self.blue, 'green': self.green, 'yellow': self.yellow }
  def pretty(self):
    return ''.join('{0}{1}'.format(l[0], l[1]) for l in (('N',self.human),('R',self.red),('B',self.blue),('G',self.green),('Y',self.yellow)) if l[1] > 0)


class Player(object):
  def __init__(self, pnum, name, deck):
    self.pnum = pnum
    self.name = name
    self.health = 0
    self.handcards = 0
    self.deckcards = 0
    self.faeria = 0
    self.harvested = 0
    self.deck = deck
    self.lands = Lands()




class Tracker(object):
  handlers = {}
  def __init__(self, cards, logfp):
    self.cards = cards
    self.logfp = logfp
    self.reset()

  def reset(self):
    self.decks = {}
    self.currdeckid = None
    self.name = None
    self.game = None
    self.dirty = False

  def feed(self, line):
    parts = line.strip().split('|')
    if len(parts) == 1:
      return
    seqnum = parts[0]
    cmd = parts[1]
    args = parts[2:]
    handler = self.handlers.get(cmd)
    if handler:
      handler(self, seqnum, cmd, args)


  def toArgDict(self, args):
    return dict(a.split(':', 1) for a in args if ':' in a)


  modetranslate = { 'COMPETITIVE': 'R', 'CASUAL': 'C' }
  def showStatus(self):
    self.dirty = False
    if not self.game:
      return
    game = self.game
    if game.currpnum is None:
      return
    currplayer = game.players[game.currpnum]
    tc()
    smode = Tracker.modetranslate.get(game.selfmode, game.selfmode)
    omode = Tracker.modetranslate.get(game.oppmode, game.oppmode)
    p('#{bold}{turn:d}{norm} - Playing({selfmode}v{oppmode}): {bold}{currname}{norm}'
      .format(turn = game.turn, currname = currplayer.name,
              bold = term.bold, norm = term.normal, oppmode = omode, selfmode = smode))
    maxdlen = 0
    halfwidth = term.width / 2
    maxnamelen = int(halfwidth - 10)
    for pnum in range(0,2):
      player = game.players[pnum]
      if pnum == game.mypnum:
          unknown = player.deckcards - player.deck.cardcount()
      else:
          unknown = player.deckcards
      y = (int(halfwidth) + 2) * pnum
      tg(1, y)
      if pnum == game.currpnum:
          p(term.bold_reverse)
      p('{0}'.format(player.name))
      p(term.normal)
      tg(2, y)
      p('HP:{bold}{hp: <2d}{norm} / MP:{bold}{mp: <2d}{norm} / Eco:{bold}{eco: <3d}{norm}{pos}D:{bold}{deck: <2d}{norm} / H:{bold}{hand: <2d}{norm} / L:{lands}'.format(
          hp = player.health,
          mp = player.faeria,
          eco = player.harvested,
          deck = player.deckcards,
          hand = player.handcards,
          bold = term.bold,
          norm = term.normal,
          pos = term.move(3, y),
          lands = player.lands.pretty()
      ))
      pdeck = player.deck
      if pdeck == None:
          continue
      maxdlen = max(len(pdeck.cards), maxdlen)
      cnum = 0
      for dc in player.deck.cards.values():
        if pnum == game.mypnum:
          percdraw = int(percent(dc.quantity, player.deckcards))
          if percdraw >= 100:
            percdraw = 'NX'
          else:
            percdraw = '{0: >2d}'.format(percdraw)
        else:
            if dc.quantity > 3:
              percdraw = '??'
            else:
              percdraw = int(percent(3 - dc.quantity, player.deckcards))
              if percdraw >= 100:
                percdraw = 'NX'
              else:
                percdraw = '{0: >2d}'.format(percdraw)
        tg(4 + cnum, y)
        if dc.quantity > 0:
          p(term.bold)
        elif not dc.generated:
          p(term.bright_red_underline)
        p('{0: >2d}'.format(dc.quantity + dc.hquantity))
        p(term.normal)
        p('x')
        p('{percdraw}{bold}%{norm} '.format(percdraw = percdraw, bold = term.bold, norm = term.normal))
        if dc.hquantity > 0:
          p(term.reverse)
        if dc.generated:
          p(term.underline)
        cardname = dc.card.name
        if ',' in cardname:
          prefix,rest = cardname.split(',', 1)
          rest = rest.strip()
          abbrevrest = ''.join(w.strip()[:1] for w in rest.split(None))
          cardname = ', '.join((prefix, abbrevrest))
        p('{0}'.format(cardname[:maxnamelen]))
        p(term.normal)
        cnum += 1
      if unknown > 0:
        tg(4 + cnum, y)
        p('{bold}{quantity: >2d}{norm}:     <{ita}Unknown{norm}>'
          .format(quantity = unknown, bold = term.bold, norm = term.normal, ita = term.italic))
    tg(6 + maxdlen, 0)
    sys.stdout.flush()


  def handler_playerstate(self, seqnum, cmd, args):
    pnum,health,faeria,handcards,deckcards,wut = args
    pnum = int(pnum)
    health = int(health)
    faeria = int(faeria)
    handcards = int(handcards)
    deckcards = int(deckcards)
    if not self.game:
      return
    player = self.game.players[pnum]
    player.health = health
    player.handcards = handcards
    player.deckcards = deckcards
    self.dirty = True



  def handler_clearroom(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    dr = argdict.get('dr')
    if not dr:
      return
    if dr[:4] != 'deck':
      return
    deckid = int(dr[4:])
    deck = self.decks.get(deckid)
    if not deck:
      raise ValueError('Tracker:clearroom: Attempt to clear cards for unknown deckid {0}'.format(deckid))
    deck.cards = collections.OrderedDict()


  def handler_set(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    t = argdict.get('t')
    dr = argdict.get('dr')
    if t == 'ACCOUNT':
      pickeddeckid = argdict.get('pickedDeckId')
      if pickeddeckid:
        self.currdeckid = int(pickeddeckid)
        # print('Set deckid: ', pickeddeckid)
      return
    elif t == 'DECK':
      name = argdict.get('name')
      did = argdict.get('id')
      if name is None or did is None:
        return
      deckid = int(did)
      deck = self.decks.get(deckid)
      if deck is None:
        raise ValueError('Tracker:clearroom: Attempt to rename unknown deckid {0} to {1}'.format(deckid, name))
      deck.name = name
      return
    dr = argdict.get('dr')


  def handler_harvestfaeria(self, seqnum, cmd, args):
    gcid,posid,amount,pnum = args
    gcid = int(gcid)
    posid = int(posid)
    amount = int(amount)
    pnum = int(pnum)
    if not self.game:
      return
    player = self.game.players[pnum]
    player.harvested += amount


  def handler_iam(self, seqnum, cmd, args):
    pnum = int(args[0])
    if not self.game:
      return
    game = self.game
    game.mypnum = pnum
    if pnum == 0:
      opnum = 1
    elif pnum == 1:
      opnum = 0
    else:
      raise ValueError('Tracker:iam: Unexpected player number {0}'.format(pnum))
    game.players[pnum] = Player(pnum, self.name, copy.deepcopy(game.inideck))
    if game.opprank == '0' and game.oppgrank == '0':
      otype = 'CPU'
    elif game.oppgrank != '0':
      otype = 'G{0}'.format(game.oppgrank)
    elif game.opprank != '0':
      otype = 'R{0}'.format(game.opprank)
    else:
      otype = '?'
    oname = '{0}({1})'.format(self.game.oppname, otype)
    game.players[opnum] = Player(opnum, oname, Deck(0, 'Opponent'))
    if pnum == 0:
      game.currpnum = 0
    else:
      game.currpnum = 1
    self.dirty = True


  def handler_comeintoplay(self, seqnum, cmd, args):
    wut,gcid,pnum = args
    gcid = int(gcid)
    pnum = int(pnum)
    if not self.game:
      return
    gcards = self.game.gamecards
    gc = gcards.get(gcid)
    if not gc:
      return
      raise ValueError('Tracker:comeintoplay: Unknown game card id {0}'.format(gcid))
    gcp,gct,gcc = gc
    #print('ComeIntoPlay p{0}: {1}'.format(pnum, gcc.name))



  def handler_payfaeria(self, seqnum, cmd, args):
    wut,pnum,amount = args
    pnum = int(pnum)
    amount = int(amount)
    if amount == 0:
      return
    if not self.game:
      return
    player = self.game.players[pnum]
    player.faeria -= amount
    #print('PayFaeria: p{0}: -{1}'.format(pnum, amount))
    self.dirty = True



  def handler_faeriagain(self, seqnum, cmd, args):
    wut,pnum,amount = args
    pnum = int(pnum)
    amount = int(amount)
    if amount == 0:
      return
    if not self.game:
      return
    player = self.game.players[pnum]
    player.faeria += amount
    #print('FaeriaGain: p{0}: +{1}'.format(pnum, amount))
    self.dirty = True


  def handler_newturn(self, seqnum, cmd, args):
    pnum,tnum = args
    pnum = int(pnum)
    tnum = int(tnum)
    if not self.game:
      return
    self.game.turn = tnum
    self.game.currpnum = pnum
    self.dirty = True


  def handler_zonemove(self, seqnum, cmd, args):
    if not self.game:
      return
    game = self.game
    gcards = game.gamecards
    wut1,gcid,fromn,fromp,ton,top = args
    fromp = int(fromp)
    top = int(top)
    gcid = int(gcid)
    gc = gcards.get(gcid)
    if not gc:
      return
      raise ValueError('Tracker:zonemove: Unknown game card id {0}'.format(gcid))
    gcp,gct,gcc = gc
    #print('ZoneMove {1}({2}) -> {3}({4}): o={0} - {5} ({6})'.format(gcp, fromn, fromp, ton, top, gcc.name, gcc.cardid))
    fplayer = game.players.get(fromp)
    tplayer = game.players.get(top)
    if fromp == game.mypnum:
      if top == fromp:
        dc = fplayer.deck.cards.get(gcc.cardid)
        if not dc:
          dc = DeckCard(gcc, 0)
          dc.generated = True
          tplayer.deck.cards[gcc.cardid] = dc
        if fromn == 'deck':
          dc.quantity -= 1
        elif fromn == 'hand':
          dc.hquantity -= 1
        if ton == 'deck':
          dc.quantity += 1
        elif ton == 'hand':
          dc.hquantity += 1
        dc.quantity = max(0, dc.quantity)
        dc.hquantity = max(0, dc.hquantity)
    elif top == game.mypnum:
      if fromp == -1:
        if ton in ('deck', 'hand'):
          dc = tplayer.deck.cards.get(gcc.cardid)
          if not dc:
            dc = DeckCard(gcc, 0)
            dc.generated = True
            tplayer.deck.cards[gcc.cardid] = dc
          if ton == 'deck':
            dc.quantity += 1
          elif ton == 'hand':
            dc.hquantity += 1
      else:
        raise ValueError('Tracker:zonemove: I do not know how to handle move between players.')
    elif fromp in game.players:
      if fromn == 'hand':
        dc = fplayer.deck.cards.get(gcc.cardid)
        if not dc:
          fplayer.deck.cards[gcc.cardid] = DeckCard(gcc, 1)
        else:
          dc.quantity += 1
    self.dirty = True


  def handler_creategamecard(self, seqnum, cmd, args):
    newid,cardid,pnum,typ = args[:4]
    wuts = args[4:]
    newid = int(newid)
    cardid = int(cardid)
    card = self.cards.get(cardid)
    if not card:
      return
      card = Card(cardid, typ, typ)
    if not self.game:
      return
    self.game.gamecards[newid] = (pnum, typ, card)
    #print('creategamecard: p{3}: {0} = ({4}){1} ({2}) -- '.format(newid, card.name, typ, pnum, card.cardid))


  def handler_startgame(self, seqnum, cmd, args):
    print('StartGame')


  def handler_stopgame(self, seqnum, cmd, args):
    self.game = None
    print('StopGame')


  def handler_setquantity(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    dr = argdict.get('dr')
    if not dr:
      return
    if dr[:4] != 'deck' or argdict.get('t') not in('CARD', 'GOLD_CARD'):
      return
    deckid = int(dr[4:])
    deck = self.decks.get(deckid)
    if not deck:
      raise ValueError('Tracker:setquantity: Attempt to set cards for unknown deckid {0}'.format(deckid))
    dcards = deck.cards
    for cdef in args[2:]:
      cardid,quantity = cdef.split(':')
      cardid = int(cardid)
      quantity = int(quantity)
      card = self.cards.get(cardid)
      if not card:
        raise ValueError('Tracker:setquantity: Deck definition with unknown cardid {0}'.format(cardid))
      dc = dcards.get(cardid)
      if dc is None:
        dcards[cardid] = DeckCard(card, quantity)
      else:
        dc.quantity += quantity
    #print('setquantity:deck: ', deck)




  def handler_sset(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    dr = argdict.get('dr')
    if not dr:
      return
    if dr == 'you':
      deckid = argdict.get('pickedDeckId')
      if deckid:
        #print('sset: deckid: ', deckid)
        self.currdeckid = int(deckid)
      name = argdict.get('userName')
      if name:
        self.name = name
    elif dr == 'decks' and argdict.get('t') == 'DECK':
      dname = argdict.get('name')
      did = argdict.get('id')
      if not dname or not did:
        raise ValueError('Tracker:sset: Expected name and id')
      did = int(did)
      deck = Deck(did, dname)
      self.decks[did] = deck
    elif dr == 'gameMembers':
      if self.game:
        raise ValueError('Tracker:startgame: Got new game while game already in progress!')
      if not self.currdeckid:
        raise ValueError('Tracker:startgame: Got new game with no deck id set!')
      gamedeck = self.decks.get(self.currdeckid)
      if not gamedeck:
        raise ValueError('Tracker:startgame: Got new game but could not find currdeckid {0} in our decks!'.format(self.currdeckid))
      self.game = Game(gamedeck)
      game = self.game
      game.opprank = argdict.get('constructedRank') or '?'
      game.oppgrank = argdict.get('constructedGodRank') or '?'
      game.oppname = argdict.get('userName') or '*Opponent'
    #print('SSET: ', self.game, argdict)


  def handler_welcome(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    source = argdict.get('source')
    if source is None:
      return
    if source == 'WorldServer':
      print('* Reset!')
      self.reset()


  def handler_setrankedmode(self, seqnum, cmd, args):
    argdict = self.toArgDict(args)
    if self.game is None:
      raise ValueError('setrankedmode: Game not set.')
    game = self.game
    game.oppmode = argdict.get('him')
    game.selfmode = argdict.get('me')


  def handler_victory(self, seqnum, cmd, args):
    if self.game is None:
      raise ValueError('victory: Game not set.')
    game = self.game
    wnum,reason = args
    winrar = int(wnum) == (game.mypnum + 1)
    print('Game outcome vs {2}: {0} - Reason: {1}'.format('Won' if winrar else 'Loss', reason, game.oppname))
    onum = 1 if game.mypnum == 0 else 0
    opp = game.players[onum]
    ocards = list((c.quantity, c.card.cardid, c.card.name) for c in opp.deck.cards.values() if not c.generated)
    me = game.players[game.mypnum]
    mcards = list((c.quantity, c.card.cardid, c.card.name) for c in me.deck.cards.values() if not c.generated)
    outcome = {
      'stamp': time.strftime('%Y%m%dT%H%M%S'),
      'first': game.mypnum == 0,
      'victory': winrar,
      'endreason': reason,
      'turn': game.turn,
      'opponent': {
        'mode': game.oppmode,
        'rank': game.opprank,
        'grank': game.oppgrank,
        'name': game.oppname,
        'health': opp.health,
        'handcards': opp.handcards,
        'deckcards': opp.deckcards,
        'faeria': opp.faeria,
        'eco': opp.harvested,
        'deck': ocards,
        'lands': opp.lands.todict()
        },
      'me': {
        'mode': game.selfmode,
        'health': me.health,
        'handcards': me.handcards,
        'deckcards': me.deckcards,
        'faeria': me.faeria,
        'eco': me.harvested,
        'deckname': me.deck.name,
        'deck': mcards,
        'lands': me.lands.todict()
        },
      }
    j = json.dumps(outcome)
    logfp = self.logfp
    logfp.write(j)
    logfp.write('\n')
    logfp.flush()


  def handler_createtokenland(self, seqnum, cmd, args):
    wut1,wut2,wut3,ltype = args
    if ltype not in ('red','blue','green','yellow','human'):
      raise ValueError('createtokenland: Unknown land type: {0}'.format(ltype))
    lands = self.game.players[self.game.currpnum].lands
    currval = getattr(lands, ltype)
    setattr(lands, ltype, currval + 1)

  handlers['$sset'] = handler_sset
  handlers['$setQuantity'] = handler_setquantity
  handlers['$startGame'] = handler_startgame
  handlers['$stopGame'] = handler_stopgame
  handlers['*createGameCard'] = handler_creategamecard
  handlers['#ZoneMove'] = handler_zonemove
  handlers['~newTurn'] = handler_newturn
  handlers['#FaeriaGain'] = handler_faeriagain
  handlers['#PayFaeria'] = handler_payfaeria
  handlers['#ComeIntoPlay'] = handler_comeintoplay
  handlers['~iam'] = handler_iam
  handlers['#HarvestFaeria'] = handler_harvestfaeria
  handlers['$set'] = handler_set
  handlers['$clearRoom'] = handler_clearroom
  handlers['~playerState'] = handler_playerstate
  handlers['$welcome'] = handler_welcome
  handlers['$setRankedMode'] = handler_setrankedmode
  handlers['$victory'] = handler_victory
  handlers['#CreateTokenLand'] = handler_createtokenland





def loadCards(fn):
  result = {}
  with open(fn, 'r') as fp:
    for line in fp:
      keypart,val = line.split(';', 1)
      val = val.strip()
      cardid,deftype = keypart.split('.', 1)
      cardid = int(cardid)
      card = result.get(cardid)
      if not card:
        card = Card(cardid)
        result[cardid] = card
      if deftype == 'name':
        card.name = val
      elif deftype == 'text':
        card.text = val
      else:
        raise ValueError('Unknown card def type: {1}'.format(deftype))
  return result


def dumpCards(cards):
  for cardid in cards:
    print(cards[cardid])


re_tf_initial = re.compile(r'^(\d+)T(\d+\.\d+\.\d+\.\d+)\.(\d+)-(\d+\.\d+\.\d+\.\d+)\.(\d+):\s*$')
re_tf_data = re.compile(r'^[0-9a-f]+: ((?:[0-9a-f]{2,4} )+).*$')
def runTCPFlow(cards, fp):
  glogfp = open(os.path.join('logs', 'faeriatrack_gamelog_{0}.log'.format(time.strftime('%Y%m%d'))), 'a')
  logfp = open('faeriatrack_net.log', 'w')
  clogfp = open('faeriatrack_commands.log', 'w')
  tracker = Tracker(cards, glogfp)
  delay = None if fp is sys.stdin else 0.3
  dbuffer = { 'I': [], 'O': [] }
  for line in fp:
    logfp.write(line)
    logfp.flush()
    line = line.strip()
    result = re_tf_initial.match(line)
    if result is None:
      raise ValueError('Fail: Could not parse initial part.')
    stamp,srcip,srcport,dstip,dstport = result.groups()
    direction = 'I' if srcport in ('02201','02202') else 'O'
    if direction == 'I':
      stype = 'W' if srcport == '02201' else 'G'
    else:
      stype = '?'
    dline = None
    data = dbuffer[direction]
    while True:
      dline = fp.readline()
      logfp.write(dline)
      logfp.flush()
      dline = dline.strip()
      if dline is None or dline == '':
        break
      result = re_tf_data.match(dline)
      if result is None:
        raise ValueError('Fail: Could not parse data part.')
      hexd = ''.join(c for c in result.groups()[0] if c != ' ')
      data.append(binascii.unhexlify(hexd).decode('ascii'))
    if data[-1][-1] != '\n':
      continue
    dbuffer[direction] = []
    if direction != 'I':
      continue
    data = ''.join(data)
    commands = data.split('\n')
    for command in commands:
      if command == '':
        continue
      clogfp.write(stype + ': ')
      clogfp.write(command)
      clogfp.write('\n')
      clogfp.flush()
      tracker.feed(command)
    if tracker.dirty:
      tracker.showStatus()
      if delay is not None:
        time.sleep(delay)



example = '''sudo tcpflow -E tcpdemux -p -c -D -Ft -Fc -S enable_report=NO tcp src portrange 2201-2202 | python3 faeriatrack.py tcpflow'''

def main():
  print(term.bold('* Faeria deck tracker v{0} by Vulpyne <vulpyne@gmail.com>'.format(version)))
  cardsname = 'cards.csv'
  print('- Loading cards from file: {0}'.format(cardsname))
  cards = loadCards(cardsname)
  print('- Loaded {0} card{1}'.format(len(cards), 's' if len(cards) != 1 else ''))
  mode = 'help'
  if len(sys.argv) > 1:
    mode = sys.argv[1]
    print('- Running with mode: {0}\n'.format(mode))
  if mode == 'help':
    print('Example: {0}'.format(example))
  elif mode == 'tcpflow':
    runTCPFlow(cards, sys.stdin)
  else:
    print('Unknown mode.')

if __name__ == '__main__':
  main()
