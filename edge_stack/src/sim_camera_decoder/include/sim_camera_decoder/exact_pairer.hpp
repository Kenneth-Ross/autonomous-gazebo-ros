#pragma once

#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <utility>

namespace sim_camera_decoder
{
template<typename Left, typename Right>
class ExactPairer
{
public:
  using Pair = std::pair<Left, Right>;

  explicit ExactPairer(std::size_t capacity = 2U)
  : capacity_(capacity) {}

  void push_left(int64_t stamp, Left value)
  {
    left_[stamp] = std::move(value);
    trim(left_);
    update_high_water();
  }

  void push_right(int64_t stamp, Right value)
  {
    right_[stamp] = std::move(value);
    trim(right_);
    update_high_water();
  }

  std::optional<Pair> take_newest_complete()
  {
    std::optional<int64_t> newest;
    for (const auto & item : left_) {
      if (right_.count(item.first) != 0U) {
        newest = item.first;
      }
    }
    if (!newest) {
      return std::nullopt;
    }
    Pair result{std::move(left_.at(*newest)), std::move(right_.at(*newest))};
    for (auto it = left_.begin(); it != left_.end(); ) {
      it = it->first <= *newest ? left_.erase(it) : std::next(it);
    }
    for (auto it = right_.begin(); it != right_.end(); ) {
      it = it->first <= *newest ? right_.erase(it) : std::next(it);
    }
    return result;
  }

  std::size_t dropped() const {return dropped_;}
  std::size_t high_water() const {return high_water_;}
  std::size_t size() const {return left_.size() + right_.size();}
  std::optional<int64_t> newest_left_stamp() const
  {
    return left_.empty() ? std::nullopt : std::optional<int64_t>(left_.rbegin()->first);
  }
  std::optional<int64_t> newest_right_stamp() const
  {
    return right_.empty() ? std::nullopt : std::optional<int64_t>(right_.rbegin()->first);
  }
  void set_capacity(std::size_t capacity) {capacity_ = capacity; trim(left_); trim(right_);}

private:
  template<typename Map>
  void trim(Map & values)
  {
    while (values.size() > capacity_) {
      values.erase(values.begin());
      ++dropped_;
    }
  }

  void update_high_water() {high_water_ = std::max(high_water_, size());}

  std::size_t capacity_;
  std::map<int64_t, Left> left_;
  std::map<int64_t, Right> right_;
  std::size_t dropped_{0U};
  std::size_t high_water_{0U};
};
}  // namespace sim_camera_decoder
