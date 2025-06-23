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


@app.route('/youtube-downloader/')
def home():
    return render_template('index.html')


@app.route('/youtube-downloader/get_streams', methods=['POST'])
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

           
@app.route('/youtube-downloader/download')
def download():
    url = request.args.get('url')
    itag = request.args.get('itag')
    stream_type = request.args.get('type')  # 'progressive' 또는 'adaptive'
    audio_itag = request.args.get('audio_itag')

    if not url or not itag:
        return "Missing URL or itag", 400

    try:
        yt = YouTube(url)
        safe_title = "".join([c for c in yt.title if c.isalnum() or c in (' ', '-')]).rstrip()
        filename = f"{safe_title}_{itag}.mp4"

        # --- yt-dlp 명령어 구성 ---
        command = [
            'yt-dlp',
            '--no-warnings',
        ]

        if stream_type == 'adaptive' and audio_itag:
            command.extend(['-f', f'{itag}+{audio_itag}', '--merge-output-format', 'mp4'])
        else:
            command.extend(['-f', itag])
        
        # '-o -' 옵션은 출력을 파일이 아닌 표준 출력(stdout)으로 하라는 의미
        command.extend(['-o', '-', url])

        print(f"Executing streaming command: {' '.join(command)}")

        # 실시간으로 데이터 흐름을 처리하기 위한 제너레이터 함수
        def generate():
            # subprocess.run 대신 Popen을 사용하여 프로세스를 시작하고 파이프를 연결
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            try:
                # stdout에서 데이터를 조각(chunk) 단위로 계속 읽어서 전달(yield)
                while True:
                    chunk = process.stdout.read(8192) # 8KB씩 읽기
                    if not chunk:
                        break
                    yield chunk
            finally:
                # 사용자가 다운로드를 중단해도 프로세스가 남지 않도록 정리
                process.terminate()
                process.wait()

        # 인코딩된 헤더 생성 (기존 함수 재활용)
        # 이 함수가 코드에 없는 경우, 이전 버전의 코드에서 가져와야 합니다.
        def encode_filename_for_header(filename):
            try:
                filename.encode('ascii')
                return f'attachment; filename="{filename}"'
            except UnicodeEncodeError:
                import urllib.parse
                encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
                return f"attachment; filename*=UTF-8''{encoded_filename}"
        
        content_disposition = encode_filename_for_header(filename)
        
        # 스트리밍 응답 객체를 생성하여 반환
        return Response(
            stream_with_context(generate()),
            mimetype='video/mp4',
            headers={'Content-Disposition': content_disposition}
        )

    except Exception as e:
        app.logger.error(f"An unexpected error occurred in /download: {e}")
        return f"예상치 못한 오류가 발생했습니다: {str(e)}", 500


# 로컬 테스트용 코드
if __name__ == '__main__':
    app.run(debug=True)