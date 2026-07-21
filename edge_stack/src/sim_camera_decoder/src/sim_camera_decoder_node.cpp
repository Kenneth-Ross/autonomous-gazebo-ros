#include <cv_bridge/cv_bridge.hpp>
#include <opencv2/imgcodecs.hpp>
#include <image_transport/image_transport.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_components/register_node_macro.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <condition_variable>
#include <chrono>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include "sim_camera_decoder/exact_pairer.hpp"

class SimCameraDecoder : public rclcpp::Node
{
public:
  explicit SimCameraDecoder(const rclcpp::NodeOptions & options = rclcpp::NodeOptions())
  : Node("camera_decoder", options), pairer_(8)
  {
    width_ = declare_parameter<int>("image_width", 1280);
    height_ = declare_parameter<int>("image_height", 800);
    frame_id_ = declare_parameter<std::string>("frame_id", "camera_link_optical");
    preview_ = declare_parameter<bool>("publish_compressed", true);
    preview_rate_ = declare_parameter<double>("preview_rate_hz", 5.0);
    jpeg_quality_ = declare_parameter<int>("jpeg_quality", 50);
    png_level_ = declare_parameter<int>("png_compression", 3);
    pairing_queue_depth_ = declare_parameter<int>("pairing_queue_depth", 8);
    if (width_ <= 0 || height_ <= 0 || preview_rate_ < 0.0 || pairing_queue_depth_ <= 0) {
      throw std::invalid_argument("dimensions must be positive and preview rate non-negative");
    }
    pairer_.set_capacity(static_cast<std::size_t>(pairing_queue_depth_));
    const auto sensor_qos = rclcpp::SensorDataQoS().keep_last(1);
    const auto info_qos = rclcpp::QoS(rclcpp::KeepLast(1)).reliable();
    rgb_pub_ = create_publisher<sensor_msgs::msg::Image>("/edge/camera/rgb/image_raw", sensor_qos);
    depth_pub_ = create_publisher<sensor_msgs::msg::Image>("/edge/camera/depth/image_raw",
      sensor_qos);
    rgb_info_pub_ = create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/rgb/camera_info",
      info_qos);
    depth_info_pub_ =
      create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/depth/camera_info", info_qos);
    rgb_preview_pub_ = create_publisher<sensor_msgs::msg::CompressedImage>(
      "/edge/camera/rgb/image_raw/compressed", sensor_qos);
    depth_preview_pub_ = create_publisher<sensor_msgs::msg::CompressedImage>(
      "/edge/camera/depth/image_raw/compressed", sensor_qos);
    configure_info();

    auto wire_qos = rmw_qos_profile_default;
    wire_qos.history = RMW_QOS_POLICY_HISTORY_KEEP_LAST;
    wire_qos.depth = 2;
    wire_qos.reliability = RMW_QOS_POLICY_RELIABILITY_BEST_EFFORT;
    rgb_sub_ = image_transport::create_subscription(this, "/oakd/rgb/image_raw",
        [this](const sensor_msgs::msg::Image::ConstSharedPtr & msg) {enqueue_rgb(msg);},
      "ffmpeg", wire_qos);
    depth_sub_ = image_transport::create_subscription(this, "/oakd/depth/image_raw",
        [this](const sensor_msgs::msg::Image::ConstSharedPtr & msg) {enqueue_depth(msg);},
      "zstd", wire_qos);
    pair_thread_ = std::thread([this]() {pair_worker();});
    if (preview_) {preview_thread_ = std::thread([this]() {preview_worker();});}
    timer_ = create_wall_timer(std::chrono::seconds(5), [this]() {report();});
  }

  ~SimCameraDecoder() override
  {
    {std::lock_guard<std::mutex> lock(mutex_); stop_ = true;}
    pair_cv_.notify_all(); preview_cv_.notify_all();
    if (pair_thread_.joinable()) {pair_thread_.join();}
    if (preview_thread_.joinable()) {preview_thread_.join();}
  }

