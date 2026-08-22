# Lightweight feedback prediction and adaptive protection

## 목적

실제 운용에서는 큰 모델보다 빠르고 설명 가능한 예측기가 유리합니다. 이 단계는 직전 구간에서 피드백된 PDR, 최대 버스트 길이와 이동 속도를 사용해 다음 구간의 채널 상태를 인과적으로 추정합니다. EWMA 계열의 경량 추정값에 보수적 마진을 적용하고, 그 결과로 미리 계산된 Reed–Solomon LUT를 조회합니다.

예측이 빗나가더라도 버스트 손실에 필요한 여유를 확보하면서, 항상 큰 중복도를 쓰는 방식보다 전송량을 줄이는 것이 목표입니다. RAW/반복 전송, 단순 직전값 예측, 경량 예측기와 비인과적 oracle을 동일 트레이스에서 비교합니다.

## 파일과 실행 순서

1. `generate_predictions.py`
   - `channel_metrics_pred.csv`에서 마진별 인과 예측 CSV를 생성합니다.
2. `select_margin.py`
   - 예측 마진 후보의 신뢰도·비용 절충을 시각화합니다.
3. `evaluate_predictive_bsm.py`
   - 56-byte 안전메시지에서 제안 예측과 단순 1-lag 기준선을 비교합니다.
4. `evaluate_bsm_modes.py`, `evaluate_sdsm_modes.py`
   - 선택 마진에 따른 BSM/SDSM 전송 신뢰도와 평균 바이트를 평가합니다.
5. `compare_predictors.py`
   - 네 종류의 경량 예측 결과를 BSM/SDSM에서 통합 비교합니다.
6. `plot_predictions.py`, `plot_zoomed_prediction.py`
   - 예측 시계열과 확대 결과를 생성합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python generate_predictions.py
python evaluate_predictive_bsm.py
python compare_predictors.py
```

스크립트는 현재 디렉터리의 CSV/LUT/`trace.bin`을 읽으므로 먼저 이 디렉터리로 이동해 실행하십시오. `results/`에는 공개용 대표 PDF 결과만 포함합니다.
