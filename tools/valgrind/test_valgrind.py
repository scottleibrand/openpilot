#!/usr/bin/env python3
import os
import unittest
import time
import subprocess

from system.hardware import TICI

LEAK_SUMMARY = b"LEAK SUMMARY:"
HEAP_SUMMARY = b"HEAP SUMMARY:"
CHECK_STR = b"All heap blocks were freed -- no leaks are possible"


class TestValgrind(unittest.TestCase):

  def run_with_valgrind(self, bin_path, timeout=5):
    cmd = ["valgrind-3.20.0/build/bin/valgrind", "--leak-check=full",
           os.path.join(self.prefix,bin_path)]

    bin_name = os.path.split(bin_path)[1]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    time.sleep(timeout)
    p.kill()
    p.wait()

    #output = p.stdout.read()
    errout = p.stderr.read()

    p.stdout.close()
    p.stderr.close()

    if LEAK_SUMMARY not in errout and HEAP_SUMMARY not in errout:
      print(f"WARNING: no summaries found for {bin_name}!")
      return

    assert CHECK_STR in errout, f"{bin_name} leaked memory: {errout}"

  @classmethod
  def setUpClass(cls):

    cls.valgrind_bin = "valgrind-3.20.0/build/bin/valgrind"
    if not os.path.exists(cls.valgrind_bin):
      print("ERROR: valgrind binary does not exist! {cls.valgrind_bin}")
      assert False

    if TICI:
      cls.prefix = "/data/openpilot"
    else:
      cls.prefix = "/home/batman/openpilot"

  def test_sensord(self):
    self.run_with_valgrind("selfdrive/sensord/_sensord")

  def test_loggerd(self):
    self.run_with_valgrind("selfdrive/loggerd/loggerd")
    # TODO: check, leak summary takes very long to be generated

  def test_dmonitoringmodeld(self):
    self.run_with_valgrind("selfdrive/modeld/dmonitoringmodeld")


if __name__ == "__main__":
  unittest.main()

