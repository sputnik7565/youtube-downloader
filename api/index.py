# api/index.py
from flask import Flask, render_template, request, redirect, Response, stream_with_context, send_from_directory
from pytubefix import YouTube
import urllib.parse
import subprocess
import tempfile
import os
import threading
import time
import re


# Flask 앱 생성. 템플릿 폴더 경로를 상대 경로로 정확히 지정합니다.
app = Flask(__name__, template_folder='../templates')

# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# 이 부분이 중요합니다! DOWNLOAD_FOLDER 변수가 여기에 정의되어야 합니다.
DOWNLOAD_FOLDER = os.path.abspath('downloads')
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲


def safe_filename(filename):
    """안전한 파일명 생성 함수"""
    # 한글과 영문, 숫자, 공백, 하이픈, 언더스코어만 허용
    safe_chars = re.sub(r'[^\w\s\-가-힣]', '', filename)
    # 연속된 공백을 하나로 줄이고 앞뒤 공백 제거
    safe_chars = re.sub(r'\s+', ' ', safe_chars).strip()
    # 파일명이 너무 길면 자르기 (최대 100자)
    if len(safe_chars) > 100:
        safe_chars = safe_chars[:100]
    return safe_chars if safe_chars else "video"


def encode_filename_for_header(filename):
    """HTTP 헤더용 파일명 인코딩"""
    try:
        # ASCII로 인코딩 가능한지 확인
        filename.encode('ascii')
        return f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        # UTF-8로 인코딩하여 RFC 5987 형식으로 반환
        encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
        return f"attachment; filename*=UTF-8''{encoded_filename}"


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/get_streams', methods=['POST'])
def get_streams():
    url = request.form['url']
    try:
        yt = YouTube(url, client='WEB')
        
        # 모든 비디오 스트림 가져오기
        all_video_streams = []
        
        # 1. Progressive 스트림 (영상+음성이 함께 있는 저화질)
        progressive_streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
        for stream in progressive_streams:
            all_video_streams.append({
                'stream': stream,
                'type': 'progressive',
                'has_audio': True,
                'resolution': stream.resolution
            })
        
        # 2. Adaptive 스트림 (고화질 영상만, 음성 별도)
        adaptive_video_streams = yt.streams.filter(adaptive=True, type='video', file_extension='mp4').order_by('resolution').desc()
        
        # 최고 품질 오디오 스트림 찾기
        best_audio = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        
        for stream in adaptive_video_streams:
            all_video_streams.append({
                'stream': stream,
                'type': 'adaptive',
                'has_audio': False,
                'resolution': stream.resolution,
                'audio_stream': best_audio
            })
        
        # 중복 해상도 제거 (높은 품질 우선)
        seen_resolutions = set()
        unique_video_streams = []
        for item in all_video_streams:
            resolution = item['resolution']
            if resolution and resolution not in seen_resolutions:
                seen_resolutions.add(resolution)
                unique_video_streams.append(item)
        
        # 해상도 순으로 정렬 (높은 해상도부터)
        def resolution_sort_key(item):
            res = item['resolution']
            if res:
                return int(res.replace('p', ''))
            return 0
        
        unique_video_streams.sort(key=resolution_sort_key, reverse=True)
        
        # 오디오 스트림
        audio_streams = yt.streams.filter(only_audio=True).order_by('abr').desc()
        
        return render_template('result.html', 
                            video=yt, 
                            video_streams=unique_video_streams, 
                            audio_streams=audio_streams,
                            original_url=urllib.parse.quote(url))
    except Exception as e:
        return f"""
            <h1>오류가 발생했습니다: {e}</h1>
            <p>유효한 유튜브 URL인지, 또는 비공개 영상이 아닌지 확인해주세요.</p>
            <a href="/youtube-downloader/">돌아가기</a>
        """

           
@app.route('/download')
def download():
    url = request.args.get('url')
    if not url: # URL 인코딩 문제 방지를 위해 unquote는 나중에 합니다.
        return "Missing URL", 400
        
    itag = request.args.get('itag')
    stream_type = request.args.get('type')  # 'progressive' 또는 'adaptive'
    audio_itag = request.args.get('audio_itag')

    if not itag:
        return "Missing itag", 400

    try:
        # URL은 yt-dlp에 전달하기 직전에 디코딩합니다.
        decoded_url = urllib.parse.unquote(url)
        
        yt = YouTube(decoded_url)
        # safe_filename 함수가 없으므로 간단한 버전으로 대체하거나, 이전 코드에서 가져옵니다.
        safe_title = "".join([c for c in yt.title if c.isalnum() or c in (' ', '-')]).rstrip()
        filename = f"{safe_title}_{itag}.mp4"

        command = ['yt-dlp', '--no-warnings']
        if stream_type == 'adaptive' and audio_itag:
            command.extend(['-f', f'{itag}+{audio_itag}', '--merge-output-format', 'mp4'])
        else:
            command.extend(['-f', itag])
        
        command.extend(['-o', '-', decoded_url])

        print(f"Executing streaming command: {' '.join(command)}")

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 실시간 스트리밍 제너레이터
        def generate():
            # stdout에서 데이터를 조각(chunk) 단위로 계속 읽어서 전달
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
            
            # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 오류 확인 로직 추가 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
            # 스트림이 끝나면 프로세스가 종료될 때까지 기다림
            retcode = process.wait()
            if retcode != 0:
                # 오류가 발생했다면, stderr에서 오류 메시지를 읽어서 로그에 출력
                error_output = process.stderr.read().decode('utf-8', errors='ignore')
                error_message = f"yt-dlp failed with return code {retcode}. Error: {error_output}"
                print(error_message) # 터미널(서버 로그)에 에러 출력
                # (선택사항) 사용자에게도 오류를 알리고 싶다면 아래 주석 해제
                # yield error_message.encode('utf-8')
            # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

        content_disposition = encode_filename_for_header(filename)
        return Response(stream_with_context(generate()), mimetype='video/mp4', headers={'Content-Disposition': content_disposition})

    except Exception as e:
        app.logger.error(f"An unexpected error occurred in /download: {e}")
        return f"예상치 못한 오류가 발생했습니다: {str(e)}", 500



# 로컬 테스트용 코드
if __name__ == '__main__':
    app.run(debug=True)