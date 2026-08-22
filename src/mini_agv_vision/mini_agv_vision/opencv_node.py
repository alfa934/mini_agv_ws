#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class OpecvNode(Node):

    def __init__(self) -> None:
        super().__init__('opencv_node_node')

        self.declare_parameter('show_display', False)
        self.show_display = self.get_parameter('show_display').value

        self.bridge = CvBridge()

        self.pub = self.create_publisher(Image, 'camera_image/grayscale', 10)

        self.sub = self.create_subscription(
            Image,
            'camera_image',
            self.image_callback,
            10
        )

        self.get_logger().info(
            'Grayscale node started. Subscribing to "/camera_image", '
            'publishing to "/camera_image/grayscale".'
        )

    def image_callback(self, msg: Image) -> None:
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'cv_bridge conversion failed: {e}')
            return

        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        gray_msg = self.bridge.cv2_to_imgmsg(gray, encoding='mono8')

        self.pub.publish(gray_msg)

        if self.show_display:
            cv2.imshow('Grayscale Stream', gray)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                rclpy.shutdown()

    def destroy_node(self) -> None:
        cv2.destroyAllWindows()
        super().destroy_node()


def main(args: list = None) -> None:
    rclpy.init(args=args)
    node = OpecvNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()