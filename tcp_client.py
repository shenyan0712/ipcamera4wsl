import socket
 
# 创建 socket 对象
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
 
# 获取本地主机名
host = "localhost" #socket.gethostname()
 
# 设置端口
port = 12345
 
# 连接服务器
client_socket.connect((host, port))
 
# 发送数据到服务器
client_socket.send(b'Hello, Server!')
 
# 接收服务器发送的数据
message = client_socket.recv(1024)
print(f"Received message: {message.decode('utf-8')}")
 
# 关闭客户端 socket
client_socket.close()