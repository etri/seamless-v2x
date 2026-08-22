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

## 게시자

- 연구 재현용 공개 스냅샷 게시자: [강동원 (@kangdongwon02)](https://github.com/kangdongwon02) · [kamilar0725@snu.ac.kr](mailto:kamilar0725@snu.ac.kr)

---

# English

This repository was established with support from the project "Development of Autonomous Cooperative Driving Technology Based on Heterogeneous V2X Seamless Communications for Autonomous Driving," administered by the Ministry of Science and ICT of the Republic of Korea.

The 2026 ETRI public software deliverables are available in [`src_2026`](./src_2026):

- Application software that integrates and transmits video data and safety messages such as BSM and SDSM through V2X communication devices
- An algorithm designed to maintain reliable message reception as network performance varies from 100% to 40%

The [`V2I_실도로 로그`](./V2I_실도로%20로그) directory contains on-road data collected at the ETRI campus.

## Reproducible Research Snapshots

Core code and processed data covering the complete workflow—from the application-layer implementation to burst-loss protection and lightweight feedback prediction—are organized under [`research`](./research).

- [`research/jcci`](./research/jcci): Integrated video and high-priority safety-message transmission with HIL implementation
- [`research/vtc`](./research/vtc): Reed–Solomon design-space exploration, LUT generation, and measured-trace evaluation
- [`research/journal`](./research/journal): Adaptive protection using a lightweight causal predictor

## Publisher

- Research release publisher: [Dongwon Kang (@kangdongwon02)](https://github.com/kangdongwon02) · [kamilar0725@snu.ac.kr](mailto:kamilar0725@snu.ac.kr)
  
