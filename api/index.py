# api/index.py
from flask import Flask, render_template, request, redirect, Response, stream_with_context
from pytubefix import YouTube
import urllib.parse
import subprocess
import tempfile
import os
import threading
import time


# Flask 앱 생성. 템플릿 폴더 경로를 상대 경로로 정확히 지정합니다.
app = Flask(__name__, template_folder='../templates')


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
            <a href="/">돌아가기</a>
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
            safe_title = "".join(c for c in yt.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_{video_stream.resolution}.mp4"
            
            def generate():
                with tempfile.TemporaryDirectory() as temp_dir:
                    try:
                        # FFmpeg로 비디오와 오디오 합치기
                        cmd = [
                            'ffmpeg',
                            '-i', video_stream.url,
                            '-i', audio_stream.url,
                            '-c', 'copy',  # 재인코딩 없이 복사
                            '-f', 'mp4',
                            '-movflags', 'frag_keyframe+empty_moov',  # 스트리밍 최적화
                            'pipe:1'  # stdout으로 출력
                        ]
                        
                        process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )
                        
                        # 데이터를 청크 단위로 스트리밍
                        while True:
                            chunk = process.stdout.read(8192)
                            if not chunk:
                                break
                            yield chunk
                        
                        process.wait()
                        
                    except Exception as e:
                        yield f"Error: {str(e)}".encode()
            
            return Response(
                stream_with_context(generate()),
                mimetype='video/mp4',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Type': 'video/mp4'
                }
            )
        
        elif download_type == 'audio':
            # 오디오만 다운로드
            stream = yt.streams.get_by_itag(itag)
            return redirect(stream.url)
            
    except Exception as e:
        return f"""
            <h1>다운로드 중 오류가 발생했습니다: {e}</h1>
            <p>FFmpeg가 설치되어 있는지 확인해주세요.</p>
            <a href="/">돌아가기</a>
        """

# 로컬 테스트용 코드
if __name__ == '__main__':
    app.run(debug=True)