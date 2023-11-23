
# io 모듈은 파일 I/O(입출력) 작업을 위한 Python의 핵심 기능을 제공
# 이 경우, io.BufferedIOBase는 바이너리 스트림에 대한 버퍼링된 인터페이스를 제공하는 기본 클래스
import io

# logging 모듈은 Python에서 로깅을 할 수 있게 해주는 모듈
# 이를 통해 오류 메시지나 정보를 로그로 기록
import logging

# socketserver 모듈은 네트워크 서버를 쉽게 구현할 수 있게 도와주는 클래스와 함수들을 제공
# 이 경우, ThreadingMixIn은 멀티스레드 서버를 구현하는 데 사용
import socketserver

# http.server 모듈은 HTTP 서버를 구현하는 클래스와 함수들 제공
# BaseHTTPRequestHandler 클래스는 HTTP 요청을 처리하는 기본 핸들러
from http import server

# threading 모듈은 스레드 기반 병렬 처리 지원
# Condition은 스레드 간 상호 배제와 조건 변수를 제공하여 스레드 동기화 수행
from threading import Condition

# picamera2 라이브러리는 Raspberry Pi의 카메라 모듈을 사용하기 위한 인터페이스 제공
# 아래 라이브러리를 사용하여 카메라로부터 영상 캡처 및 스트리밍기능 제공
from picamera2 import Picamera2
# JpegEncoder는 JPEG 형식으로 영상을 인코딩하는 기능 제공
from picamera2.encoders import JpegEncoder
# FileOutput은 파일로 출력하는 기능을 제공하며 여기서는 스트리밍 데이터를 파일로 핸들링
from picamera2.outputs import FileOutput



# 매직 넘버를 사용하지 않기 위한 상수 선언
SERVER_PORT = 8080  # 서버가 사용할 포트 번호
CAMERA_RESOLUTION = (640, 480)  # 카메라 해상도
STREAM_WIDTH = 640  # 스트리밍될 비디오의 너비
STREAM_HEIGHT = 480  # 스트리밍될 비디오의 높이

# HTML 페이지의 내용 정의. (웹 브라우저에서 보여질 스크립트)
PAGE_TEMPLATE = """
<html>
<head>
<title>picamera2 MJPEG streaming</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming</h1>
<img src="stream.mjpg" width="{width}" height="{height}" />
</body>
</html>
"""

# 스트리밍 출력을 위한 클래스로 이 클래스는 카메라에서 오는 데이터를 처리
class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None  # 현재 비디오 프레임을 저장할 변수
        self.condition = Condition()  # 스레드 간 동기화를 위한 조건 변수

    def write(self, buf):
        # 카메라에서 새로운 프레임이 오면 이 함수가 호출
        with self.condition:
            self.frame = buf  # 새 프레임을 저장
            self.condition.notify_all()  # 다른 스레드에게 알림



# HTTP 요청을 처리하는 클래스
class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        # 클라이언트가 웹 페이지를 요청하면 이 함수가 호출
        if self.path == '/':
            self.redirect_to_index()  # 홈페이지로 리다이렉트
        elif self.path == '/index.html':
            self.handle_index_page()  # HTML 페이지를 보여주는 함수
        elif self.path == '/stream.mjpg':
            self.handle_mjpeg_stream()  # MJPEG 스트림을 처리 함수
        else:
            self.send_error(404)  # 요청한 페이지가 없으면 404 에러 출력

    def redirect_to_index(self):
        # 클라이언트를 index 페이지로 리다이렉트
        self.send_response(301)
        self.send_header('Location', '/index.html')
        self.end_headers()

    def handle_index_page(self):
        # HTML 페이지의 내용을 클라이언트에게 전송
        content = PAGE_TEMPLATE.format(width=STREAM_WIDTH, height=STREAM_HEIGHT).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def handle_mjpeg_stream(self):
        # 비디오 스트리밍을 처리
        self.send_response(200)
        self.send_no_cache_headers()
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.end_headers()
        self.stream_video_frames()

    def send_no_cache_headers(self):
        # 캐시방지 헤더 설정
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Pragma', 'no-cache')

    def stream_video_frames(self):
        # 비디오 프레임을 라이브로 클라이언트에게 전송
        try:
            while True:
                with output.condition:
                    output.condition.wait()  # 새 프레임이 준비될 때까지 대기
                    frame = output.frame  # 준비된 프레임 가져옴
                # 클라이언트에게 프레임 전송
                self.wfile.write(b'--FRAME\r\n')
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Content-Length', len(frame))
                self.end_headers()
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except Exception as e:
            # 스트리밍 중 오류가 발생하면 경고 메시지를 출력
            logging.warning('Streaming interrupted: %s', str(e))

# 멀티스레드 지원 HTTP 서버 클래스
class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True  # 주소 재사용을 허용
    daemon_threads = True  # 데몬 스레드를 사용

# 메인 함수
def main():
    picam2 = Picamera2()
    # 카메라 해상도 설정
    picam2.configure(picam2.create_video_configuration(main={"size": CAMERA_RESOLUTION}))
    global output  # 전역 변수 
    output = StreamingOutput()
    # 카메라로부터 스트리밍 시작
    picam2.start_recording(JpegEncoder(), FileOutput(output))

    try:
        # 서버를 초기화 및 실행
        address = ('0.0.0.0', SERVER_PORT)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        # 프로그램이 종료되면 카메라 스트리밍도 중지
        picam2.stop_recording()

# 이 파일이 직접 실행될 때만 main 함수를 실행
if __name__ == '__main__':
    main()
