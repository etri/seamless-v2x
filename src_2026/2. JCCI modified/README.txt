JCCI용 코드입니다.
bin file에 실도로 패킷 도착 여부를 10으로 저장하였고
이를 활용해서 sender가 송신여부를 결정하여, 실도로를 HIL로 모사합니다.

전체 20분 가량 중
90초 가량의 좋은 데이터를 추출하여 사용했습니다.

---

English

This directory contains the HIL experiment code.
The binary file stores on-road packet arrivals as a sequence of ones and zeros.
The sender replays this sequence to decide whether each packet is transmitted, thereby reproducing the measured road channel in HIL.

A representative segment of approximately 90 seconds was selected from roughly 20 minutes of collected data.
