#!/usr/bin/env python

import rospy
from std_msgs.msg import Bool
from dbw_mkz_msgs.msg import ThrottleCmd, SteeringCmd, BrakeCmd, SteeringReport
from geometry_msgs.msg import TwistStamped, PoseStamped
from styx_msgs.msg import Lane
from std_msgs.msg import Float32
import math

from twist_controller import Controller

'''
You can build this node only after you have built (or partially built) the `waypoint_updater` node.

You will subscribe to `/twist_cmd` message which provides the proposed linear and angular velocities.
You can subscribe to any other message that you find important or refer to the document for list
of messages subscribed to by the reference implementation of this node.

One thing to keep in mind while building this node and the `twist_controller` class is the status
of `dbw_enabled`. While in the simulator, its enabled all the time, in the real car, that will
not be the case. This may cause your PID controller to accumulate error because the car could
temporarily be driven by a human instead of your controller.

We have provided two launch files with this node. Vehicle specific values (like vehicle_mass,
wheel_base) etc should not be altered in these files.

We have also provided some reference implementations for PID controller and other utility classes.
You are free to use them or build your own.

Once you have the proposed throttle, brake, and steer values, publish it on the various publishers
that we have created in the `__init__` function.

'''


class DBWNode(object):
    def __init__(self):
        rospy.init_node('dbw_node', log_level=rospy.DEBUG)

        # Parameter
        vehicle_mass = rospy.get_param('~vehicle_mass', 1736.35)
        fuel_capacity = rospy.get_param('~fuel_capacity', 13.5)
        brake_deadband = rospy.get_param('~brake_deadband', .1)
        decel_limit = rospy.get_param('~decel_limit', -5)
        accel_limit = rospy.get_param('~accel_limit', 1.)
        wheel_radius = rospy.get_param('~wheel_radius', 0.2413)
        wheel_base = rospy.get_param('~wheel_base', 2.8498)
        steer_ratio = rospy.get_param('~steer_ratio', 14.8)
        max_lat_accel = rospy.get_param('~max_lat_accel', 3.)
        max_steer_angle = rospy.get_param('~max_steer_angle', 8.)
        min_speed = rospy.get_param('~min_speed', 1.)

        # Publisher
        self.steer_pub = rospy.Publisher('/vehicle/steering_cmd', SteeringCmd, queue_size=2)
        self.throttle_pub = rospy.Publisher('/vehicle/throttle_cmd', ThrottleCmd, queue_size=2)
        self.brake_pub = rospy.Publisher('/vehicle/brake_cmd', BrakeCmd, queue_size=2)

        # Controller
        controller_args = {'wheel_base': wheel_base,
                           'steer_ratio': steer_ratio,
                           'min_speed': min_speed,
                           'max_lat_accel': max_lat_accel,
                           'max_steer_angle': max_steer_angle,
                           'decel_limit': decel_limit,
                           'accel_limit': accel_limit,
                           'vehicle_mass': vehicle_mass,
                           'wheel_radius': wheel_radius,
                           'brake_deadband': brake_deadband
                           }

        self.controller = Controller(**controller_args)

        # Variables
        self.dbw_enabled = True  # drive-by-wire is enabled by default and can be disable by a manual operator
        self.curr_vel = 0.0  # Current velocity
        self.curr_ang_vel = 0.0  # Current angular velocity
        self.target_vel = 0.0  # Target velocity
        self.target_ang_vel = 0.0  # Target angular velocity
        self.current_pose = None  # current pose of the car
        self.final_waypoints = None  # Lane object
        self.last_timestamp = rospy.rostime.get_time()
        self.curr_angle = 0.0
        self.cte = 0.0
        self.count = 0

        # Subscriber
        rospy.Subscriber('/twist_cmd', TwistStamped, self.twist_cmd_cb)
        rospy.Subscriber('/current_velocity', TwistStamped, self.current_velocity_cb)
        rospy.Subscriber('/vehicle/dbw_enabled', Bool, self.dbw_enabled_cb, queue_size=1)
        rospy.Subscriber('/final_waypoints', Lane, self.final_waypoints_cb, queue_size=1)
        rospy.Subscriber('current_pose', PoseStamped, self.current_pose_cb, queue_size=1)
        rospy.Subscriber('/vehicle/steering_report', SteeringReport, self.current_angle_cb, queue_size=1)
        rospy.Subscriber('/vehicle/cte', Float32, self.cte_cb, queue_size=1)

        self.loop()

    def loop(self):
        rate = rospy.Rate(50)  # 10Hz

        while not rospy.is_shutdown():

            now = rospy.rostime.get_time()
            elapsed = now - self.last_timestamp
            self.last_timestamp = now

            # Saving Arguments for the Controller
            control_args = {'target_vel': self.target_vel,  # target linear velocity
                            'curr_vel': self.curr_vel,  # current linear velocity
                            'target_ang_vel': self.target_ang_vel,  # target angular velocity
                            'curr_ang_vel': self.curr_ang_vel,  # current angular velocity
                            'dbw_enabled': self.dbw_enabled,  # dbw status
                            'curr_angle': self.curr_angle,
                            'cte': self.cte,
                            'elapsed': elapsed
                            }

            # Call Controller
            throttle, brake, angle = self.controller.control(**control_args)

            # We can uncomment the control calling above when they are done, first here some values for throttle, brake and angle
            # throttle = 1.0
            # brake = 0
            # angle = 0.0
            if self.dbw_enabled:
                self.publish(throttle, brake, angle)
            rate.sleep()

    def publish(self, throttle, brake, steer):
        #debug_msg = "DBW T:{} \t B:{} \t S:{}\t".format(throttle, brake, steer)
        #rospy.logdebug(debug_msg)
        self.count += 1

        tcmd = ThrottleCmd()
        tcmd.enable = True
        tcmd.pedal_cmd_type = ThrottleCmd.CMD_PERCENT
        tcmd.pedal_cmd = throttle
        self.throttle_pub.publish(tcmd)

        scmd = SteeringCmd()
        scmd.enable = True
        scmd.steering_wheel_angle_cmd = steer
        self.steer_pub.publish(scmd)

        bcmd = BrakeCmd()
        bcmd.enable = True
        bcmd.pedal_cmd_type = BrakeCmd.CMD_TORQUE
        bcmd.pedal_cmd = brake
        self.brake_pub.publish(bcmd)

    def dbw_enabled_cb(self, msg):
        self.dbw_enabled = bool(msg.data)

    def twist_cmd_cb(self, msg):
        self.target_vel = msg.twist.linear.x
        self.target_ang_vel = msg.twist.angular.z

    def current_velocity_cb(self, msg):
        self.curr_vel = msg.twist.linear.x
        self.curr_ang_vel = msg.twist.angular.z

    def current_pose_cb(self, msg):
        self.current_pose = msg.pose

    def cte_cb(self, msg):
        self.cte = msg.data

    def final_waypoints_cb(self, msg):
        self.final_waypoints_cb = msg.waypoints

    def current_angle_cb(self, msg):
        self.curr_angle = msg.steering_wheel_angle


if __name__ == '__main__':
    DBWNode()
