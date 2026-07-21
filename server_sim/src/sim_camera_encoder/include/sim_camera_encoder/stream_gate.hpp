#pragma once

#include <atomic>

namespace sim_camera_encoder
{
class StreamGate
{
public:
  StreamGate(bool rgb = true, bool depth = true)
  : rgb_(rgb), depth_(depth) {}
  bool rgb() const {return rgb_.load();}
  bool depth() const {return depth_.load();}
  void set_rgb(bool enabled) {rgb_.store(enabled);}
  void set_depth(bool enabled) {depth_.store(enabled);}

private:
  std::atomic<bool> rgb_;
  std::atomic<bool> depth_;
};
}  // namespace sim_camera_encoder
