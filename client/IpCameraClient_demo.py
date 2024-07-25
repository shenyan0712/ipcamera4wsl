

import cv2
from IpCameraClient import IpCameraClient


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

    client.disconnect()
    print('exit.')