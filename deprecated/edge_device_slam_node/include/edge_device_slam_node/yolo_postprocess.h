#ifndef YOLO_POSTPROCESS_H
#define YOLO_POSTPROCESS_H

#include <vector>
#include <cmath>
#include <algorithm>
#include <opencv2/opencv.hpp>

struct Detection {
    cv::Rect box;
    float confidence;
    int class_id;
};

class YoloPostProcess {
public:
    static std::vector<Detection> process(float* output_0, float* output_1, float* output_2, 
                                        int img_w, int img_h, float conf_threshold) {
        std::vector<Detection> detections;
        // YOLOv11n 416x416 - Single class: "cone"
        // Decoding logic will treat the score tensor as having 1 class only.
        return detections;
    }

    static void nms(std::vector<Detection>& detections, float nms_threshold) {
        if (detections.empty()) return;
        std::sort(detections.begin(), detections.end(), [](const Detection& a, const Detection& b) {
            return a.confidence > b.confidence;
        });

        std::vector<bool> is_suppressed(detections.size(), false);
        for (size_t i = 0; i < detections.size(); ++i) {
            if (is_suppressed[i]) continue;
            for (size_t j = i + 1; j < detections.size(); ++j) {
                if (is_suppressed[j]) continue;
                float iou = calculate_iou(detections[i].box, detections[j].box);
                if (iou > nms_threshold) is_suppressed[j] = true;
            }
        }

        std::vector<Detection> result;
        for (size_t i = 0; i < detections.size(); ++i) {
            if (!is_suppressed[i]) result.push_back(detections[i]);
        }
        detections = result;
    }

private:
    static float calculate_iou(const cv::Rect& a, const cv::Rect& b) {
        float inter = (a & b).area();
        float union_area = a.area() + b.area() - inter;
        return inter / union_area;
    }
};

#endif
