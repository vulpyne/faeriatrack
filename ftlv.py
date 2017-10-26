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


import json
import sys

def prettylands(l):
  if l is None:
    return '?'
  return ''.join('{0}{1}'.format(l[0], l[1]) for l in (('N',l['neutral']),('R',l['red']),('B',l['blue']),('G',l['green']),('Y',l['yellow'])) if l[1] > 0)


modetranslate = { 'COMPETITIVE': 'R', 'CASUAL': 'C' }
fmt = '{stamp: <13s}  {victory: <3s}  {first: <4s}  {mode: >4} {oeco: >5}  {meco: >5}  {olands: <14s}  {mlands: <14s}  {dname: <15s}  {orank: <5s}  {oname: <20s}'
fmtshow = { 'stamp': '** Timestamp', 'victory': 'W/L', 'first': '1st', 'mode': 'mode', 'oeco': 'oeco', 'meco': 'meco', 'mlands': 'mlands', 'olands': 'olands', 'dname': 'deckname', 'orank': 'orank', 'oname': 'oname' }
def main():
  ln = 0
  for l in sys.stdin:
    if ln % 10 == 0:
      if ln != 0:
        print('')
      print(fmt.format(**fmtshow))
    ln = ln + 1
    le = json.loads(l)
    if le['opponent']['grank'] != '0':
      orank = '#{0}'.format(le['opponent']['grank'])
    else:
      orank = 'R{0}'.format(le['opponent']['rank'])
    oname = le['opponent']['name']
    args = {
      'stamp': le['stamp'][:13],
      'victory': 'W' if le['victory'] else 'L',
      'first': 'F' if le['first'] else 'S',
      'oeco': le['opponent']['eco'],
      'meco': le['me']['eco'],
      'olands': prettylands(le['opponent'].get('lands')),
      'mlands': prettylands(le['me'].get('lands')),
      'dname': le['me']['deckname'][:15],
      'mode': '{0}v{1}'.format(modetranslate.get(le['me']['mode'], '?'), modetranslate.get(le['opponent']['mode'], '?')),
      'orank': orank,
      'oname': oname[:20],
    }
    print(fmt.format(**args))

if __name__ == '__main__':
  main()
