# RS policy design and burst-error evaluation

## 목적

버스트 손실 환경에서도 고우선순위 안전메시지를 최대한 복원하기 위해 Reed–Solomon 총 심볼 수 `N`과 심볼 간 간격 `G`를 함께 선택합니다. 56-byte BSM은 7-byte 심볼 `K=8`, 513-byte SDSM은 19-byte 심볼 `K=27`로 모델링합니다.

설계공간 생성기는 Gilbert–Elliott 채널에서 환경 PDR과 평균 버스트 길이를 변화시키며 성공률, 지연과 전송량을 계산합니다. 30 kHz subcarrier spacing에 대응하는 0.5 ms 슬롯과 100 ms 안전메시지 기한을 사용합니다. LUT 생성기는 99% 신뢰도 하드 제약을 적용하고 오버헤드 중심, 지연 중심, 균형 모드의 정책을 만듭니다.

## 파일과 실행 순서

1. `generate_bsm_design_space.py`, `generate_sdsm_design_space.py`
   - 전체 설계공간을 생성해 `56데이터.csv`, `513데이터.csv`로 저장합니다.
   - 계산량과 메모리 사용량이 크므로 재생성이 필요할 때만 실행하십시오.
2. `build_bsm_lut.py`, `build_sdsm_lut.py`
   - 설계공간 CSV에서 세 종류의 LUT를 생성합니다.
3. `build_trace.py`
   - 저장소의 기존 원시 로그에서 `trace.bin`과 `channel_metrics.csv`를 생성합니다.
4. `analyze_bursts.py`
   - 100-packet 윈도우 통계와 LUT 셀 점유율을 계산합니다.
5. `evaluate_bsm.py`, `evaluate_sdsm.py`
   - 실측 트레이스에서 RAW, 반복 전송과 적응형 RS 정책을 비교합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python build_bsm_lut.py
python build_sdsm_lut.py
python analyze_bursts.py trace.bin trace_windows.csv
python evaluate_bsm.py
python evaluate_sdsm.py
```

Windows PowerShell에서는 가상환경 활성화 명령만 `.venv\Scripts\activate`로 바꾸면 됩니다. 제공된 `trace.bin`, 채널 지표, 설계공간 CSV와 LUT는 결과 재현을 위한 가공 산출물입니다.
