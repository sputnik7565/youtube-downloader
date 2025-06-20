# api/index.py
from flask import Flask, render_template, request, redirect
from pytubefix import YouTube
import urllib.parse

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
        
        # 비디오 스트림 (음성 포함, mp4)
        video_streams = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
        
        # 오디오 스트림 (m4a가 일반적)
        audio_streams = yt.streams.filter(only_audio=True).order_by('abr').desc()
        
        return render_template('result.html', 
                            video=yt, 
                            video_streams=video_streams, 
                            audio_streams=audio_streams,
                            original_url=urllib.parse.quote(url)) # URL을 안전하게 인코딩
    except Exception as e:
        return f"""
            <h1>오류가 발생했습니다: {e}</h1>
            <p>유효한 유튜브 URL인지, 또는 비공개 영상이 아닌지 확인해주세요.</p>
            <a href="/">돌아가기</a>
        """

@app.route('/download')
def download():
    # 인코딩된 URL을 다시 디코딩
    url = urllib.parse.unquote(request.args.get('url'))
    itag = request.args.get('itag')
    
    try:
        yt = YouTube(url, client='WEB')
        stream = yt.streams.get_by_itag(itag)
        
        # 실제 다운로드 URL로 사용자를 리디렉션
        return redirect(stream.url)
    except Exception as e:
        return f"""
            <h1>다운로드 중 오류가 발생했습니다: {e}</h1>
            <a href="/">돌아가기</a>
        """

# 로컬 테스트용 코드 (Vercel에서는 사용되지 않음)
if __name__ == '__main__':
    app.run(debug=True)