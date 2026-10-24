import tempfile
import unittest
from pathlib import Path

from harness.document import load_document
from harness.family import classify
from harness.jd import parse_jd
from harness.rules_data import load_scoring
from harness.score import score_resume
from harness.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parent / "fixtures" / "workspace"  # 가상 인물의 작업 폴더

# family id → (이력서 헤드라인, 경력 문장, 스킬, 공고 제목, 공고 자격요건). 모두 가상 인물·회사다.
SAMPLES = {
    "backend_engineer": ("Backend Engineer", "Spring Boot 기반 주문 API 서버를 개발하고 Redis 캐시로 응답 시간을 120ms에서 40ms로 줄였다. MySQL 쿼리 최적화와 Kafka 메시지 큐 도입으로 대용량 트래픽을 처리했다.",
                         "Java, Kotlin, Spring, MySQL, Redis, Kafka, AWS", "백엔드 개발자", "Java 또는 Kotlin, Spring 서버 개발 경험\nMySQL 쿼리 최적화, REST API 설계"),
    "frontend_engineer": ("Frontend Engineer", "React와 TypeScript로 결제 화면을 개발하고 Lighthouse 점수를 62에서 91로 올렸다. Next.js SSR 도입으로 LCP를 단축했다.",
                          "React, Next.js, TypeScript, JavaScript, HTML, CSS", "프론트엔드 개발자", "React, TypeScript 실무 경험\n웹 성능 최적화 경험"),
    "mobile_engineer": ("iOS Developer", "Swift와 SwiftUI로 iOS 앱을 개발해 App Store에 출시하고 크래시 비율을 1.2%에서 0.3%로 낮췄다. TestFlight 배포와 앱 출시 프로세스를 운영했다.",
                        "iOS, Swift, SwiftUI, UIKit, Firebase, Flutter", "iOS 개발자", "Swift, UIKit/SwiftUI 앱 개발 경험\nApp Store 출시 경험"),
    "fullstack_engineer": ("Full-Stack Engineer", "Next.js 프런트엔드와 Node.js API를 함께 개발해 MVP를 6주 만에 출시했다. PostgreSQL 스키마부터 Docker 배포까지 End-to-End로 맡았다.",
                           "TypeScript, React, Node.js, PostgreSQL, Docker, AWS", "풀스택 개발자", "TypeScript, React, Node.js 경험\nAWS 배포 경험"),
    "devops_sre_engineer": ("DevOps Engineer", "Terraform으로 AWS 인프라를 코드화하고 GitHub Actions CI/CD 파이프라인을 구축해 배포 시간을 40분에서 8분으로 줄였다. Kubernetes 클러스터를 운영하며 Prometheus와 Grafana 모니터링, 장애 대응 온콜을 맡았다.",
                           "AWS, Kubernetes, Docker, Terraform, Prometheus, Grafana, Linux", "DevOps 엔지니어", "Kubernetes 운영 경험\nTerraform 등 IaC 경험, CI/CD 구축 경험"),
    "qa_engineer": ("QA Engineer", "테스트 케이스 400개를 설계하고 Cypress와 Selenium으로 회귀 테스트를 자동화해 릴리즈 검증 시간을 3일에서 4시간으로 줄였다. 결함 관리는 Jira로 운영했다.",
                    "QA, 테스트 케이스, Cypress, Selenium, Postman, Jira", "QA 엔지니어", "테스트 케이스 설계 경험\nCypress 등 테스트 자동화 경험"),
    "data_analyst": ("Data Analyst", "SQL로 코호트 분석과 퍼널 분석을 수행하고 Tableau 대시보드를 구축해 리텐션 지표 개선 의사결정을 도왔다. A/B 테스트 설계와 통계 분석으로 전환율을 14% 높였다.",
                     "SQL, Python, pandas, Tableau, GA4, Amplitude, 통계", "데이터 분석가", "SQL 능숙자\nA/B 테스트와 통계 분석 경험, Tableau 등 BI 도구 경험"),
    "data_engineer": ("Data Engineer", "Airflow로 ETL 데이터 파이프라인을 구축하고 BigQuery 데이터 웨어하우스 모델링을 맡아 일 처리량 2TB 배치를 안정화했다. Spark 분산 처리로 처리 시간을 70% 줄였다.",
                      "Python, SQL, Airflow, Spark, BigQuery, Kafka, dbt", "데이터 엔지니어", "Airflow 등 데이터 파이프라인 구축 경험\nSpark 대용량 데이터 처리 경험"),
    "ml_ai_engineer": ("Machine Learning Engineer", "PyTorch로 딥러닝 추천 모델을 학습해 오프라인 AUC를 0.71에서 0.78로 올리고 MLflow로 모델 서빙 파이프라인을 운영했다. RAG와 파인튜닝으로 LLM 검색 품질을 개선했다.",
                       "Python, PyTorch, scikit-learn, MLflow, RAG, 논문, 모델 평가", "ML 엔지니어", "PyTorch 딥러닝 모델 학습 경험\nMLOps, 모델 평가 경험"),
    "product_manager": ("Product Manager", "PRD와 로드맵을 작성하고 백로그 우선순위를 조정해 신규 구독 기능을 출시했다. OKR 기반으로 리텐션 지표를 개선하고 스프린트를 운영했다.",
                        "PRD, 로드맵, OKR, SQL, Jira, Figma", "Product Manager", "PRD 작성 경험\n로드맵 수립과 우선순위 결정 경험"),
    "service_planner": ("서비스 기획자", "신규 서비스 기획서와 화면 정의서, 스토리보드를 작성하고 요구사항 정의부터 개발팀과의 QA 일정 조율까지 맡아 앱 개편을 출시했다.",
                        "서비스 기획, 기획서, 화면 정의서, 스토리보드, Jira, Confluence", "서비스 기획자", "서비스 기획 경험\n화면 정의서와 요구사항 정의서 작성"),
    "biz_strategist": ("사업 기획자", "신사업 사업계획서를 작성하고 시장 조사와 재무 모델링으로 사업성 분석을 수행했다. 경영 보고용 전략 과제를 정리하고 BM 설계와 가격 정책 제안을 맡았다.",
                       "사업계획서, 시장 분석, 재무 모델링, BM 설계, Excel", "사업 기획", "사업계획 수립 경험\n시장 분석과 재무 모델링 능력"),
    "motion_designer": ("Motion Designer", "After Effects로 모션그래픽과 숏폼 광고 영상을 제작하고 Premiere Pro로 영상 편집을 맡아 월 20편을 제작했다. Cinema 4D 3D 렌더링과 Lottie 애니메이션도 담당했다.",
                        "After Effects, Premiere Pro, Cinema 4D, Lottie, 모션그래픽, 영상 편집", "모션 디자이너", "After Effects 모션그래픽 제작 경험\n영상 편집 경험"),
    "performance_marketer": ("퍼포먼스 마케터", "Meta Ads와 Google Ads, 네이버 검색광고 매체를 운영해 ROAS를 280%에서 410%로 올리고 CPA를 22% 낮췄다. AppsFlyer 어트리뷰션으로 소재 테스트 효율을 관리했다.",
                          "퍼포먼스 마케팅, Meta Ads, Google Ads, GA4, AppsFlyer, ROAS, CPA", "퍼포먼스 마케터", "광고 운영 경험, ROAS/CPA 관리\nGA4 활용 경험"),
    "content_brand_marketer": ("콘텐츠 마케터", "브랜드 캠페인을 기획하고 블로그와 뉴스레터, 인스타그램 SNS 콘텐츠를 운영해 구독자를 3배로 늘렸다. SEO 키워드 분석과 카피라이팅으로 유입을 높였다.",
                               "콘텐츠 마케팅, SNS 마케팅, 브랜드 마케팅, SEO, 카피라이팅", "콘텐츠 마케터", "콘텐츠 기획 경험\nSNS 채널 운영 경험"),
    "growth_marketer": ("Growth Marketer", "그로스 해킹 실험 30건을 설계하고 퍼널 최적화와 A/B 테스트로 가입 전환율을 18% 올렸다. Amplitude 코호트 분석으로 활성화와 리텐션 가설을 검증했다.",
                        "그로스 마케팅, A/B 테스트, 퍼널 분석, Amplitude, SQL, GA4", "그로스 마케터", "그로스 실험 설계 경험\n퍼널과 리텐션 분석 경험"),
    "crm_marketer": ("CRM 마케터", "Braze로 CRM 마케팅 자동화 시나리오를 설계해 휴면 고객 재구매율을 9% 높였다. 앱 푸시와 이메일 마케팅의 고객 세그먼트 타겟팅과 오픈율 A/B 테스트를 맡았다.",
                     "CRM 마케팅, Braze, 마케팅 자동화, 리텐션 마케팅, SQL", "CRM 마케터", "CRM 마케팅 경험\nBraze 같은 마케팅 자동화 툴 경험"),
    "sales_bd": ("B2B 영업 담당자", "기업 영업으로 신규 고객사 40곳을 개척하고 영업 파이프라인을 관리해 연간 매출 목표 대비 달성률 128%를 기록했다. Salesforce로 리드 관리와 제안서 작성, 계약 협상을 맡았다.",
                 "B2B 영업, 파이프라인 관리, Salesforce, 제안서 작성, 협상", "B2B 영업", "기업 영업 경험\n매출 목표 달성 이력, 제안 발표 경험"),
    "hr_recruiter": ("채용 담당자", "개발 직군 채용 프로세스를 운영하며 인재 소싱과 면접 진행, 서류 검토를 맡아 채용 리드타임을 45일에서 30일로 줄였다. 채용 브랜딩과 온보딩, 평가 제도 운영도 지원했다.",
                     "리크루팅, 인재 소싱, 채용 브랜딩, 인사 운영, 그리팅", "리크루터", "채용 경험\n인재 소싱과 면접 진행 경험"),
    "finance_accountant": ("회계 담당자", "월 결산과 재무제표 작성, 부가세 신고, 전표 처리를 맡고 더존 ERP로 정산 업무를 운영해 결산 마감을 5일에서 3일로 단축했다. K-IFRS 연결 결산과 내부 통제 점검을 지원했다.",
                           "회계, 결산, 재무제표, K-IFRS, 세무, 더존, Excel", "회계 담당자", "결산 및 재무제표 작성 경험\n세무 신고 경험, ERP 경험"),
    "operations_cs": ("CS 운영 매니저", "고객 상담 센터를 운영하며 Zendesk로 VOC 분석과 고객 불만 처리를 맡아 CSAT를 82에서 91로 올렸다. 응대 매뉴얼과 프로세스 개선으로 처리 시간을 25% 줄이고 SLA 관리를 맡았다.",
                       "CS 운영, 고객 응대, VOC 분석, Zendesk, 프로세스 개선, SLA 관리", "CS 운영 매니저", "고객 응대 경험\nVOC 분석과 프로세스 개선 경험"),
    "md_commerce": ("상품 MD", "카테고리 MD로 상품 기획과 소싱, 협력사 관리를 맡고 기획전과 프로모션으로 카테고리 매출을 30% 키웠다. 마진 관리와 재고 분석, 스마트스토어 입점 운영을 담당했다.",
                    "상품 기획, 소싱, 카테고리 관리, 프로모션 운영, 매출 분석, 스마트스토어", "상품 MD", "상품 기획 및 소싱 경험\n프로모션 운영과 마진 관리 경험"),
}


