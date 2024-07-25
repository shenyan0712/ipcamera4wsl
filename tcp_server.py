import socket
import time
 
# 创建 socket 对象
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


# 获取本地主机名
host = "localhost" # socket.gethostname()
 
# 设置一个端口
port = 12345
 
# 绑定端口
server_socket.bind((host, port))
 
# 设置最大连接数，超过后排队
server_socket.listen(5)
server_socket.settimeout(0.5)
# server_socket.setblocking(False)
 
while True:
    # 建立客户端连接
    try:
        client_socket, addr = server_socket.accept()
    except:
        print('time out')
        # time.sleep(0.1)
        continue
 
    # 接收客户端发送的数据
    message = client_socket.recv(1024).decode('utf-8')
    print(f"Received message: {message}")
 
    # 发送数据到客户端
    client_socket.send(b'Hello, Client!')
 
    # 关闭客户端连接
    client_socket.close()