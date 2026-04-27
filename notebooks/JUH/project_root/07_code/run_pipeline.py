import traceback

from pipeline.step1_collect_reference import run as run_step1
from pipeline.step2_collect_candidates import run as run_step2_collect
from pipeline.step2_prepare_candidates import run as run_step2_prepare
from pipeline.step3_build_reference_profile import run as run_step3
from pipeline.step4_score_similarity import run as run_step4
from pipeline.step5_build_shortlist import run as run_step5
from pipeline.step6_export_dashboard import run as run_step6


def main():
    print("=" * 60)
    print("CME 후보 탐색 파이프라인 시작")
    print("=" * 60)

    steps = [
        ("STEP 1 - CME 레퍼런스 수집", run_step1),
        ("STEP 2 - 일반 후보 Discovery 수집", run_step2_collect),
        ("STEP 3 - 후보 데이터 준비", run_step2_prepare),
        ("STEP 4 - CME 레퍼런스 프로필 생성", run_step3),
        ("STEP 5 - CME 유사도 계산", run_step4),
        ("STEP 6 - shortlist 생성", run_step5),
        ("STEP 7 - 대시보드용 데이터 저장", run_step6),
    ]

    for step_name, step_func in steps:
        print(f"\n>>> {step_name} 시작")
        try:
            step_func()
            print(f"<<< {step_name} 완료")
        except Exception as e:
            print(f"!!! {step_name} 실패")
            print("에러:", e)
            traceback.print_exc()
            raise

    print("\n" + "=" * 60)
    print("파이프라인 전체 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()