def write_resume(folder: Path, headline: str, body: str, skills: str) -> Path:
    path = folder / "resume.md"
    path.write_text(f"Sample Person\n{headline}\n\nSummary\n{headline} 경력 3년.\n\nExperience\n{headline}  예시회사  2022.01 - 2025.01\n- {body}\n\nSkills\n{skills}\n\nEducation\n예시대학교 졸업\n", encoding="utf-8")
    return path


def write_jd(folder: Path, title: str, requirements: str) -> Path:
    path = folder / "jd.md"
    path.write_text(f"---\ncompany: 예시회사\ntitle: {title}\n---\n\n## 주요 업무\n{title} 업무를 담당합니다.\n\n## 자격 요건\n경력 2년 이상\n{requirements}\n", encoding="utf-8")
    return path


class JobFamilyTests(unittest.TestCase):
    def setUp(self):
        self.taxonomy = load_taxonomy()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_each_sample_resume_and_jd_classify_into_its_family_and_score_runs(self):
        for family_id, (headline, body, skills, jd_title, requirements) in SAMPLES.items():
            with self.subTest(family=family_id):
                doc = load_document(ROOT, write_resume(self.folder, headline, body, skills))
                result = classify(doc, self.taxonomy)
                self.assertEqual(family_id, result["predicted"], result["ranking"][:3])
                self.assertEqual(family_id, result["headline_family"])
                jd = parse_jd(self.taxonomy, write_jd(self.folder, jd_title, requirements))
                self.assertEqual(family_id, jd["family"])
                score = score_resume(ROOT, jd, doc)
                self.assertTrue(0 <= score["total"] <= 100)
                self.assertEqual(family_id, score["family"]["id"])
                self.assertEqual(100, sum(score["family"]["weights"].values()))
                self.assertGreater(score["components"]["title"]["score"], 0)

    def test_every_family_group_has_scoring_weights_that_sum_to_one_hundred(self):
        scoring = load_scoring()
        for group, weights in scoring["family_weights"].items():
            self.assertEqual(100, sum({**scoring["weights"], **weights}.values()), group)
        groups = {f.get("group") for f in self.taxonomy.families} - {"design"}
        self.assertLessEqual(groups, set(scoring["family_weights"]))

    def test_every_family_core_skill_exists_in_the_skill_taxonomy(self):
        known = set(self.taxonomy.concept_by_id)
        for family in self.taxonomy.families:
            self.assertLessEqual(set(family.get("core_skills", [])), known, family["id"])

    def test_korean_and_english_skill_synonyms_match(self):
        from harness.taxonomy import Haystack
        for concept, text in (("react", "리액트로 개발"), ("sql", "SQL 쿼리"), ("ga4", "GA4 설정"), ("figma", "Figma 프로토타입")):
            self.assertIn(concept, self.taxonomy.concepts_in(Haystack(text)), concept)
        self.assertIn("python", self.taxonomy.concepts_in(Haystack("파이썬 개발")))
        self.assertIn("kubernetes", self.taxonomy.concepts_in(Haystack("쿠버네티스 운영")))

    def test_jd_with_unfamiliar_title_gets_family_from_its_body(self):
        path = self.folder / "jd.md"
        path.write_text("---\ncompany: 예시회사\ntitle: 그린필드 담당자\n---\n\n## 주요 업무\nKubernetes 클러스터 운영과 Terraform 인프라 자동화, CI/CD 파이프라인 구축, 모니터링과 장애 대응\n", encoding="utf-8")
        self.assertEqual("devops_sre_engineer", parse_jd(self.taxonomy, path)["family"])

    def test_portfolio_penalties_apply_only_to_families_that_expect_a_portfolio(self):
        failing = {"rules": [{"id": "R-TRUTH-01", "severity": "high", "status": "fail", "message": "이미지 쪽"}]}
        for family_id, expected in (("backend_engineer", False), ("product_designer", True)):
            with self.subTest(family=family_id):
                headline, body, skills, jd_title, requirements = SAMPLES.get(family_id, ("Product Designer", "Figma로 디자인 시스템을 만들어 전환율을 12% 높였다.", "Figma, 디자인 시스템", "Product Designer", "Figma 경험"))
                doc = load_document(ROOT, write_resume(self.folder, headline, body, skills))
                jd = parse_jd(self.taxonomy, write_jd(self.folder, jd_title, requirements))
                score = score_resume(ROOT, jd, doc, portfolio_audit=failing)
                applied = any(p["rule_id"].startswith("portfolio:") for p in score["penalties"])
                self.assertEqual(expected, applied)
                self.assertEqual(expected, score["family"]["portfolio_penalties_applied"])

    def test_resume_for_another_family_scores_lower_title_credit_than_a_match(self):
        headline, body, skills, _, _ = SAMPLES["backend_engineer"]
        doc = load_document(ROOT, write_resume(self.folder, headline, body, skills))
        match = score_resume(ROOT, parse_jd(self.taxonomy, write_jd(self.folder, "백엔드 개발자", "Spring")), doc)
        cross = score_resume(ROOT, parse_jd(self.taxonomy, write_jd(self.folder, "Product Designer", "Figma")), doc)
        self.assertGreater(match["components"]["title"]["score"], cross["components"]["title"]["score"])

    def test_family_evidence_reports_decisive_evidence_found_in_resume(self):
        headline, body, skills, jd_title, requirements = SAMPLES["sales_bd"]
        doc = load_document(ROOT, write_resume(self.folder, headline, body, skills))
        score = score_resume(ROOT, parse_jd(self.taxonomy, write_jd(self.folder, jd_title, requirements)), doc)
        by_label = {e["label"]: e["found"] for e in score["family_evidence"]}
        self.assertTrue(by_label["목표 대비 달성률"])


if __name__ == "__main__":
    unittest.main()
