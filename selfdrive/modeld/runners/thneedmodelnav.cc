#include "selfdrive/modeld/runners/thneedmodelnav.h"

#include <cassert>

ThneedModelNav::ThneedModelNav(const char *path, float *loutput, size_t loutput_size, int runtime, bool luse_extra, bool luse_tf8, cl_context context) {
  thneed = new Thneed(true, context);
  thneed->load(path);
  thneed->clexec();

  recorded = false;
  output = loutput;
  use_extra = luse_extra;
}

void ThneedModelNav::addRecurrent(float *state, int state_size) {
  recurrent = state;
}

void ThneedModelNav::addTrafficConvention(float *state, int state_size) {
  trafficConvention = state;
}

void ThneedModelNav::addDesire(float *state, int state_size) {
  desire = state;
}

void ThneedModelNav::addNavFeatures(float *state, int state_size) {
  navFeatures = state;
}

void ThneedModelNav::addImage(float *image_input_buf, int buf_size) {
  input = image_input_buf;
}

void ThneedModelNav::addExtra(float *extra_input_buf, int buf_size) {
  extra = extra_input_buf;
}

void* ThneedModelNav::getInputBuf() {
  return &(thneed->input_clmem[0]);
}

void* ThneedModelNav::getExtraBuf() {
  return nullptr;
}

void ThneedModelNav::execute() {
  if (!recorded) {
    thneed->record = true;
    float *inputs[1] = {input};
    thneed->copy_inputs(inputs);
    thneed->clexec();
    thneed->copy_output(output);
    thneed->stop();

    recorded = true;
  } else {
    float *inputs[1] = {input};
    thneed->execute(inputs, output);
  }
}
