# seamless-v2x
본 폴더는 과학기술정보통신부에서 주관하는 "자율주행을 위한 이기종 V2X Seamless 통신 기반 자율협력주행 기술개발"과제의 지원으로 구축되었습니다.
#
2026년 ETRI 공개산출물(SW)은 다음과 같습니다. 
(./src_2026)
- V2X 통신장치를 통한 영상 데이터 및 안전메시지(BSM, SDSM 등)를 통합하여 전송하는 응용 SW
- 네트워크 성능변화율(100%~40%)에도 안정적인 메시지 수신을 위한 알고리즘 적용
#
 ./V2I_실도로 로그
- ETRI 원내 실도로 수집 데이터 

## 연구 재현용 공개 스냅샷

응용계층 구현부터 버스트 손실 대응 정책, 경량 피드백 예측까지 이어지는 핵심 코드와 가공 데이터는 [`research`](./research)에 정리되어 있습니다.

- [`research/jcci`](./research/jcci): 영상과 고우선순위 안전메시지 통합 송수신 및 HIL 구현
- [`research/vtc`](./research/vtc): Reed–Solomon 정책 설계공간, LUT 생성과 실측 트레이스 평가
- [`research/journal`](./research/journal): 경량 인과 예측기를 이용한 적응형 보호 확장

## 코드 작성자

- `research/vtc` 및 `research/journal` 코드 작성: [강동원 (@kangdongwon02)](https://github.com/kangdongwon02)
- `research/jcci/hil_sender_bsm.py` 및 `research/jcci/hil_sender_sdsm.py` HIL 실험 코드 작성: [강동원 (@kangdongwon02)](https://github.com/kangdongwon02)

## Code Author

- Code in `research/vtc` and `research/journal` was written by [Dongwon Kang (@kangdongwon02)](https://github.com/kangdongwon02).
- The HIL experiment code in `research/jcci/hil_sender_bsm.py` and `research/jcci/hil_sender_sdsm.py` was written by [Dongwon Kang (@kangdongwon02)](https://github.com/kangdongwon02).
  
