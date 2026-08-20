import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ros_gz_bridge.actions import RosGzBridge

def generate_launch_description():
    pkg_share = get_package_share_directory('mini_agv_description')

    # Compute the resource path: the parent of the package share directory
    gz_resource_path = os.path.dirname(pkg_share)   # e.g., .../share

    default_urdf = os.path.join(pkg_share, 'urdf', 'mini_agv_description.urdf')
    default_sdf = os.path.join(pkg_share, 'urdf', 'mini_agv_description.sdf')
    default_rviz = os.path.join(pkg_share, 'rviz', 'config.rviz')
    world_path = os.path.join(pkg_share, 'world', 'my_world.sdf')
    bridge_config = os.path.join(pkg_share, 'config', 'bridge_config.yaml')

    # Robot state publisher (URDF)
    with open(default_urdf, 'r') as f:
        robot_desc = f.read()

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}]
    )

    rviz2 = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', default_rviz]
    )

    # Gazebo with GUI (server + client)
    gz_sim = ExecuteProcess(
        cmd=['gz', 'sim', '-r', world_path],
        output='screen'
    )

    # ROS-Gazebo bridge (composable)
    bridge = RosGzBridge(
        bridge_name='ros_gz_bridge',
        config_file=bridge_config,
        container_name='ros_gz_container',
        create_own_container='True',
        use_composition='True',
    )

    # Spawn the robot using the SDF file
    spawn_robot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_spawn_model.launch.py')
        ),
        launch_arguments={
            'file': default_sdf,
            'entity_name': 'mini_agv',
            'x': '0.0',
            'y': '0.0',
            'z': '0.9',
            'yaw': '0.0',
        }.items()
    )

    return LaunchDescription([
        # Set environment variable so Gazebo finds meshes
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', gz_resource_path),
        DeclareLaunchArgument('use_sim_time', default_value='True'),
        robot_state_publisher,
        rviz2,
        gz_sim,
        bridge,
        spawn_robot,
    ])