#!/usr/bin/env python3
import os
import threading
import time
import unittest
import subprocess
import signal


from collections import defaultdict

import cereal.messaging as messaging
from collections import namedtuple
from tools.lib.logreader import LogReader
from selfdrive.test.openpilotci import get_url
from common.basedir import BASEDIR

ProcessConfig = namedtuple('ProcessConfig', ['proc_name', 'pub_sub', 'ignore', 'command', 'path', 'segment', 'wait_for_response'])

CONFIGS = [
  ProcessConfig(
    proc_name="ubloxd",
    pub_sub={
      "ubloxRaw": ["ubloxGnss", "gpsLocationExternal"],
    },
    ignore=[],
    command="./ubloxd",
    path="selfdrive/locationd/",
    segment="0375fdf7b1ce594d|2019-06-13--08-32-25--3",
    wait_for_response=True
  ),
  #ProcessConfig(
  #  proc_name="locationd",
  #  pub_sub={
  #    "liveLocationKalman": ["gpsLocation", "cameraOdometry",
  #        "liveCalibration", "carState", "carParams", "accelerometer", "gyroscope"],
  #  },
  #  ignore=[],
  #  command="./locationd",
  #  path="selfdrive/locationd/",
  #  segment="376bf99325883932|2022-11-07--23-34-22--6",
  #  wait_for_response=True
  #),
]


class TestValgrind(unittest.TestCase):
  def extract_leak_sizes(self, log):
    if "All heap blocks were freed -- no leaks are possible" in log:
      return (0,0,0)

    log = log.replace(",","")  # fixes casting to int issue with large leaks
    print(f"RAW LOG: '{log}'")
    err_lost1 = log.split("definitely lost: ")[1]
    err_lost2 = log.split("indirectly lost: ")[1]
    err_lost3 = log.split("possibly lost: ")[1]
    definitely_lost = int(err_lost1.split(" ")[0])
    indirectly_lost = int(err_lost2.split(" ")[0])
    possibly_lost = int(err_lost3.split(" ")[0])
    return (definitely_lost, indirectly_lost, possibly_lost)

  def valgrindlauncher(self, arg, cwd):
    os.chdir(os.path.join(BASEDIR, cwd))
    # Run valgrind on a process
    command = "valgrind --leak-check=full " + arg
    print(f"Testing: {command}")
    p = subprocess.Popen(command, stderr=subprocess.PIPE, shell=True, preexec_fn=os.setsid)  # pylint: disable=W1509

    print("Running replay...")
    while not self.replay_done:
      time.sleep(0.1)

    print("Replay Done...")
    # Kill valgrind and extract leak output
    os.killpg(os.getpgid(p.pid), signal.SIGINT)
    _, err = p.communicate()
    error_msg = str(err, encoding='utf-8')
    with open(os.path.join(BASEDIR, "selfdrive/test/valgrind_logs.txt"), "a") as f:
      f.write(error_msg)
      f.write(5 * "\n")
    definitely_lost, indirectly_lost, possibly_lost = self.extract_leak_sizes(error_msg)
    if max(definitely_lost, indirectly_lost, possibly_lost) > 0:
      self.leak = True
      print("LEAKS from", arg, "\nDefinitely lost:", definitely_lost, "\nIndirectly lost", indirectly_lost, "\nPossibly lost", possibly_lost)
    else:
      self.leak = False

  def replay_process(self, config, logreader):
    pub_sockets = [s for s in config.pub_sub.keys()]  # We get responses here
    sub_sockets = [s for _, sub in config.pub_sub.items() for s in sub]  # We dump data from logs here

    print(f"sub sockets: {sub_sockets}")
    print(f"pub sockets: {pub_sockets}")

    pm = messaging.PubMaster(pub_sockets)
    sm = messaging.SubMaster(sub_sockets)

    all_msgs = sorted(logreader, key=lambda msg: msg.logMonoTime)
    pub_msgs = [msg for msg in all_msgs if msg.which() in pub_sockets]

    msgs = defaultdict(list)
    for msg in all_msgs:
      msgs[msg.which()] = msg

    print(f"all msg: {len(all_msgs)}")
    print(f"all msg: {list(msgs.keys())}")
    print(f"pub msg: {len(pub_msgs)}")
    print(f"config.pub_sub.keys(): {list(config.pub_sub.keys())}")

    thread = threading.Thread(target=self.valgrindlauncher, args=(config.command, config.path))
    thread.daemon = True
    thread.start()
    time.sleep(1)

    while not all(pm.all_readers_updated(s) for s in pub_sockets):
      print("sleep...")
      time.sleep(0)

    print(f"Replay length: {len(pub_msgs)}")

    for msg in pub_msgs:
      print(f"replay: {msg.which()}")
      pm.send(msg.which(), msg.as_builder())
      if config.wait_for_response:
        sm.update(100)

    print("Replay DONE...")
    self.replay_done = True

    thread.join()

  def test_config(self):
    open(os.path.join(BASEDIR, "selfdrive/test/valgrind_logs.txt"), "w").close()

    for cfg in CONFIGS:
      self.leak = None
      self.replay_done = False

      r, n = cfg.segment.rsplit("--", 1)
      log_name = get_url(r, n)
      print(f"Replay log: {log_name}")
      lr = LogReader(log_name)
      self.replay_process(cfg, lr)

      while self.leak is None:
        time.sleep(0.1)  # Wait for the valgrind to finish

      self.assertFalse(self.leak)


if __name__ == "__main__":
  unittest.main()
