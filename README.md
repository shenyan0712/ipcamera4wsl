# ipcamera4wsl

This is a simple tool for accessing cameras in WSL linux using pure TCP communication. 

### Advantage

This tool use PySide6(Qt) to obtain camera infomations and to config cameras, which is much helper for computer with multiple cameras and choosing right resolutions.

## Usage

### server

server runs on Windows 10/11, only OpenCV and PySide6 are required.

```bash
python server/IpCameraServer.py
```

then camera server remains running until you turn it off.

### client

client runs on WSL Ubuntu or other linux distrubitions based on WSL. 

for demonstration just run:

```bash
python client/IpCameraClient_demo.py
```

