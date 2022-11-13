#!/usr/bin/env python3
import numpy as np
import argparse
import binascii
import time
from collections import defaultdict

import cereal.messaging as messaging
from selfdrive.debug.can_table import can_table
from tools.lib.logreader import logreader_from_route_or_segment

RED = '\033[91m'
CLEAR = '\033[0m'

MIN_MSGS_CHECK_MULTIPLEX = 10


def check_multiplexed(first_bytes):
  # stupid simple, doesn't catch any msgs with jumps in ids
  aset = set(np.diff(first_bytes))
  return len(aset) == 1 or aset == {1, -max(first_bytes)}


def update(msgs, bus, dat, low_to_high, high_to_low, multiplexed, msg_count, quiet=False):
  for x in msgs:
    if x.which() != 'can':
      continue

    for msg in x.can:
      if msg.src == bus:
        dat[msg.address] = msg.dat

        # wait until we check enough messages
        multiplexed[msg.address].append(msg.dat[0])
        if len(multiplexed[msg.address]) <= MIN_MSGS_CHECK_MULTIPLEX:
          continue

        # Do diffing with address + multiplex id as key if msg is likely multiplexed
        is_multiplexed = check_multiplexed(multiplexed[msg.address])
        multiplex_id = msg.dat[0] if is_multiplexed else 0

        i = int.from_bytes(msg.dat, byteorder='big')
        l_h = low_to_high[msg.address][multiplex_id]
        h_l = high_to_low[msg.address][multiplex_id]

        change = None
        if (i | l_h) != l_h:
          low_to_high[msg.address][multiplex_id] = i | l_h
          change = "+"

        if (~i | h_l) != h_l:
          high_to_low[msg.address][multiplex_id] = ~i | h_l
          change = "-"

        if change and not quiet:
          m_id_txt = f":m{hex(multiplex_id)[2:]}" if is_multiplexed else ""
          print(f"{time.monotonic():.2f}\t{hex(msg.address)}{m_id_txt} ({msg.address}{m_id_txt})\t{change}{binascii.hexlify(msg.dat)}")


def can_printer(bus=0, init_msgs=None, new_msgs=None, table=False, multiplex=False):
  logcan = messaging.sub_sock('can', timeout=10)

  dat = defaultdict(int)
  low_to_high = defaultdict(lambda: defaultdict(int))
  high_to_low = defaultdict(lambda: defaultdict(int))
  multiplexed = defaultdict(list)

  if init_msgs is not None:
    update(init_msgs, bus, dat, low_to_high, high_to_low, multiplexed, quiet=True)

  low_to_high_init = low_to_high.copy()
  high_to_low_init = high_to_low.copy()

  if new_msgs is not None:
    update(new_msgs, bus, dat, low_to_high, high_to_low)
  else:
    # Live mode
    print(f"Waiting for messages on bus {bus}")
    try:
      while 1:
        can_recv = messaging.drain_sock(logcan)
        update(can_recv, bus, dat, low_to_high, high_to_low, multiplexed)
        time.sleep(0.02)
    except KeyboardInterrupt:
      pass

  # TODO: broken
  # print("\n\n")
  # tables = ""
  # for addr in sorted(dat.keys()):
  #   init = low_to_high_init[addr] & high_to_low_init[addr]
  #   now = low_to_high[addr] & high_to_low[addr]
  #   d = now & ~init
  #   if d == 0:
  #     continue
  #   b = d.to_bytes(len(dat[addr]), byteorder='big')
  #
  #   byts = ''.join([(c if c == '0' else f'{RED}{c}{CLEAR}') for c in str(binascii.hexlify(b))[2:-1]])
  #   header = f"{hex(addr).ljust(6)}({str(addr).ljust(4)})"
  #   print(header, byts)
  #   tables += f"{header}\n"
  #   tables += can_table(b) + "\n\n"
  #
  # if table:
  #   print(tables)


if __name__ == "__main__":
  desc = """Collects messages and prints when a new bit transition is observed.
  This is very useful to find signals based on user triggered actions, such as blinkers and seatbelt.
  Leave the script running until no new transitions are seen, then perform the action."""
  parser = argparse.ArgumentParser(description=desc,
                                   formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  parser.add_argument("--bus", type=int, help="CAN bus to print out", default=0)
  parser.add_argument("--table", action="store_true", help="Print a cabana-like table")
  parser.add_argument("--multiplex", action="store_true", help="Detect multiplexed messages")
  parser.add_argument("init", type=str, nargs='?', help="Route or segment to initialize with. Use empty quotes to compare against all zeros.")
  parser.add_argument("comp", type=str, nargs='?', help="Route or segment to compare against init")

  args = parser.parse_args()

  init_lr, new_lr = None, None
  if args.init:
    if args.init == '':
      init_lr = []
    else:
      init_lr = logreader_from_route_or_segment(args.init)
  if args.comp:
    new_lr = logreader_from_route_or_segment(args.comp)

  can_printer(args.bus, init_msgs=init_lr, new_msgs=new_lr, table=args.table, multiplex=args.multiplex)
