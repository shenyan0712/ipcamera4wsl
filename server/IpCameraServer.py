

import cv2
import socket
import json
import threading
import time

from QCameraInfo import QCameraInfo

"""
根据给定的相机以及分辨率，创建Tcp Server, 当有客户端连接时，开始采集相机图像并传输给客户端

"""
class CameraSocketServer:
    def __init__(self) -> None:
        self.cameraInfo = QCameraInfo()
        self.dataThread = None
        self.ctrlThread = None
        """
        'close' -> 未建立连接时的状态
        'idle' -> 已建立连接，但还未启动发送
        'running' -> 正在进行发送
        """
        self.dataThread_state = "idle"    
        self.exitFlag = False

        # 创建 socket 对象
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    # 相机数据流
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    # 相机控制流
        self.ctrl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.ctrl_cli_socket = None
        # 绑定端口
        self.data_socket.bind(("localhost", 30000))
        self.ctrl_socket.bind(("localhost", 30001))
        # 设置最大连接数，超过后排队
        self.data_socket.listen(2)
        # self.data_socket.settimeout(0.5)
        self.data_socket.setblocking(True)
        self.ctrl_socket.listen(2)
        # self.ctrl_socket.settimeout(0.5)
        self.ctrl_socket.setblocking(True)

        self.cam_idx = -1
        self.width = 640
        self.height = 480
        pass

    # 设置使用的相机以及分辨率
    def SetCamera(self, camNum: int, width: int, height: int)->bool:
        print('SetCamera')
        self.cam_idx = camNum
        self.width = width
        self.height = height
        return True

    """
    Socket处于侦听状态，当有客户端连接时启动线程采集相机图像
    """
    def Start(self):
        self.dataThread = threading.Thread(target=self.dataThread_func)
        self.dataThread.start()
        self.ctrlThread = threading.Thread(target=self.ctrlThread_func)
        self.ctrlThread.start()

    def Stop(self):
        self.exitFlag = True
        self.data_socket.close()
        if self.dataThread is not None and self.dataThread.is_alive():
            self.dataThread.join()
        self.ctrl_socket.close()
        if self.ctrl_cli_socket:
            self.ctrl_cli_socket.close()
        if self.ctrlThread is not None and self.ctrlThread.is_alive():
            self.ctrlThread.join()

    def dataThread_func(self):
        print('dataThread_func')
        while not self.exitFlag:
            # 建立客户端连接
            try:
                print('data_socket listening...')
                client_socket, addr = self.data_socket.accept()
            except:
                # print('data_socket accept time out')
                # time.sleep(0.5)
                continue
            print('data_socket got a connection.')
            self.dataThread_state = 'idle'
            while not self.exitFlag:
                if self.dataThread_state == 'running':
                    try:
                        self.sending_loop(client_socket)
                    except:     #发送通信错误，关闭该连接
                        self.dataThread_state = 'close'
                elif self.dataThread_state == 'close':
                    client_socket.close()
                    break
                else:
                    # print('idle')
                    time.sleep(0.2)

            # 关闭客户端连接
            client_socket.close()
        print('dataThread_func exit.')

    def ctrlThread_func(self):
        print('ctrlThread_func')
        while not self.exitFlag:
            # 建立客户端连接
            try:
                print('ctrl_socket listening...')
                self.ctrl_cli_socket = None
                self.ctrl_cli_socket, addr = self.ctrl_socket.accept()
            except:
                # print('ctrl_socket accept time out')
                continue
            print('ctrl_socket got a connection.')
            while not self.exitFlag:
                try:
                    # 接受客户端的命令
                    recv_data = self.recv_ctrl_pack(self.ctrl_cli_socket)
                except socket.error as e:   # 接受发生错误，则断开连接
                    print("socket err: ", str(e))   
                    self.ctrl_cli_socket.close()
                    self.dataThread_state = 'close'    # 当控制流断开时，也通知数据流断开
                    break
                if len(recv_data)==0:   # 表示socket的recv函数收到了0字节，一般表示远端关闭了连接
                    print('client connection closed.')
                    self.ctrl_cli_socket.close()
                    self.dataThread_state = 'close'
                    break
                print('recv data:', recv_data)
                response = self.handle_ctrl_cmd(recv_data)
                print('send response:', response)
                self.send_ctrl_pack(self.ctrl_cli_socket, response)
        print('ctrlThread_func exit.')

    # 处理控制命令
    def handle_ctrl_cmd(self, cmd: dict)->dict:
        response = {'result': False}
        if 'cmd' not in cmd:
            response['msg'] = 'no cmd'
        elif cmd['cmd'] == 'get_cameras':
            response['result'] = True
            response['cameras'] = self.cameraInfo.QueryCameras()
        elif cmd['cmd'] == 'set_camera':    # 设置将使用的相机，及其对应的分辨率
            cam_idx = cmd['cam_idx']
            width = cmd['width']
            height = cmd['height']
            response['result'] =self.SetCamera(cam_idx, width, height)
        elif cmd['cmd'] == 'get_camera_formats':
            min_width = 640
            min_height = 0
            max_height = 10000
            min_fps = 30
            cam_name = cmd['cam_name']
            if 'min_width' in cmd:
                min_width = int(cmd['min_width'])
            if 'min_fps' in cmd:
                min_fps = int(cmd['min_fps'])
            if 'min_height' in cmd:
                min_height = int(cmd['min_height'])
            if 'max_height' in cmd:
                max_height = int(cmd['max_height'])
            response['result'] = True
            response['formats'] = self.cameraInfo.GetAvailableFormats(cam_name, min_width=min_width, min_fps=min_fps, min_height=min_height, max_height=max_height)
        elif cmd['cmd'] == 'capture':
            self.dataThread_state = 'running' # 通知数据线程开始发送图像数据
            response['result'] = True
        elif cmd['cmd'] == 'stop_capture':
            self.dataThread_state = 'idle'
            response['result'] = True
        return response

    # 不断地发生相机数据到客户端
    def sending_loop(self, cli_socket: socket.socket):
        if self.cam_idx <0:
            self.dataThread_state = "idle"
            return
        """
        # 初始化cv相机
        opencv在获取相机图像时发现一个问题，即常规的cap=VideoCapture(0)不能获得1280x960分辨率的图像。
        单独只改用CAP_DSHOW后端会出现低帧率的情况，还需要设置CAP_PROP_FOURCC。
        """
        cap = cv2.VideoCapture(self.cam_idx, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        # cap.set(cv2.CAP_PROP_FPS, 30)
        # 进入相机图像发送状态
        while not self.exitFlag and self.dataThread_state == 'running':
            # 读取相机
            ret, frame = cap.read()     # frame为(h,w,3)的numpy数组，类型为uint8
            if frame is None:
                continue
            if True:    # 启用压缩
                # opencv method
                result = cv2.imencode('.jpg', frame)[1] # result为压缩后的一维numpy数组
                send_bytes = result.tobytes() 
            else:
                send_bytes = frame.tobytes()

            # 先发送四个字节的数据长度
            # print(time.asctime(), send_bytes.__len__())
            length_info = send_bytes.__len__().to_bytes(4, byteorder='big')
            cli_socket.sendall(length_info)
            # 再发送图像数据
            cli_socket.sendall(send_bytes)
        print('exit from sending_loop')

    # 用于ctrl_socket，发送一个控制数据包
    def send_ctrl_pack(self, cli_socket:socket.socket, data: dict):
        jsonObj = json.dumps(data)
        send_data = bytes(jsonObj, 'utf-8')
        # 先发送4字节长度信息
        length_info = send_data.__len__().to_bytes(4, byteorder='big')
        cli_socket.sendall(length_info)
        # 再发送实际数据
        cli_socket.sendall(send_data)
        pass

    # 用于ctrl_socket, 接收一个应答数据包
    def recv_ctrl_pack(self, cli_socket:socket.socket)->dict:
        # 先接受4字节长度信息
        recv_bytes = cli_socket.recv(4, socket.MSG_WAITALL)
        data_len = int.from_bytes(recv_bytes, byteorder='big')
        if data_len ==0:
            return {}
        # 接收实际的数据
        recv_bytes = cli_socket.recv(data_len, socket.MSG_WAITALL)
        json_txt = recv_bytes.decode('utf-8')
        data = json.loads(json_txt)
        # print(f"Received message:", print(data))
        return data


if __name__ == "__main__":
    server = CameraSocketServer()
    server.Start()
    try:
        cnt = 0
        while True:
            if cnt%20==0:
                print('tick:', time.asctime())
            time.sleep(0.2)
            cnt+=1
    except:
        server.Stop()
        print('service exit.')

