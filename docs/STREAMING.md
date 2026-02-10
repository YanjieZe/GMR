# Live Streaming

Real-time motion retargeting from motion capture systems or VR headsets.

---

## PICO VR → Robot (TWIST2)

Real-time streaming from a PICO headset via [XRoboToolkit](https://github.com/XR-Robotics/XRoboToolkit-PC-Service).

### Setup

**On the PICO headset:**

Install the PICO SDK from the [XRoboToolkit Unity Client releases](https://github.com/XR-Robotics/XRoboToolkit-Unity-Client/releases/).

**On your PC:**

1. Install the PC service:
   ```bash
   # Download the deb for Ubuntu 22.04
   wget https://github.com/XR-Robotics/XRoboToolkit-PC-Service/releases/download/v1.0.0/XRoboToolkit_PC_Service_1.0.0_ubuntu_22.04_amd64.deb
   sudo dpkg -i XRoboToolkit_PC_Service_1.0.0_ubuntu_22.04_amd64.deb
   ```
   Or build from [source](https://github.com/XR-Robotics/XRoboToolkit-PC-Service).

   > [!WARNING]
   > Launch the `xrobotoolkit-pc-service` app before starting teleoperation.

2. Build the Python SDK:
   ```bash
   conda activate gmr

   git clone https://github.com/YanjieZe/XRoboToolkit-PC-Service-Pybind.git
   cd XRoboToolkit-PC-Service-Pybind

   # Build the C++ SDK
   mkdir -p tmp && cd tmp
   git clone https://github.com/XR-Robotics/XRoboToolkit-PC-Service.git
   cd XRoboToolkit-PC-Service/RoboticsService/PXREARobotSDK
   bash build.sh
   cd ../../../..

   # Copy headers and library
   mkdir -p lib include
   cp tmp/XRoboToolkit-PC-Service/RoboticsService/PXREARobotSDK/PXREARobotSDK.h include/
   cp -r tmp/XRoboToolkit-PC-Service/RoboticsService/PXREARobotSDK/nlohmann include/nlohmann/
   cp tmp/XRoboToolkit-PC-Service/RoboticsService/PXREARobotSDK/build/libPXREARobotSDK.so lib/

   # Build Python bindings
   conda install -c conda-forge pybind11
   pip uninstall -y xrobotoolkit_sdk
   python setup.py install
   ```

### Run

```bash
# From TWIST2 repo
bash teleop.sh
```

You should see the retargeted robot motion in a MuJoCo window.

---

## OptiTrack → Robot

Real-time streaming from an [OptiTrack](https://www.optitrack.com/) system via Motive.

### Network Setup

You need two machines:
- **Server** — running Motive (OptiTrack desktop app)
- **Client** — running GMR

Find both IP addresses. In Motive, configure streaming:

![OptiTrack Streaming](../assets/optitrack.png)

### Run

```bash
python scripts/optitrack_to_robot.py \
  --server_ip <motive_pc_ip> \
  --client_ip <your_pc_ip> \
  --use_multicast False \
  --robot unitree_g1
```