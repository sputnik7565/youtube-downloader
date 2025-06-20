# 1. 기본 이미지 선택 (Python 3.11과 Debian(Bullseye) 운영체제 포함)
FROM python:3.11-bullseye

# 2. Node.js 설치
# Debian 패키지 목록을 업데이트하고, Node.js 설치에 필요한 curl과 gnupg를 설치합니다.
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    # Node.js 18.x 버전을 사용하도록 저장소를 추가합니다.
    curl -sL https://deb.nodesource.com/setup_18.x | bash - && \
    # Node.js를 설치합니다.
    apt-get install -y nodejs && \
    # 불필요한 패키지 캐시를 정리하여 이미지 용량을 줄입니다.
    rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 의존성 파일 복사 및 설치
# 먼저 requirements.txt만 복사하여 설치합니다.
# 이렇게 하면 나중에 코드만 변경되었을 때 이 단계의 캐시를 재사용하여 빌드 속도가 빨라집니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 나머지 프로젝트 파일 전체 복사
COPY . .

# 6. 서버 실행
# Gunicorn이라는 WSGI 서버를 사용하여 Flask 앱을 실행합니다.
# Render는 PORT 환경 변수에 서비스할 포트 번호를 동적으로 할당해줍니다.
# 0.0.0.0은 모든 네트워크 인터페이스에서 요청을 받도록 설정하는 것입니다.
# api.index:app 은 api/index.py 파일 안에 있는 app 객체를 의미합니다.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "api.index:app"]