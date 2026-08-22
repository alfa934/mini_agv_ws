#!/usr/bin/env python3

import time
import sys
import numpy as np

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage
from cv_bridge import CvBridge
import cv2


class CameraNode(Node):

    def __init__(self) -> None:
        super().__init__('camera_node')

        self.declare_parameter('camera_index', 0)
        self.declare_parameter('show_display', False)
        self.declare_parameter('target_fps', 30.0)
        self.declare_parameter('frame_width', 640)
        self.declare_parameter('frame_height', 480)
        self.declare_parameter('use_compressed', True)
        self.declare_parameter('jpeg_quality', 80)

        self.camera_index = self.get_parameter('camera_index').value
        self.show_display = self.get_parameter('show_display').value
        self.target_fps = self.get_parameter('target_fps').value
        self.frame_width = self.get_parameter('frame_width').value
        self.frame_height = self.get_parameter('frame_height').value
        self.use_compressed = self.get_parameter('use_compressed').value
        self.jpeg_quality = self.get_parameter('jpeg_quality').value

        self.bridge = CvBridge()

        topic = 'camera_image/compressed' if self.use_compressed else 'camera_image'
        msg_type = CompressedImage if self.use_compressed else Image
        self.publisher = self.create_publisher(msg_type, topic, 10)
        self.get_logger().info(f'Publishing to "{topic}"')

        self.open_camera()
        self.warm_up()

        self.frame_interval = 1.0 / self.target_fps if self.target_fps > 0 else 0.0
        self.frame_drop_count = 0

        self.get_logger().info(
            f'Camera {self.camera_index} ready at {self.frame_width}x{self.frame_height}'
        )

    def open_camera(self) -> None:
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().error(f'Could not open camera {self.camera_index}')
            sys.exit(1)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception as e:
            self.get_logger().warn(f'Could not set buffer size: {e}')

    def warm_up(self, num_frames: int = 5) -> None:
        for _ in range(num_frames):
            self.cap.read()

    def publish_frame(self) -> None:
        ret, frame = self.cap.read()
        if not ret:
            self.frame_drop_count += 1
            if self.frame_drop_count % 30 == 0:
                self.get_logger().warn(f'Frame drops: {self.frame_drop_count}')
            time.sleep(0.005)
            return

        self.frame_drop_count = 0

        if self.use_compressed:
            msg = self.build_compressed_msg(frame)
        else:
            msg = self.build_raw_msg(frame)

        msg.header.stamp = self.get_clock().now().to_msg()
        self.publisher.publish(msg)

        if self.show_display:
            cv2.imshow('USB Camera Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                rclpy.shutdown()

    def build_compressed_msg(self, frame: np.ndarray) -> CompressedImage:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        _, jpeg_buffer = cv2.imencode('.jpg', frame, encode_params)
        msg = CompressedImage()
        msg.format = 'jpeg'
        msg.data = np.array(jpeg_buffer).tobytes()
        return msg

    def build_raw_msg(self, frame: np.ndarray) -> Image:
        return self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')

    def destroy_node(self) -> None:
        self.cap.release()
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args: list = None) -> None:
    rclpy.init(args=args)
    node = CameraNode()
    node.get_logger().set_level(rclpy.logging.LoggingSeverity.INFO)

    try:
        while rclpy.ok():
            start_time = node.get_clock().now()

            node.publish_frame()
            rclpy.spin_once(node, timeout_sec=0)

            if node.target_fps > 0:
                elapsed = (node.get_clock().now() - start_time).nanoseconds / 1e9
                sleep_time = node.frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()