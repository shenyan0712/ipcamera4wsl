
import cv2
import numpy as np
import time
import socket
import json
import threading
import copy


"""
用于wsl的网络相机客户端，初始化完成后，可以像OpenCV一样使用read()函数读取图像帧
"""


lock = threading.Lock()

class IpCameraClient:
    def __init__(self) -> None:
        self.dataThread = None      # 该线程用于不断地接收来自远端的相机图像数据
        self.handleThread = None    # 当有新图像时，调用处理函数
        self.exitFlag = False
        self.handler = None
        self.hasNewImg = False
        self.cur_cvImg = np.array([])   # 判断是否有效：shape==(0,)
        # 创建 socket 对象
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.settimeout(1.0)    # 因为是本机通信，所以1.0算比较大的值
        self.ctrl_socket.settimeout(1.0)

        # 增大接收buffer的尺寸有助于提高网络传输的速率
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
        self.recv_bufsize = self.data_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
        print(self.recv_bufsize)

        self.matrix = np.array([])
        self.distortion = np.array([])

        self.cam_idx = 0
        self.width = 1280
        self.height = 720
        self.mode = 'cv'

    """
    默认使用OpenCV模式, 即通过read()来读取每一帧数据
    """
    def connect(self, ip='localhost', port=30000, mode: str='cv'):
        # 连接服务器
        try:
            self.data_socket.connect((ip, port))
            self.ctrl_socket.connect((ip, port+1))
            self.data_socket.settimeout(99999.0)        # 
            self.ctrl_socket.settimeout(99999.0)
            self.dataThread = threading.Thread(target=self.dataThread_func)
            self.dataThread.start()
            self.mode = mode
            if mode=='qt':
                self.handleThread = threading.Thread(target=self.handleThread_func)
                self.handleThread.start()
            return True
        except:
            return False
 
    def disconnect(self):
        self.data_socket.close()
        self.ctrl_socket.close()
        self.exitFlag = True
        if self.dataThread is not None and self.dataThread.is_alive():
            self.dataThread.join()

    # 返回dict, cam_name -> cam_idx
    def get_cameras(self) ->dict:
        cmd = {'cmd':'get_cameras'}
        self.send_ctrl_pack(self.ctrl_socket, cmd)
        response = self.recv_ctrl_pack(self.ctrl_socket)
        print(response)
        if response['result']:
            return response['cameras']
        else:
            return {}

    def set_camera(self, cam_idx, width, height)->bool:
        cam_info = {'cmd':'set_camera', 'cam_idx': cam_idx, 'width': width, 'height': height}
        self.send_ctrl_pack(self.ctrl_socket, cam_info)
        response = self.recv_ctrl_pack(self.ctrl_socket)
        print(response)
        return response['result']

    def get_camera_formats(self, cam_name:str, min_width=640, min_fps = 30, min_height=0, max_height=10000) ->list:
        cmd = {'cmd': 'get_camera_formats', 'cam_name': cam_name, 'min_width':min_width, 'min_fps': min_fps, 'min_height':min_height, 'max_height': max_height}
        self.send_ctrl_pack(self.ctrl_socket, cmd)
        response = self.recv_ctrl_pack(self.ctrl_socket)
        print(response)
        if response['result']:
            return response['formats']
        else:
            return []

    # 载入相机校正参数, 目前仅用于'cv'模式
    def load_undist_params(self, filePathStr):
        self.matrix = np.array([])
        self.distortion = np.array([])
        with open(str(filePathStr), 'r') as f:
            params = json.load(f)
        if len(params)==0:
            return False
        if 'distortion' not in params and \
                'matrix' not in params:
            return False
        self.distortion = np.array(params['distortion'])
        if self.distortion.shape == (5,):
            self.distortion = self.distortion.reshape(1,5)
        self.matrix = np.array(params['matrix'])
        if self.distortion.shape != (1, 5) and self.distortion.shape != (5, 1):
            self.matrix = np.array([])
            self.distortion = np.array([])
            return False
        if self.matrix.shape != (3, 3):
            self.matrix = np.array([])
            self.distortion = np.array([])
            return False
        return True

    def set_handler(self, handler):
        self.handler = handler

    def start_capture(self)->bool:
        cmd={'cmd': 'capture'}
        self.send_ctrl_pack(self.ctrl_socket, cmd)
        response = self.recv_ctrl_pack(self.ctrl_socket)
        print(response)
        return response['result']
    
    def stop_capture(self)->bool:
        cmd={'cmd': 'stop_capture'}
        self.send_ctrl_pack(self.ctrl_socket, cmd)
        response = self.recv_ctrl_pack(self.ctrl_socket)
        print(response)
        return response['result']       

    def get_last_cvImg(self):
        lock.acquire()
        cvImg =  copy.deepcopy(self.cur_cvImg)
        lock.release()
        return cvImg
    
    # 用于OpenCV阻塞式读取图像帧
    def read(self):
        while not self.exitFlag:
            if self.hasNewImg:
                lock.acquire()
                cvImg =  copy.deepcopy(self.cur_cvImg)
                if self.matrix.shape==(3,3):
                    cvImg = cv2.undistort(cvImg, self.matrix, self.distortion)
                lock.release()
                return cvImg
            time.sleep(0.02)

    def dataThread_func(self):
        print('dataThread_func')
        while not self.exitFlag:
            try:
                frame = self.recv_data_pack(self.data_socket)
                # print(time.asctime(), frame.shape)
                lock.acquire()
                self.cur_cvImg = copy.deepcopy(frame)
                self.hasNewImg = True
                lock.release()
            except Exception as e:
                print(f"Error: {e}")
                self.exitFlag = True
                break
        print('dataThread_func exit')

    def handleThread_func(self):
        while not self.exitFlag:
            if self.hasNewImg:
                if self.handler is not None:
                    lock.acquire()
                    self.handler(self.cur_cvImg)
                    self.hasNewImg = False
                    lock.release()
            else:
                time.sleep(0.01)
        print('handleThread_func exit')

    # 用于ctrl_socket，发送一个控制数据包
    def send_ctrl_pack(self, cli_socket:socket.socket, data: dict):
        jsonObj = json.dumps(data)
        print("send json:", jsonObj)
        send_data = bytes(jsonObj, 'utf-8')
        print("length: ", send_data.__len__())
        # 先发送4字节长度信息
        length_info = send_data.__len__().to_bytes(4, byteorder='big')
        print('sent:', cli_socket.send(length_info))
        # 再发送实际数据
        print('sent:', cli_socket.send(send_data))
        pass

    # 用于ctrl_socket, 接收一个应答数据包
    def recv_ctrl_pack(self, cli_socket:socket.socket)->dict:
        # 先接受4字节长度信息
        recv_bytes = cli_socket.recv(4)
        data_len = int.from_bytes(recv_bytes, byteorder='big')
        # 接收实际的数据
        recv_bytes = cli_socket.recv(data_len)
        json_txt = recv_bytes.decode('utf-8')
        data = json.loads(json_txt)
        # print(f"Received message:", print(data))
        return data

    # 用于data_socket, 接收一个相机图像帧
    def recv_data_pack(self, cli_socket:socket.socket):
        # 先接受4字节长度信息
        recv_bytes = cli_socket.recv(4)
        total_len = int.from_bytes(recv_bytes, byteorder='big')
        # print('img data len:', total_len)
        # 接收实际的图像数据
        recv_bytes =b''
        while len(recv_bytes) < total_len:
            to_read = total_len - len(recv_bytes)
            recv_bytes += cli_socket.recv(
                self.recv_bufsize if to_read > self.recv_bufsize else to_read)
        img_arr = np.frombuffer(recv_bytes, np.uint8)
        if True:     # 启用压缩的话，需解压缩
            # opencv method
            img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        else:
            img =img.reshape([self.height, self.width, 3])
        return img

    def __del__(self):  
        self.disconnect()



if __name__ == "__main__":
    client = IpCameraClient()
    if not client.connect():
        print('cannot connect to server')
        exit(-1)
    cam_dict = client.get_cameras()
    if len(cam_dict) == 0:
        print('no camera available.')
        exit(-1)
    cam_names = list(cam_dict.keys())
    formats = client.get_camera_formats(cam_names[0])
    print(formats)
    if not client.set_camera(0, 1280, 960):
        print('cannot set camera')
        exit(-1)
    client.start_capture()
    cv2.namedWindow('camera', cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            img = client.read()
            # print(img.shape)
            cv2.imshow('camera', img)
            key = cv2.waitKey(1)
            if key == 27:
                break
    except:
        client.stop_capture()

    # time.sleep(2)
    # print('start capture again')
    # client.start_capture()
    # try:
    #     # while True:
    #     for i in range(5):
    #         time.sleep(1)
    # except:
    #     client.stop_capture() 

    client.disconnect()
    print('exit.')