private:
  using ImagePtr = sensor_msgs::msg::Image::ConstSharedPtr;
  struct PreviewJob {std_msgs::msg::Header header; cv::Mat rgb; cv::Mat depth;};
  static int64_t stamp(const ImagePtr & msg) {return rclcpp::Time(msg->header.stamp).nanoseconds();}
  void enqueue_rgb(const ImagePtr & msg)
  {
    {std::lock_guard<std::mutex> lock(mutex_); ++rgb_received_; pairer_.push_left(stamp(msg), msg);}
    pair_cv_.notify_one();
  }
  void enqueue_depth(const ImagePtr & msg)
  {
    {std::lock_guard<std::mutex> lock(mutex_); ++depth_received_;
      pairer_.push_right(stamp(msg), msg);}
    pair_cv_.notify_one();
  }
  void pair_worker()
  {
    while (true) {
      std::optional<typename sim_camera_decoder::ExactPairer<ImagePtr, ImagePtr>::Pair> pair;
      {std::unique_lock<std::mutex> lock(mutex_);
        pair_cv_.wait_for(lock, std::chrono::milliseconds(100));
        if (stop_) {return;}
        pair = pairer_.take_newest_complete();}
      if (!pair) {std::this_thread::yield(); continue;}
      publish_pair(pair->first, pair->second);
    }
  }
  void publish_pair(const ImagePtr & rgb, const ImagePtr & depth)
  {
    if (rgb->width != static_cast<uint32_t>(width_) ||
      rgb->height != static_cast<uint32_t>(height_) ||
      depth->width != rgb->width || depth->height != rgb->height || rgb->encoding != "bgr8" ||
      depth->encoding != "16UC1") {++malformed_; return;}
    auto rgb_out = std::make_unique<sensor_msgs::msg::Image>(*rgb);
    auto depth_out = std::make_unique<sensor_msgs::msg::Image>(*depth);
    rgb_out->header.frame_id = frame_id_; depth_out->header.frame_id = frame_id_;
    auto header = rgb_out->header;
    rgb_pub_->publish(std::move(rgb_out)); depth_pub_->publish(std::move(depth_out));
    info_.header = header;
    rgb_info_pub_->publish(info_); depth_info_pub_->publish(info_);
    ++published_;
    if (preview_) {
      const int64_t now = rclcpp::Time(header.stamp).nanoseconds();
      const int64_t period = preview_rate_ > 0.0 ? static_cast<int64_t>(1e9 / preview_rate_) : 0;
      if (period == 0 || now - last_preview_stamp_ >= period) {
        try {
          PreviewJob job{header, cv_bridge::toCvShare(rgb, "bgr8")->image.clone(),
            cv_bridge::toCvShare(depth, "16UC1")->image.clone()};
          {std::lock_guard<std::mutex> lock(mutex_); preview_job_ = std::move(job);
            last_preview_stamp_ = now;}
          preview_cv_.notify_one();
        } catch (const cv_bridge::Exception &) {++malformed_;}
      }
    }
  }
  void preview_worker()
  {
    while (true) {
      PreviewJob job;
      {std::unique_lock<std::mutex> lock(mutex_);
        preview_cv_.wait(lock, [this]() {return stop_ || preview_job_.has_value();});
        if (stop_) {return;} job = std::move(*preview_job_); preview_job_.reset();}
      sensor_msgs::msg::CompressedImage rgb, depth;
      rgb.header = job.header; rgb.format = "jpeg";
      depth.header = job.header; depth.format = "png";
      cv::imencode(".jpg", job.rgb, rgb.data, {cv::IMWRITE_JPEG_QUALITY, jpeg_quality_});
      cv::imencode(".png", job.depth, depth.data, {cv::IMWRITE_PNG_COMPRESSION, png_level_});
      rgb_preview_pub_->publish(rgb); depth_preview_pub_->publish(depth); ++previews_;
    }
  }
  void configure_info()
  {
    const double fx = declare_parameter<double>("camera.fx", 800.0);
    const double fy = declare_parameter<double>("camera.fy", 800.0);
    const double cx = declare_parameter<double>("camera.cx", width_ / 2.0);
    const double cy = declare_parameter<double>("camera.cy", height_ / 2.0);
    info_.width = width_; info_.height = height_; info_.distortion_model = "plumb_bob";
    info_.k = {fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0};
    info_.p = {fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0};
    info_.r = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0}; info_.d.assign(5, 0.0);
  }
  void report()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    const auto rgb_stamp = pairer_.newest_left_stamp();
    const auto depth_stamp = pairer_.newest_right_stamp();
    const long long stamp_gap_ns = rgb_stamp && depth_stamp ?
      static_cast<long long>(*rgb_stamp - *depth_stamp) : 0LL;
    RCLCPP_INFO(get_logger(), "rgb_received=%lu depth_received=%lu pairs_published=%lu "
      "unmatched_dropped=%zu queue_size=%zu queue_high_water=%zu stamp_gap_ns=%lld "
      "malformed=%lu previews=%lu", rgb_received_, depth_received_, published_,
      pairer_.dropped(), pairer_.size(), pairer_.high_water(), stamp_gap_ns, malformed_, previews_);
  }
  image_transport::Subscriber rgb_sub_, depth_sub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr rgb_pub_, depth_pub_;
  rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr rgb_info_pub_, depth_info_pub_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr rgb_preview_pub_,
    depth_preview_pub_;
  sensor_msgs::msg::CameraInfo info_;
  sim_camera_decoder::ExactPairer<ImagePtr, ImagePtr> pairer_;
  std::mutex mutex_; std::condition_variable pair_cv_, preview_cv_;
  std::optional<PreviewJob> preview_job_; std::thread pair_thread_, preview_thread_;
  rclcpp::TimerBase::SharedPtr timer_; bool stop_{false}, preview_; int width_, height_;
  int jpeg_quality_, png_level_, pairing_queue_depth_; double preview_rate_; std::string frame_id_;
  int64_t last_preview_stamp_{0};
  uint64_t rgb_received_{0}, depth_received_{0}, published_{0}, malformed_{0}, previews_{0};
};

RCLCPP_COMPONENTS_REGISTER_NODE(SimCameraDecoder)
