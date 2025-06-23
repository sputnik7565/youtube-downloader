---

# YouTube Downloader Web App

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

간단한 웹 인터페이스를 통해 유튜브 비디오를 다운로드할 수 있는 웹 애플리케이션입니다. Docker를 사용하여 어떤 환경에서든 쉽게 서비스를 실행할 수 있도록 설계되었습니다.

<br>

## ✨ 스크린샷 (Screenshot)

![image](https://github.com/user-attachments/assets/1c78c4e9-b66e-4b28-9a06-0f98c53c8444)


<br>

## 🚀 주요 기능 (Features)

-   **URL 기반 다운로드**: 유튜브 영상 URL만으로 간편하게 다운로드할 수 있습니다.
-   **고화질 영상 지원**: `pytube`를 사용하여 가능한 최고 화질의 영상과 음원을 각각 다운로드합니다.
-   **자동 병합**: `FFmpeg`을 사용하여 다운로드된 영상과 음원을 자동으로 하나의 파일로 병합합니다.
-   **간편한 배포**: Docker와 Docker Compose를 통해 단 한 줄의 명령어로 서비스를 시작할 수 있습니다.
-   **파일 영속성**: 다운로드된 파일은 호스트 머신의 `downloads` 폴더에 저장되어 컨테이너가 종료되어도 유지됩니다.

<br>

## 🛠️ 기술 스택 (Tech Stack)

-   **Backend**: Python, Flask, Pytube
-   **WSGI Server**: Gunicorn
-   **Containerization**: Docker, Docker Compose
-   **Core Dependency**: FFmpeg (비디오/오디오 병합)
-   **Frontend**: HTML, CSS, JavaScript

<br>

## 📋 사전 요구 사항 (Prerequisites)

이 프로젝트를 로컬 환경에서 실행하기 위해 다음 프로그램들이 설치되어 있어야 합니다.

-   [Docker](https://www.docker.com/get-started)
-   [Docker Compose](https://docs.docker.com/compose/install/) (Docker Desktop에는 기본적으로 포함되어 있습니다.)

<br>

## ⚙️ 시작하기 (Getting Started)

프로젝트를 로컬 머신에서 실행하는 방법은 다음과 같습니다.

**1. 저장소 클론 (Clone the repository)**
```bash
git clone https://github.com/sputnik7565/youtube-downloader.git
cd youtube-downloader
```

**2. Docker 컨테이너 실행 (Run the Docker container)**
`docker-compose`를 사용하여 애플리케이션을 빌드하고 실행합니다.
```bash
docker-compose up --build
```
-   `--build` 옵션은 Docker 이미지를 새로 빌드할 때 사용합니다. 최초 실행 시 또는 코드 변경 시에 필요합니다.

**3. 애플리케이션 접속 (Access the application)**
웹 브라우저를 열고 다음 주소로 이동하세요.
[http://localhost:8080](http://localhost:8080)

**4. 다운로드 확인**
영상을 다운로드하면 프로젝트 루트 디렉터리에 자동으로 생성된 `downloads` 폴더 안에 파일이 저장됩니다. 이는 `docker-compose.yml`에 정의된 볼륨 마운트 설정 때문입니다.

<br>

## 💻 사용 방법 (Usage)

1.  웹 페이지의 입력창에 다운로드할 유튜브 영상의 URL을 붙여넣습니다.
2.  `Download` 버튼을 클릭합니다.
3.  다운로드가 시작되며, 완료되면 잠시 후 파일이 서버에 저장됩니다. (현재는 별도의 진행률 표시가 없습니다.)
4.  서버의 `downloads` 폴더에서 결과 파일을 확인할 수 있습니다.

<br>

## 📂 프로젝트 구조 (Project Structure)

```
.
├── app/                  # Flask 애플리케이션 소스 코드
│   ├── static/           # CSS, JS 등 정적 파일
│   ├── templates/        # HTML 템플릿 파일
│   └── main.py           # 메인 Flask 애플리케이션 로직
├── downloads/            # 다운로드된 영상이 저장되는 폴더 (볼륨 마운트)
├── .gitignore            # Git 추적 제외 목록
├── Dockerfile            # 애플리케이션 Docker 이미지 빌드를 위한 설정 파일
├── docker-compose.yml    # Docker 컨테이너 실행을 위한 설정 파일
├── LICENSE               # 프로젝트 라이선스 (MIT)
└── requirements.txt      # Python 패키지 의존성 목록
```

<br>

## 💡 향후 개선 과제 (Future Improvements)

이 프로젝트를 더 발전시키기 위한 아이디어들입니다. Pull Request는 언제나 환영합니다!

-   [ ] **다운로드 진행률 표시**: 사용자에게 실시간 다운로드 상태 및 진행률을 보여주는 기능 추가. (e.g., WebSocket, SSE)
-   [ ] **다양한 포맷/화질 선택**: 사용자가 원하는 영상 화질이나 포맷(mp3, mp4 등)을 선택할 수 있는 옵션 제공.
-   [ ] **비동기 처리**: 다운로드와 같은 장기 실행 작업을 백그라운드에서 처리하도록 개선. (e.g., Celery, Redis Queue)
-   [ ] **오류 처리 강화**: 유효하지 않은 URL 입력, 다운로드 실패 등 예외 상황에 대한 사용자 친화적인 피드백 제공.
-   [ ] **UI/UX 개선**: 더 세련되고 사용하기 편한 인터페이스로 개선.
-   [ ] **테스트 코드 작성**: 안정적인 서비스를 위한 단위 테스트 및 통합 테스트 추가.

<br>

## 🤝 기여하기 (Contributing)

이 프로젝트에 기여하고 싶으시다면, 다음 절차를 따라주세요.

1.  이 저장소를 **Fork** 하세요.
2.  새로운 기능이나 버그 수정을 위한 브랜치를 만드세요. (`git checkout -b feature/AmazingFeature`)
3.  코드를 수정하고 변경 사항을 **Commit** 하세요. (`git commit -m 'Add some AmazingFeature'`)
4.  만든 브랜치로 **Push** 하세요. (`git push origin feature/AmazingFeature`)
5.  **Pull Request**를 열어주세요.

<br>

## 📜 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE)에 따라 배포됩니다.

---
