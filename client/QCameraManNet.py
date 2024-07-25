
"""
# 基于PySide6的相机处理框架
# 测试中PySide6-6.6之后版本才能获取win11下的相机信息
"""
import time
import cv2
import numpy as np

import json
import threading
from pathlib import Path
from PySide6.QtWidgets import QMainWindow, QLabel, QApplication, QMessageBox
from PySide6.QtGui import QCloseEvent, QPixmap, QImage
import sys

from IpCameraClient import IpCameraClient

import ImageFuncs
# lock = threading.Lock()


IP="localhost"

"""
camera_socket_client可以看做是对CameraSocketClient的一个简单封装
"""
class QCameraMan:
    def __init__(self):
        self.captured = False                       # 是否捕获图像标志
        self.handler = None
        self.camParams = {}                         # 相机参数，包括相机内参矩阵('matrix')，畸变系数('distortion')等
        self.needRectification = False                # 若此项为False则输出的图像不进行校正
        self.cam_name = ""                          # 当前相机的名称
        self.cur_format = ""                        # 当前相机当前使用的格式
        self.formats = []                           # 当前相机支持的格式
        self.cam_dict = {}                          # key为相机名称，value为对应的索引号 

        self.resolution =(0, 0)
        self.client = IpCameraClient()
        self.client.set_handler(self.img_preHandle)

    # 连接到相机服务端
    def Init(self) ->bool:
        return self.client.connect(mode='qt')
    
    # 程序退出时必须调用该method，不然其线程不会
    def DeInit(self):
        self.client.stop_capture()
        self.client.disconnect()

    # 查询相机, 返回 名称->QCameraDevice字典
    def QueryCameras(self) -> list:
        self.cam_dict =  self.client.get_cameras()
        return list(self.cam_dict.keys())

    """ 
    选中一个相机作为当前相机, 返回该相机支持的格式,可以通过min_width和min_height来设定最小尺寸
    返回的格式列表形如：
        ['2592x1944 30fps Jpeg', '1920x1080 30fps Jpeg', '1280x720 30fps Jpeg',
        '1280x960 30fps Jpeg', '2048x1536 30fps Jpeg', '1920x1080 3fps YUYV', 
        '1280x720 8fps YUYV', '2592x1944 2fps YUYV', '1280x960 8fps YUYV', '2048x1536 3fps YUYV']
    """
    def SetCurCamera(self, cam_name: str, min_width=640, min_fps=30, min_height=0, max_height=10000) -> list:
        print('SetCurCamera: ', cam_name)
        if cam_name not in self.cam_dict:
            return False
        self.cam_name = cam_name
        self.formats = self.client.get_camera_formats(self.cam_name, min_width, min_fps, min_height, max_height)
        return self.formats

    def GetCurCamName(self)->str:
        return self.cam_name

    def GetResolution(self)->tuple:
        return self.resolution

    def SetRectificationFlag(self, flag:bool):
        self.needRectification = flag

    """
    设置当前相机的视频格式
    """
    def SetFormat(self, formatStr: str) -> bool:
        if self.cam_name not in self.cam_dict:
            return False
        cam_idx = self.cam_dict[self.cam_name]
        if formatStr not in self.formats:
            return False
        # 从格式字串中解析出width和height
        resolution = formatStr.split(" ")[0].split('x')
        w, h= (int(resolution[0]), int(resolution[1]))
        if self.client.set_camera(cam_idx, w, h):
            self.cur_format = formatStr
            self.resolution =(w, h)
            return True
        else:
            return False
    
    """
    从文件载入相机对应格式的参数
    """
    def LoadParamFromFile(self, filePath:Path, fmtStr: str):
        resolution = fmtStr.split(" ")[0].split('x')
        w, h= (int(resolution[0]), int(resolution[1]))
        if not filePath.exists():
            print('camera param file %s does not exist.'%str(filePath))
            return False
        params = {}
        with open(str(filePath), 'r') as f:
            params = json.load(f)
        if len(params)==0:
            return False
        if 'distortion' not in params and \
                'matrix' not in params:
            return False
        distortion = np.array(params['distortion'])
        if distortion.shape == (5,):
            distortion = distortion.reshape(1,5)
        matrix = np.array(params['matrix'])
        if distortion.shape != (1, 5) and distortion.shape != (5, 1):
            return False
        if matrix.shape != (3, 3):
            return False
        # 分辨率要一致
        if w != params['width'] or h !=params['height']:
            print('param file err: resolution dos not match.')
            return False
        self.camParams = params
        self.camParams['distortion'] = distortion
        self.camParams['matrix'] = matrix
        return True

    def LoadParamFromDir(self, dir: Path,  camName:str, fmtStr: str):
        if camName not in self.cam_dict:
            return False
        resolution = fmtStr.split(" ")[0]
        # w, h= resolution.split('x')
        fileName = camName + "@" + resolution + ".json"
        paramFilePath = Path(dir) / fileName
        # camera_conf = None
        return self.LoadParamFromFile(paramFilePath, fmtStr)

    # 获得当前相机的内参矩阵K， 前提条件为使用SetFormat对相机设置了视频格式
    def GetK(self):
        print('GetK')
        if self.camParams is None:
            return np.eye(3)
        else:
            return self.camParams['matrix']

    # 注册当捕获图像时的处理函数
    def set_handler(self, handler):
        self.handler = handler
        # self.client.set_handler(handler)

    # 启动当前相机
    def StartCamera(self)->bool:
        if self.cam_name not in self.cam_dict:
            return False
        return self.client.start_capture()

    def StopCamera(self):
        # if self.curCamName not in self.camDict:
            # return
        self.client.stop_capture()
        print('camera stopped')

    # 预处理图像
    def img_preHandle(self, cvImg):
        # 进行图像校正
        if self.needRectification and self.camParams is not None and len(self.camParams)!=0:
            cvImg = cv2.undistort(cvImg, self.camParams['matrix'],
                                self.camParams['distortion'])        

        if self.handler is not None:
            # print(time.asctime(), cvImg.shape)
            self.handler(cvImg)

    def GetCvImage(self):
        return self.client.get_last_cvImg()

    def __del__(self):
        self.DeInit()


