# Application-layer protection and HIL implementation

## 목적

V2X 응용은 영상과 안전메시지를 함께 전달합니다. 영상도 중요하지만 충돌 경고, 차량 상태와 같은 BSM/SDSM 안전메시지는 더 높은 우선순위와 복원 신뢰도가 필요합니다. 이 구현은 기존 영상 패킷 흐름을 유지하면서 안전메시지만 GF(256) 기반 Reed–Solomon 심볼로 분할·보호합니다.

송신기는 안전메시지를 `K`개의 원본 심볼로 나누고 환경에 따라 총 `N`개 심볼을 생성해 영상 패킷에 실어 보냅니다. 수신기는 임의의 `K`개 독립 심볼을 확보하면 가우스 소거 기반으로 메시지를 복원합니다. 연속 손실 구간에서는 심볼 간 간격을 두어 하나의 버스트가 모든 복구 기회를 제거하지 않도록 합니다.

## 구성

- `select_window.py`: GUI 진입점
- `sender_window.py`: 영상 송신과 56-byte 안전메시지 RS 인코딩
- `receiver_window.py`: 영상 수신, RS 디코딩 및 상태 표시
- `packet_header_struct.py`: TLVC/SSOV 패킷 구조
- `hil_sender_bsm.py`: 56-byte BSM HIL 송신기
- `hil_sender_sdsm.py`: 513-byte SDSM HIL 송신기
- `trace.bin`: 실도로 패킷 성공(1)/손실(0)을 packed-bit로 저장한 대표 구간
- `channel_metrics.csv`: 100-packet 윈도우 단위 PDR/최대 버스트
- `scenario_v2x_56.csv`: GUI 송신 시나리오
- `resource/`: GUI 지도·아이콘·상태 이미지

## 실행 환경

- Windows 권장 (`cv2.CAP_DSHOW`, `pygrabber` 사용)
- Python 3.9–3.11
- 송신/수신 장비와 통신 가능한 네트워크 인터페이스

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python select_window.py
```

HIL 송신기는 메시지 크기에 따라 다음과 같이 실행합니다.

```powershell
python hil_sender_bsm.py
python hil_sender_sdsm.py
```

지도·기상 기능을 사용할 때는 API 키를 소스에 넣지 말고 환경변수로 설정하십시오.

```powershell
$env:TMAP_API_KEY="your-key"
$env:WEATHER_API_SERVICE_KEY="your-key"
```

기본 대상 IP는 코드에 예시값으로 들어 있으며 UI에서 실제 장비 주소로 변경해야 합니다. 실험 실행 시 생성되는 로그는 공개 스냅샷에 포함하지 않습니다.

---

## English

### Purpose

The V2X application carries video and safety messages together. Although video is important, BSM/SDSM safety messages such as collision warnings and vehicle-state information require higher priority and stronger recovery reliability. This implementation preserves the existing video-packet flow while splitting and protecting only the safety messages as GF(256)-based Reed–Solomon symbols.

The sender divides a safety message into `K` source symbols, generates a total of `N` symbols according to the environment, and carries them in video packets. Once the receiver obtains any `K` independent symbols, it recovers the message through Gaussian elimination. During consecutive loss intervals, spacing the symbols prevents a single burst from eliminating every recovery opportunity.

### Contents

- `select_window.py`: GUI entry point
- `sender_window.py`: Video transmission and RS encoding of 56-byte safety messages
- `receiver_window.py`: Video reception, RS decoding, and status display
- `packet_header_struct.py`: TLVC/SSOV packet structures
- `hil_sender_bsm.py`: HIL sender for 56-byte BSMs
- `hil_sender_sdsm.py`: HIL sender for 513-byte SDSMs
- `trace.bin`: Representative road segment stored as packed packet-success (1) and packet-loss (0) bits
- `channel_metrics.csv`: PDR and maximum burst length for each 100-packet window
- `scenario_v2x_56.csv`: GUI transmission scenario
- `resource/`: GUI maps, icons, and status images

### Runtime Environment

- Windows recommended because the code uses `cv2.CAP_DSHOW` and `pygrabber`
- Python 3.9–3.11
- A network interface that can communicate with the transmitting or receiving equipment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python select_window.py
```

Run the HIL sender that corresponds to the message size:

```powershell
python hil_sender_bsm.py
python hil_sender_sdsm.py
```

For map and weather features, configure API keys through environment variables instead of placing credentials in the source code:

```powershell
$env:TMAP_API_KEY="your-key"
$env:WEATHER_API_SERVICE_KEY="your-key"
```

The source contains an example destination IP. Replace it through the UI with the address of the actual equipment. Runtime logs generated during experiments are not included in this public snapshot.
