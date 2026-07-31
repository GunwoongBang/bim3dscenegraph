import os
import signal
import shutil
import subprocess

from pathlib import Path

UTIL = Path(__file__).parent / "util"


def launch_ros2_pipeline(logger=None):
    """
    Launches the ROS2 point cloud generation pipeline, including
    Gazebo simulation, LIO-SAM, and teleop.

    Args:
        logger: Optional logger for output messages

    Returns:
        proc:
            Tuple of subprocess.Popen objects for (sim_proc, lio_proc, teleop_proc).
    """
    subprocess.run(
        [str(UTIL / "build.sh")],
        check=True,
    )

    if logger:
        logger.logText("SCAN2GRAPH", "Built ROS2 workspace")

    sim_proc = subprocess.Popen(
        [str(UTIL / "run_sim.sh")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    lio_proc = subprocess.Popen(
        [str(UTIL / "run_lio_sam.sh")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    if logger:
        logger.logText("SCAN2GRAPH", "Launched ROS2 point cloud generation")

    terminal = next(
        (t for t in ("gnome-terminal", "xterm", "konsole", "xfce4-terminal")
         if shutil.which(t)), None
    )
    if terminal is None:
        raise RuntimeError("No terminal emulator found for teleop.")

    teleop_script = str(UTIL / "run_teleop.sh")
    if terminal == "gnome-terminal":
        teleop_proc = subprocess.Popen(
            ["gnome-terminal", "--", "bash", teleop_script],
            start_new_session=True,
        )
    elif terminal == "xterm":
        teleop_proc = subprocess.Popen(
            ["xterm", "-e", teleop_script],
            start_new_session=True,
        )
    else:
        teleop_proc = subprocess.Popen(
            [terminal, "-e", teleop_script],
            start_new_session=True,
        )

    proc = (sim_proc, lio_proc, teleop_proc)

    return proc


def _kill_group(proc):
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.wait(timeout=5)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


_ROS2_BIN = "/opt/ros/humble/bin/ros2"


def _kill_all_ros2():
    for pattern in (
        "run_sim.sh", "run_lio_sam.sh",             # bash session leaders
        "ros2",                                     # ros2 launch/run wrappers
        "lio_sam",                                  # lio_sam C++ node executables
        "gzserver", "gzclient", "gazebo",           # Gazebo processes
        "robot_state_publisher", "static_transform_publisher",
    ):
        subprocess.run(["pkill", "-9", "-f", pattern], check=False)

    subprocess.run("rm -rf /dev/shm/fastrtps_*", shell=True, check=False)


_WS_SETUP = str(UTIL.parent.parent.parent / "ifc2pointcloud" /
                "install" / "setup.bash")


def _save_lio_sam_map():
    # Source both ROS2 and the workspace so lio_sam/srv/SaveMap is resolvable.
    cmd = (
        f"source /opt/ros/humble/setup.bash && "
        f"source {_WS_SETUP} && "
        f"{_ROS2_BIN} service call /lio_sam/save_map lio_sam/srv/SaveMap "
        f"\"{{resolution: 0.0, destination: ''}}\""
    )
    subprocess.run(cmd, shell=True, executable="/bin/bash",
                   check=False, timeout=30)


def stop_ros2_pipeline(proc, logger=None):
    """
    Stops the ROS2 point cloud generation pipeline by terminating the simulation,
    LIO-SAM, and teleop processes.
    """
    _save_lio_sam_map()

    if logger:
        logger.logText("SCAN2GRAPH", "Saved LIO-SAM point cloud")

    for process in proc:
        if process and process.poll() is None:
            _kill_group(process)

    _kill_all_ros2()

    if logger:
        logger.logText("SCAN2GRAPH", "Stopped ROS2 point cloud generation")
