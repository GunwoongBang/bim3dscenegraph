from pathlib import Path
import shutil
import subprocess
import time

UTIL = Path(__file__).parent / "util"


def launch_ros2_pipeline(logger=None):
    if logger:
        logger.logText("SENSOR2GRAPH", "Launching ROS2 simulation...")

    sim_proc = subprocess.Popen(
        [str(UTIL / "run_sim.sh")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(8)  # wait for Gazebo to initialise

    lio_proc = subprocess.Popen(
        [str(UTIL / "run_lio_sam.sh")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    terminal = next(
        (t for t in ("gnome-terminal", "xterm", "konsole", "xfce4-terminal")
         if shutil.which(t)), None
    )
    if terminal is None:
        raise RuntimeError("No terminal emulator found for teleop.")

    teleop_script = str(UTIL / "run_teleop.sh")
    if terminal == "gnome-terminal":
        teleop_proc = subprocess.Popen(
            ["gnome-terminal", "--", "bash", teleop_script])
    elif terminal == "xterm":
        teleop_proc = subprocess.Popen(["xterm", "-e", teleop_script])
    else:
        teleop_proc = subprocess.Popen([terminal, "-e", teleop_script])

    return sim_proc, lio_proc, teleop_proc


def stop_ros2_pipeline(sim_proc, lio_proc, teleop_proc, logger=None):
    if logger:
        logger.logText("SENSOR2GRAPH", "Stopping ROS2 pipeline...")
    for proc in (teleop_proc, lio_proc, sim_proc):
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
