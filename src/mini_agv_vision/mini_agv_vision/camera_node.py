#!/usr/bin/env python3

import sys
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

        camera_index = self.get_parameter('camera_index').value
        self.show_display = self.get_parameter('show_display').value


        self.publisher = self.create_publisher(Image, 'camera_image', 10)
        self.bridge = CvBridge()


        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().error(f'Could not open camera {camera_index}')
            sys.exit(1)

        publisher_hz = 1.0/30.0
        self.timer = self.create_timer(publisher_hz, self.process_frame)

        self.get_logger().info(
            f'Camera {camera_index} opened. Publishing to "/camera_image".'
        )


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
        """Release the camera and close any OpenCV windows."""
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