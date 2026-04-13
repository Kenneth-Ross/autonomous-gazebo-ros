
import sys
print(sys.path)
import argparse
import os

import cv2
from cv_bridge import CvBridge
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Image


def main():
    parser = argparse.ArgumentParser(description='Extract a video from a rosbag.')
    parser.add_argument('bag_file', help='Path to the rosbag file')
    parser.add_argument('output_file', help='Path to the output video file')
    parser.add_argument('--topic', help='Topic to extract the video from', default='/oakd/rgb/image_raw')
    args = parser.parse_args()

    bag_path = args.bag_file
    storage_options = rosbag2_py.StorageOptions(uri=bag_path, storage_id='mcap')
    converter_options = rosbag2_py.ConverterOptions('', '')
    reader = rosbag2_py.SequentialReader()
    reader.open(storage_options, converter_options)

    bridge = CvBridge()
    video_writer = None

    topic_types = reader.get_all_topics_and_types()
    type_map = {topic_types[i].name: topic_types[i].type for i in range(len(topic_types))}

    while reader.has_next():
        (topic, data, t) = reader.read_next()
        if topic == args.topic:
            msg_type = type_map[topic]
            msg = deserialize_message(data, Image)
            cv_image = bridge.imgmsg_to_cv2(msg, "bgr8")

            if video_writer is None:
                video_writer = cv2.VideoWriter(args.output_file,
                                               cv2.VideoWriter_fourcc(*'mp4v'),
                                               30,
                                               (cv_image.shape[1], cv_image.shape[0]))
            video_writer.write(cv_image)

    if video_writer is not None:
        video_writer.release()


if __name__ == '__main__':
    main()