class TestWin(QMainWindow):
    def __init__(self):
        super(TestWin, self).__init__()
        self.imgLbl = QLabel()
        self.setCentralWidget(self.imgLbl)
        self.cameraMan = QCameraMan()
        if not self.cameraMan.Init():
            QMessageBox.critical(self, "错误", "无法连接到相机服务端")
            exit(-1)
        camList = self.cameraMan.QueryCameras()
        if len(camList) == 0:
            print('No camera exists')
            exit(-1)
        formats = self.cameraMan.SetCurCamera(camList[0], 1280)       # 设置当前相机
        if len(formats) ==0:
            print("set camera err.")
            return
        print(formats)
        sel_fmt_idx = 7
        # print('has param file:', self.cameraMan.HasParamFile(formats[2]))  # 查看是否给定格式有对应的参数文件
        print('set format %s:'%formats[sel_fmt_idx], self.cameraMan.SetFormat(formats[sel_fmt_idx]))
        camParamFilePath = Path("/home/arczee/workspace/delta_ros2_ws/src/delta_python/delta_python/camera_calibration/USB Video Device@1280x960.json")
        ret = self.cameraMan.LoadParamFromFile(camParamFilePath, formats[sel_fmt_idx])
        print('config param: ', ret)
        self.cameraMan.SetCalibrationFlag(True)

        self.cameraMan.StartCamera()
        self.cameraMan.set_handler(self.hasImage_handle)

    def hasImage_handle(self, cvImg):
        # print('cameraMan_hasImage')
        # cvImg = self.cameraMan.GetCvImage()
        if cvImg is None or cvImg.shape==(0,):
            return
        qimg = ImageFuncs.CvImg2QImg(cvImg)
        pixmap = QPixmap(qimg)
        self.imgLbl.setPixmap(pixmap)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        print('window closed')
        self.cameraMan.DeInit()
        return super().closeEvent(event)

    # def 



def get_camera_info():
    print('test')
    cameraMan = QCameraMan()
    if not cameraMan.Init():
        print("无法连接到相机服务端")
        return
    camNames = cameraMan.QueryCameras()
    formats = cameraMan.SetCurCamera(camNames[0], min_height=960, max_height=960)       # 设置当前相机
    print(formats)
    # cameraMan.DeInit()

    # print('has param file:', cameraMan.HasParamFile(formats[2]))  # 查看是否给定格式有对应的参数文件

    # # print('set format %s:'%formats[2], cameraMan.SetFormat(formats[2]))
    # print('set format %s:'%formats[2], cameraMan.SetFormat(formats[2]))
    # ret = cameraMan.ConfigParam("../camera_calibration/USB Video Device@1280x720.json")
    # print('K:', cameraMan.GetK())

def main():
    app = QApplication()
    win = TestWin()

    win.show()
    app.exec()


if __name__ == "__main__":
    get_camera_info()
    main()

