# Research release snapshots

이 디렉터리는 하나의 연구 흐름을 세 단계의 재현 가능한 공개 산출물로 정리합니다.

| 단계 | 디렉터리 | 핵심 내용 |
|---|---|---|
| 응용·HIL 구현 | [`jcci`](./jcci) | 영상 패킷과 함께 전달되는 고우선순위 안전메시지를 응용계층 Reed–Solomon 부호로 보호하고, 실도로 손실 트레이스로 HIL 검증 |
| 정책 설계·평가 | [`vtc`](./vtc) | Gilbert–Elliott 버스트 손실 환경에서 RS 중복도 `N`과 인터리빙 간격 `G`의 설계공간 생성, LUT 구성 및 평가 |
| 경량 예측 확장 | [`journal`](./journal) | 직전 채널 상태를 피드백받는 가벼운 인과 예측기와 보수적 마진을 이용한 적응 정책 평가 |

## 전체 흐름

1. 기존 영상 트래픽은 유지하되, 한층 더 중요한 BSM/SDSM 안전메시지를 별도로 식별합니다.
2. 안전메시지를 GF(256) 기반 Reed–Solomon 심볼로 나누어 응용계층에서 인코딩합니다.
3. 버스트 손실에 대비해 환경별 중복도 `N`과 전송 간격 `G`를 선택합니다.
4. 수신 측은 충분한 심볼을 받으면 원문을 복원합니다.
5. 실도로에서 관측한 패킷 성공/손실 열을 재생해 송수신기를 HIL로 검증합니다.
6. 실제 운용에서는 직전 관측값의 피드백으로 다음 구간을 가볍게 예측해 LUT를 선택합니다.

5G NR의 30 kHz subcarrier spacing은 0.5 ms 슬롯을 제공하므로, 짧아진 스케줄링 단위에서 중복 심볼을 시간축에 세밀하게 배치할 수 있습니다. 본 공개 코드의 설계공간 시뮬레이터는 이 0.5 ms 슬롯을 기반으로 전송 시간을 모델링합니다.

## 공개 범위

여기에는 실행에 필요한 핵심 소스, 가공된 패킷 트레이스, 채널 지표, LUT와 대표 결과만 포함합니다. 논문 원문, 발표자료, 개인 미디어, 행정 문서, 임시 파일과 중복 사본은 포함하지 않습니다. 원시 실도로 로그는 저장소의 기존 [`V2I_실도로 로그`](../V2I_실도로%20로그) 디렉터리를 사용하며 이곳에 복제하지 않습니다.

모든 경로는 각 하위 디렉터리를 현재 작업 디렉터리로 두고 실행하는 것을 기준으로 합니다. 전체 설계공간 생성은 CPU와 메모리를 많이 사용하므로 제공된 CSV/LUT로 평가 파이프라인을 먼저 확인하는 것을 권장합니다.

---

## English

This directory organizes the complete research workflow into three reproducible public snapshots.

| Stage | Directory | Scope |
|---|---|---|
| Application and HIL implementation | [`jcci`](./jcci) | Protect high-priority safety messages carried alongside video packets with application-layer Reed–Solomon coding, then validate the implementation in HIL using a measured road-loss trace |
| Policy design and evaluation | [`vtc`](./vtc) | Generate the design space for RS redundancy `N` and interleaving gap `G` under Gilbert–Elliott burst losses, construct LUTs, and evaluate the resulting policies |
| Lightweight prediction extension | [`journal`](./journal) | Evaluate adaptive policies driven by a lightweight causal predictor and conservative margins using feedback from the preceding channel state |

### End-to-End Workflow

1. Preserve the existing video traffic while separately identifying the higher-priority BSM/SDSM safety messages.
2. Encode each safety message at the application layer as GF(256)-based Reed–Solomon symbols.
3. Select the redundancy level `N` and transmission gap `G` for the current burst-loss environment.
4. Recover the original message once the receiver has collected enough symbols.
5. Validate the transmitter and receiver in HIL by replaying packet-success and packet-loss observations collected on the road.
6. During practical operation, use feedback from the preceding interval to predict the next interval with a lightweight estimator and select the corresponding LUT entry.

A 30 kHz subcarrier spacing in 5G NR provides a 0.5 ms slot. This shorter scheduling unit enables fine-grained placement of redundant symbols over time. The design-space simulators in this release model transmission timing using the 0.5 ms slot.

### Public Release Scope

This release contains only the core source code, processed packet traces, channel metrics, LUTs, and representative results required to run the workflow. Paper manuscripts, presentation slides, personal media, administrative documents, temporary files, and duplicate copies are excluded. The original road logs already available in [`V2I_실도로 로그`](../V2I_실도로%20로그) are not duplicated here.

Run each command with its corresponding subdirectory as the current working directory. Full design-space generation is CPU- and memory-intensive; first validate the evaluation pipeline with the provided CSV and LUT files.
