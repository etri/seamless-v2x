import numpy as np
import pandas as pd
import glob

def create_preprocessed_files(file_pattern="ETRI_OBU_01(RX))*.csv",
                              bin_output="trace.bin",
                              metrics_output="channel_metrics.csv"):
    try:
        # 1. 원본 CSV 파일 검색 및 로드 (중간 파일 생성 생략)
        file_list = glob.glob(file_pattern)
        if not file_list:
            print(f"[System] '{file_pattern}' 패턴의 원본 파일을 찾을 수 없습니다.")
            return

        all_seq_numbers = []
        for file in file_list:
            df = pd.read_csv(file)
            if 'ulTimeStamp' in df.columns:
                seqs = df['ulTimeStamp'].dropna().astype(int)
                seqs = seqs[seqs > 0].values
                all_seq_numbers.extend(seqs)

        if not all_seq_numbers:
            print("[System] 유효한 패킷 시퀀스가 존재하지 않습니다.")
            return

        # 2. 1과 0으로 이루어진 배열(Trace) 직접 생성
        all_seq_numbers = np.unique(all_seq_numbers)
        all_seq_numbers.sort()
        max_seq = all_seq_numbers[-1]

        trace_array = np.zeros(max_seq, dtype=np.uint8)
        trace_array[all_seq_numbers - 1] = 1

        # 3. Binary 형태로 즉시 압축 저장 (.bin 생성)
        packed_trace = np.packbits(trace_array)
        with open(bin_output, 'wb') as f:
            f.write(packed_trace.tobytes())
        print(f"[Pre-process] {bin_output} 생성 완료 (용량: {len(packed_trace)} bytes, 원본 패킷 수: {len(trace_array)})")

        # 4. 100개 단위 윈도우별 순수 실측 지표 추출
        window_size = 100
        records = []

        for i in range(0, len(trace_array), window_size):
            window = trace_array[i : i + window_size]
            actual_size = len(window)
            pdr = np.sum(window) / actual_size

            is_zero = np.equal(window, 0)
            zero_lengths = np.diff(np.where(np.concatenate(([is_zero[0]], is_zero[:-1] != is_zero[1:], [True])))[0])[::2]
            max_burst = np.max(zero_lengths) if len(zero_lengths) > 0 else 0

            records.append([i // window_size, round(pdr, 4), max_burst])

        # 5. 순수 지표 CSV 저장 (channel_metrics.csv 생성)
        metrics_df = pd.DataFrame(records, columns=['Window_Idx', 'PDR', 'Max_Burst'])
        metrics_df.to_csv(metrics_output, index=False)
        print(f"[Pre-process] {metrics_output} 생성 완료 (총 {len(records)} 윈도우)")

    except Exception as e:
        print(f"[오류 발생] {e}")

if __name__ == "__main__":
    create_preprocessed_files()