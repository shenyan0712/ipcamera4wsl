
"""
# 使用PySide6获得编号以及对应的相机信息
"""
import time
import cv2
import numpy as np

import json
import threading
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QCoreApplication
from PySide6.QtMultimedia import QCamera, QMediaDevices
import sys

lock = threading.Lock()


class QCameraInfo(QObject):
    # 通知相机帧缓存中已经有图像, 
    # 注：如果需要对图像进行处理一般不用sig_hasImage，因为这样可能会造成GUI卡死，使用RegisterHandle来进行处理
    sig_hasImage = Signal()
    sig_camErr = Signal(QCamera.Error, str)

    def __init__(self):
        super(QCameraInfo, self).__init__()


    # 查询相机, 返回 名称->编号的dict
    def QueryCameras(self) -> dict:
        self.camDevDict = {}
        self.camNumDict = {}
        camDevs = QMediaDevices.videoInputs()
        if len(camDevs)>0:
            self.camDevDict.clear()
        camNum = 0
        for camDev in camDevs:
            self.camDevDict[camDev.description()] = camDev
            self.camNumDict[camDev.description()] = camNum
        return self.camNumDict


    """
    获得当前相机的可用视频格式, 可以通过min_width和min_height来设定最小尺寸
    返回的格式列表形如：
        ['2592x1944 30fps Jpeg', '1920x1080 30fps Jpeg', '1280x720 30fps Jpeg',
        '1280x960 30fps Jpeg', '2048x1536 30fps Jpeg', '1920x1080 3fps YUYV', 
        '1280x720 8fps YUYV', '2592x1944 2fps YUYV', '1280x960 8fps YUYV', '2048x1536 3fps YUYV']
    """
    def GetAvailableFormats(self, camName, min_width=640, min_fps=30, min_height=480, max_height=10000) ->list:
        if camName not in self.camDevDict:
            return []
        curCamDev = self.camDevDict[camName]
        # self.curCam = QCamera()
        formatList = curCamDev.videoFormats()
        self.formatDict = {}
        for camFormat in formatList:
            w = str(camFormat.resolution().width())
            h = str(camFormat.resolution().height())
            if camFormat.resolution().width()<min_width \
                or camFormat.resolution().height()<min_height \
                or camFormat.resolution().height()>max_height \
                or camFormat.minFrameRate()< min_fps :
                continue
            fps = str(int(camFormat.minFrameRate())) + 'fps'

            pf = camFormat.pixelFormat().name   # .decode('utf-8')
            if pf.endswith('Invalid'):
                continue
            # pf = pf.removeprefix('Format_')           # python 3.9
            pf = pf.replace("Format_", "")
            _formatStr = w + 'x' + h + " " + fps + " " + pf
            self.formatDict[_formatStr] = camFormat
        return list(self.formatDict.keys())


if __name__ == "__main__":
    app = QCoreApplication()
    camInfo = QCameraInfo()
    camNums = camInfo.QueryCameras()
    camName = list(camNums.keys())[0]
    print(camNums)
    print(camInfo.GetAvailableFormats(camName, min_width=1280, min_height=960, max_height=960))