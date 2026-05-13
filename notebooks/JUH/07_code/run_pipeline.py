import traceback

from pipeline.step2_collect_candidates import run as run_step2_collect
from pipeline.step2_prepare_candidates import run as run_step2_prepare
from pipeline.step2_refresh_candidates import run as run_step2_refresh
from pipeline.step2_append_refresh_video_master import run as run_step2_append_refresh_video_master
from pipeline.step2_build_growth_proxy_from_master import run as run_step2_build_growth_proxy_from_master
from pipeline.step2_merge_refresh_into_candidates import run as run_step2_merge_refresh
from pipeline.step3_build_candidate_features import run as run_step3_features
from pipeline.step4_score_candidates import run as run_step4_score
from pipeline.step6_export_dashboard import run as run_step6
from pipeline.step7_append_snapshots import run as run_step7_snapshot
from pipeline.step6_5_enrich_channel_thumbnails import run as run_step6_5_enrich_thumbnails
from pipeline.step5_build_shortlist_tracking import run as run_step5_tracking

def main():
    print("=" * 60)
    print("CME 후보 탐색 파이프라인 시작")
    print("=" * 60)

    steps = [
        ("STEP 1 - 일반 후보 Discovery 수집", run_step2_collect),
        ("STEP 2 - 후보 데이터 준비", run_step2_prepare),
        ("STEP 3 - 후보 채널 Refresh", run_step2_refresh),
        ("STEP 4 - Refresh video raw master 누적", run_step2_append_refresh_video_master),
        ("STEP 5 - master raw 기반 성장성 proxy 생성", run_step2_build_growth_proxy_from_master),
        ("STEP 6 - Refresh 결과 후보 테이블 반영", run_step2_merge_refresh),
        ("STEP 7 - candidate feature 생성", run_step3_features),
        ("STEP 8 - candidate scoring", run_step4_score),
        ("STEP 9 - shortlist 변화 추적 생성", run_step5_tracking),
        ("STEP 10 - 대시보드용 데이터 저장", run_step6),
        ("STEP 10.5 - 채널 프로필 이미지 URL 보강", run_step6_5_enrich_thumbnails),
        ("STEP 11 - snapshot append", run_step7_snapshot),
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