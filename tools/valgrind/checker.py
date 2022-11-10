#!/usr/bin/env python
import os
import sys

LOGFILE = "output.log"
CHECK_STR = "All heap blocks were freed -- no leaks are possible"

def main():
  if not os.path.exists(LOGFILE):
    print("ERROR: output logfile not found")
    sys.exit(-1)

  with open(LOGFILE, "r") as f:
    content = f.read()
    if CHECK_STR not in content:
      print("ERROR: leak have been found!")
      sys.exit(-1)

  print("Valgrind checks passed!")

if __name__ == "__main__":
  main()

