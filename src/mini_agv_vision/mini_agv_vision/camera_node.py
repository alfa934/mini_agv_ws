#!/usr/bin/env python3

import sys
import time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class CameraNode(Node):
    def __init__(self) -> None:
        super().__init__('camera_node')

        self.declare_parameter('camera_index', 0)
        self.declare_parameter('show_display', False)
        self.declare_parameter('frame_width', 640)
        self.declare_parameter('frame_height', 480)
        self.declare_parameter('fps', 30.0)

        camera_index = self.get_parameter('camera_index').value
        self.show_display = self.get_parameter('show_display').value
        self.frame_w = self.get_parameter('frame_width').value
        self.frame_h = self.get_parameter('frame_height').value
        fps = self.get_parameter('fps').value

        self.publisher = self.create_publisher(Image, 'camera_image', 10)
        self.bridge = CvBridge()

        self.cap = self.open_camera(camera_index)
        self.warm_up()

        self.timer = self.create_timer(1.0 / fps, self.process_frame)

        self.get_logger().info(
            f'Camera {camera_index} ready at {self.frame_w}x{self.frame_h}, '
            f'publishing to "/camera_image" at {fps} Hz.'
        )

    def open_camera(self, index: int):
        """Try to open the camera with fallback backends and set resolution."""
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        cap = None
        for backend in backends:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                self.get_logger().info(f'Opened camera with backend {backend}')
                break
        if cap is None or not cap.isOpened():
            self.get_logger().error(f'Could not open camera {index} with any backend')
            sys.exit(1)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_h)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if actual_w != self.frame_w or actual_h != self.frame_h:
            self.get_logger().warn(
                f'Requested {self.frame_w}x{self.frame_h}, got {actual_w}x{actual_h}'
            )
            self.frame_w, self.frame_h = actual_w, actual_h

        return cap

    def warm_up(self, num_frames: int = 5) -> None:
        time.sleep(0.5)
        for i in range(num_frames):
            ret, _ = self.cap.read()
            if not ret:
                self.get_logger().warn(f'Warm‑up frame {i} failed')
            time.sleep(0.05)

    def process_frame(self) -> None:
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn('Failed to grab frame')
            return

        ros_image = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        self.publisher.publish(ros_image)

        if self.show_display:
            cv2.imshow('Camera Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.get_logger().info('Shutdown requested via "q" key')
                rclpy.shutdown()

    def destroy_node(self) -> None:
        self.cap.release()
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args: list = None) -> None:
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()