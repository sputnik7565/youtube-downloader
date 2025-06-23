# api/index.py
from flask import Flask, render_template, request, redirect, Response, stream_with_context
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
    url = urllib.parse.unquote(request.args.get('url'))
    itag = request.args.get('itag')
    download_type = request.args.get('type', 'progressive')
    audio_itag = request.args.get('audio_itag')
    
    try:
        yt = YouTube(url, client='WEB')
        
        if download_type == 'progressive':
            # Progressive 스트림 (영상+음성 함께)
            stream = yt.streams.get_by_itag(itag)
            return redirect(stream.url)
        
        elif download_type == 'adaptive':
            # Adaptive 스트림 (영상+음성 분리, FFmpeg로 합치기)
            video_stream = yt.streams.get_by_itag(itag)
            audio_stream = yt.streams.get_by_itag(audio_itag)
            
            if not video_stream or not audio_stream:
                return "비디오 또는 오디오 스트림을 찾을 수 없습니다."
            
            # 안전한 파일명 생성
            safe_title = safe_filename(yt.title)
            filename = f"{safe_title}_{video_stream.resolution}.mp4"
            
            # 디버깅 정보 출력
            print(f"=== 스트림 정보 ===")
            print(f"Video URL: {video_stream.url}")
            print(f"Audio URL: {audio_stream.url}")
            print(f"Video itag: {video_stream.itag}")
            print(f"Audio itag: {audio_stream.itag}")
            print(f"Video resolution: {video_stream.resolution}")
            print(f"Audio bitrate: {audio_stream.abr}")
            
            def generate():
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_video = os.path.join(temp_dir, "video.mp4")
                    temp_audio = os.path.join(temp_dir, "audio.mp4")
                    temp_output = os.path.join(temp_dir, "output.mp4")
                    
                    try:
                        print("=== 비디오 다운로드 시작 ===")
                        # 1단계: 비디오 파일 다운로드
                        video_stream.download(output_path=temp_dir, filename="video.mp4")
                        
                        print("=== 오디오 다운로드 시작 ===")
                        # 2단계: 오디오 파일 다운로드
                        audio_stream.download(output_path=temp_dir, filename="audio.mp4")
                        
                        # 파일 존재 및 크기 확인
                        if not os.path.exists(temp_video):
                            yield "비디오 파일 다운로드 실패".encode('utf-8')
                            return
                        if not os.path.exists(temp_audio):
                            yield "오디오 파일 다운로드 실패".encode('utf-8')
                            return
                            
                        video_size = os.path.getsize(temp_video)
                        audio_size = os.path.getsize(temp_audio)
                        print(f"Video size: {video_size} bytes")
                        print(f"Audio size: {audio_size} bytes")
                        
                        if video_size == 0 or audio_size == 0:
                            yield "다운로드된 파일이 비어있습니다.".encode('utf-8')
                            return
                        
                        print("=== FFmpeg 합성 시작 ===")
                        # 3단계: FFmpeg로 합성
                        cmd = [
                            'ffmpeg',
                            '-i', temp_video,
                            '-i', temp_audio,
                            '-c:v', 'copy',
                            '-c:a', 'copy',
                            '-f', 'mp4',
                            '-movflags', 'faststart',
                            '-y',
                            temp_output
                        ]
                        
                        print(f"FFmpeg 명령어: {' '.join(cmd)}")
                        
                        # FFmpeg 실행
                        process = subprocess.run(
                            cmd,
                            capture_output=True,
                            timeout=300,
                            text=True
                        )
                        
                        print(f"FFmpeg return code: {process.returncode}")
                        if process.stderr:
                            print(f"FFmpeg stderr: {process.stderr}")
                        if process.stdout:
                            print(f"FFmpeg stdout: {process.stdout}")
                        
                        if process.returncode != 0:
                            error_msg = f"FFmpeg 오류 (코드: {process.returncode}): {process.stderr}"
                            yield error_msg.encode('utf-8')
                            return
                        
                        # 생성된 파일 확인
                        if not os.path.exists(temp_output):
                            yield "출력 파일이 생성되지 않았습니다.".encode('utf-8')
                            return
                            
                        output_size = os.path.getsize(temp_output)
                        print(f"Output size: {output_size} bytes")
                        
                        if output_size == 0:
                            yield "출력 파일이 비어있습니다.".encode('utf-8')
                            return
                        
                        print("=== 파일 전송 시작 ===")
                        # 4단계: 파일 전송
                        try:
                            with open(temp_output, 'rb') as f:
                                sent_bytes = 0
                                while True:
                                    chunk = f.read(8192)
                                    if not chunk:
                                        break
                                    sent_bytes += len(chunk)
                                    yield chunk
                                print(f"전송 완료: {sent_bytes} bytes")
                        except Exception as e:
                            print(f"파일 전송 오류: {str(e)}")
                            yield f"파일 전송 오류: {str(e)}".encode('utf-8')
                        
                    except subprocess.TimeoutExpired:
                        error_msg = "처리 시간이 초과되었습니다."
                        print(error_msg)
                        yield error_msg.encode('utf-8')
                    except Exception as e:
                        error_msg = f"처리 중 오류 발생: {str(e)}"
                        print(error_msg)
                        yield error_msg.encode('utf-8')
            
            # 인코딩된 헤더 생성
            content_disposition = encode_filename_for_header(filename)
            
            return Response(
                stream_with_context(generate()),
                mimetype='video/mp4',
                headers={
                    'Content-Disposition': content_disposition,
                    'Content-Type': 'video/mp4',
                    'Cache-Control': 'no-cache'
                }
            )
        
        elif download_type == 'audio':
            # 오디오만 다운로드
            stream = yt.streams.get_by_itag(itag)
            return redirect(stream.url)
            
    except Exception as e:
        return f"""
            <h1>다운로드 중 오류가 발생했습니다: {e}</h1>
            <p>다음 사항을 확인해주세요:</p>
            <ul>
                <li>FFmpeg가 시스템에 설치되어 있는지 확인</li>
                <li>인터넷 연결이 안정적인지 확인</li>
                <li>유튜브 영상이 여전히 공개 상태인지 확인</li>
            </ul>
            <a href="/youtube-downloader/">돌아가기</a>
        """


# 로컬 테스트용 코드
if __name__ == '__main__':
    app.run(debug=True)