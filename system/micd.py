#!/usr/bin/env python3
import time

import sounddevice as sd
import numpy as np

from cereal import messaging
from common.filter_simple import FirstOrderFilter
from common.realtime import Ratekeeper
from system.swaglog import cloudlog

RATE = 10
DT_MIC = 1. / RATE

MUTE_TIME = 1


class Mic:
  def __init__(self, pm, sm):
    self.pm = pm
    self.sm = sm
    self.rk = Ratekeeper(RATE)

    self.channels = 0
    self.measurements = np.array([])
    self.filter = FirstOrderFilter(1, 3, DT_MIC)
    self.last_alert_time = 0

  def update(self):
    self.sm.update(0)

    if self.sm.updated['controlsState']:
      if self.sm['controlsState'].alertSound > 0:
        self.last_alert_time = time.time()

    muted = time.time() - self.last_alert_time < MUTE_TIME

    msg = messaging.new_message('microphone')
    microphone = msg.microphone

    if not muted and len(self.measurements) > 0:
      noise_level_raw = [np.linalg.norm(channel) for channel in self.measurements.T]
      self.filter.update(sum(noise_level_raw) / self.channels)
    else:
      noise_level_raw = [0] * self.channels
    self.measurements = np.array([])

    microphone.ambientNoiseLevelRaw = noise_level_raw
    microphone.filteredAmbientNoiseLevel = self.filter.x

    self.pm.send('microphone', msg)
    self.rk.keep_time()

  def callback(self, indata, frames, time, status):
    self.measurements = np.concatenate((self.measurements, indata))

  def micd_thread(self, device=None):
    if device is None:
      device = "sysdefault"

    with sd.InputStream(device=device, samplerate=44100, callback=self.callback) as stream:
      cloudlog.info(f"micd stream started: {stream.samplerate=} {stream.channels=} {stream.dtype=} {stream.device=}")
      self.channels = stream.channels
      while True:
        self.update()


def main(pm=None, sm=None):
  if pm is None:
    pm = messaging.PubMaster(['microphone'])
  if sm is None:
    sm = messaging.SubMaster(['controlsState'])

  mic = Mic(pm, sm)
  mic.micd_thread()


if __name__ == "__main__":
  main()
