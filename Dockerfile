# 1. 기본 이미지 선택 (Python 3.11과 Debian(Bullseye) 운영체제 포함)
FROM python:3.11-bullseye

# 2. 시스템 패키지 업데이트 및 필요한 도구 설치
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 3. Node.js 설치 (필요한 경우)
RUN curl -sL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 4. 작업 디렉토리 설정
WORKDIR /app

# 5. 의존성 파일 복사 및 설치
# 먼저 requirements.txt만 복사하여 설치합니다.
# 이렇게 하면 나중에 코드만 변경되었을 때 이 단계의 캐시를 재사용하여 빌드 속도가 빨라집니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. 나머지 프로젝트 파일 전체 복사
COPY . .

# 7. 포트 노출 (선택사항)
EXPOSE 8000

# 8. 서버 실행
# Gunicorn이라는 WSGI 서버를 사용하여 Flask 앱을 실행합니다.
# Render는 PORT 환경 변수에 서비스할 포트 번호를 동적으로 할당해줍니다.
# 0.0.0.0은 모든 네트워크 인터페이스에서 요청을 받도록 설정하는 것입니다.
# api.index:app 은 api/index.py 파일 안에 있는 app 객체를 의미합니다.
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:8000", "--timeout", "300", "api.index:app"]