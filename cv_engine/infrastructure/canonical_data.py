from __future__ import annotations

from pathlib import Path

from ..domain.facts import render_fact_source
from ..domain.models import FactSource


def _fact(
    fact_id: str,
    meaning: str,
    en: str,
    *,
    he: str | None = None,
    tags: list[str],
    provenance: str,
    style: str = "bullet",
    dates: str | None = None,
    replaces: str | None = None,
    link_target: str | None = None,
) -> dict:
    renderings = {"en": en}
    if he:
        renderings["he"] = he
    return {
        "fact_id": fact_id,
        "meaning": meaning,
        "renderings": renderings,
        "tags": tags,
        "status": "canonical",
        "provenance": provenance,
        "confirmed_at": "2026-08-16" if provenance.startswith("v1 handoff") else None,
        "effective_dates": dates,
        "replaces": replaces,
        "resume_style": style,
        "link_target": link_target,
    }


HANDOFF = "v1 handoff Section 7; explicitly canonical"
LEGACY = "base/cv_base.md; migrated without strengthening"

# Post-v1 addition, deliberately outside the generated sources below. Those
# sources reproduce the v1 migrated state, whose per-file hashes are recorded in
# docs/v1-retrospective-migration-verification.json; adding a v2 fact to them
# would silently invalidate that evidence. This fact is created through the
# normal lifecycle instead, exactly as any later canonical fact would be.
V2_IDENTITY_FACT = {
    # New v2 facts take UUIDv4 technical identity; only migrated facts keep a
    # semantic ID, and there is no v1 identity fact to preserve.
    "fact_id": "0f3a6c4e-6b5f-4a2b-9c1d-7e8f5a0b2c31",
    "meaning": "The candidate's professional name is Matan Malka; the Hebrew rendering is מתן מלכה.",
    "renderings": {"en": "Matan Malka", "he": "מתן מלכה"},
    "tags": ["identity", "contact"],
    "provenance": (
        "base/cv_base.md and every rendered v1 CV; relocated into its canonical "
        "location for v2 without change"
    ),
    "confirmed_at": "2026-08-17",
    "effective_dates": None,
    "replaces": None,
    "resume_style": "heading",
}


COMMON_FACTS = [
    _fact("common.contact.location", "Professional location is Tel Aviv.", "Tel Aviv", he="תל אביב", tags=["contact"], provenance=LEGACY, style="contact"),
    _fact("common.contact.phone", "Professional phone is +972-50-668-8386.", "+972-50-668-8386", he="+972-50-668-8386", tags=["contact", "phone"], provenance=LEGACY, style="contact"),
    _fact("common.contact.email", "Professional email is matan1391@gmail.com.", "matan1391@gmail.com", he="matan1391@gmail.com", tags=["contact", "email"], provenance=LEGACY, style="contact"),
    # `link_target` restates, machine-readably, the address this fact's own
    # meaning already gives in prose. Nothing is added to the migrated fact.
    _fact("common.contact.linkedin", "Professional LinkedIn URL is https://www.linkedin.com/in/matanmalka1.", "linkedin.com/in/matanmalka1", he="linkedin.com/in/matanmalka1", tags=["contact", "linkedin"], provenance=LEGACY, style="contact", link_target="https://www.linkedin.com/in/matanmalka1"),
    _fact("common.contact.github", "Professional GitHub URL is https://github.com/matanmalka1.", "github.com/matanmalka1", he="github.com/matanmalka1", tags=["contact", "github", "development"], provenance=LEGACY, style="contact", link_target="https://github.com/matanmalka1"),
    _fact("common.language.hebrew", "Hebrew proficiency is Native.", "Hebrew: Native", he="עברית: שפת אם", tags=["language"], provenance=HANDOFF, style="item"),
    _fact("common.language.english", "English proficiency is Fluent.", "English: Fluent", he="אנגלית: שוטפת", tags=["language"], provenance=HANDOFF, style="item"),
    _fact("common.language.arabic", "Arabic proficiency is Conversational.", "Arabic: Conversational", he="ערבית: ברמת שיחה", tags=["language"], provenance=HANDOFF, style="item"),
    _fact("common.language.french", "French proficiency is Conversational.", "French: Conversational", he="צרפתית: ברמת שיחה", tags=["language"], provenance=HANDOFF, style="item"),
    _fact("common.logistics.driving_license", "Driving license: yes.", "Valid driving license", he="רישיון נהיגה בתוקף", tags=["logistics"], provenance=HANDOFF, style="item"),
    _fact("common.logistics.private_vehicle", "Private vehicle: yes.", "Private vehicle", he="רכב פרטי", tags=["logistics"], provenance=HANDOFF, style="item"),
    _fact("common.logistics.nationwide_travel", "Willing to travel nationwide: yes.", "Willing to travel nationwide", he="נכונות לנסיעות בכל הארץ", tags=["logistics", "field-sales"], provenance=HANDOFF, style="item"),
    _fact("common.logistics.nationwide_sales", "Verified nationwide field-Sales experience: yes.", "Nationwide field sales experience", he="ניסיון במכירות שטח בפריסה ארצית", tags=["logistics", "field-sales", "sales"], provenance=HANDOFF, style="item"),
    _fact("common.education.fullstack", "Completed a 990-hour Full-Stack Development professional program at John Bryce in Tel Aviv during 2024-2025.", "Full-Stack Development, John Bryce, Tel Aviv | 990-hour professional program, 2024-2025", he="לימודי Full-Stack Development, ג'ון ברייס, תל אביב | תוכנית מקצועית בת 990 שעות, 2024-2025", tags=["education", "development"], provenance=LEGACY, style="item", dates="2024-2025"),
]


SALES_FACTS = [
    _fact("sales.company.activity", "Pcom Solutions was an import/export and wholesale company primarily supplying and selling mobile devices to businesses in Israel.", "Pcom Solutions was an import/export and wholesale company supplying mobile devices to businesses across Israel.", he="Pcom Solutions הייתה חברת יבוא, יצוא וסיטונאות שסיפקה ומכרה מכשירים סלולריים לעסקים ברחבי ישראל.", tags=["sales", "b2b", "company"], provenance=HANDOFF),
    _fact("sales.company.customers", "B2B customers included business owners, procurement managers, stores, chains, companies, and institutions across industries.", "Served business owners, procurement managers, stores, chains, companies, and institutions across industries.", he="עבודה מול בעלי עסקים, מנהלי רכש, חנויות, רשתות, חברות ומוסדות במגוון ענפים.", tags=["sales", "b2b", "customers"], provenance=HANDOFF),
    _fact("sales.role.field.title", "Historical title: Field Sales Representative (B2B) at Pcom Solutions.", "Field Sales Representative (B2B) | Pcom Solutions", he="Field Sales Representative (B2B) | Pcom Solutions", tags=["sales", "historical-title", "field-sales"], provenance=HANDOFF, style="heading", dates="2019-03/2020-08"),
    _fact("sales.role.field.dates", "Field Sales Representative dates are March 2019 to August 2020, approximately 1.5 years.", "March 2019 - August 2020", he="מרץ 2019 - אוגוסט 2020", tags=["sales", "date"], provenance=HANDOFF, style="date", dates="2019-03/2020-08"),
    _fact("sales.role.leader.title", "Historical title: Team Leader / Sales Supervisor (B2B) at Pcom Solutions.", "Team Leader / Sales Supervisor (B2B) | Pcom Solutions", he="Team Leader / Sales Supervisor (B2B) | Pcom Solutions", tags=["sales", "historical-title", "leadership"], provenance=HANDOFF, style="heading", dates="2020-08/2025-01"),
    _fact("sales.role.leader.dates", "Team Leader / Sales Supervisor dates are August 2020 to January 2025, approximately 4 years and 6 months.", "August 2020 - January 2025", he="אוגוסט 2020 - ינואר 2025", tags=["sales", "date", "leadership"], provenance=HANDOFF, style="date", dates="2020-08/2025-01"),
    _fact("sales.summary.field", "Verified nationwide B2B field-Sales experience includes new-customer acquisition, account management, quotations, tenders, negotiation, and closing.", "Nationwide B2B field sales professional experienced in new-customer acquisition, account management, quotations, tenders, negotiation, and closing.", he="איש מכירות שטח B2B בפריסה ארצית, בעל ניסיון בגיוס לקוחות, ניהול תיקי לקוחות, הצעות מחיר, מכרזים, משא ומתן וסגירת עסקאות.", tags=["sales", "field-sales", "summary"], provenance=HANDOFF, style="paragraph"),
    _fact("sales.summary.account", "Verified Sales background combines a recurring account portfolio, retention, upsell, cross-sell, and new-customer acquisition.", "B2B Account Manager with experience managing recurring customers, growing existing accounts, retaining business, and acquiring new customers.", he="מנהל תיקי לקוחות B2B בעל ניסיון בניהול לקוחות חוזרים, הרחבת פעילות, שימור לקוחות וגיוס לקוחות חדשים.", tags=["sales", "account-management", "summary"], provenance=HANDOFF, style="paragraph"),
    _fact("sales.summary.new_business", "Verified full-cycle B2B Sales includes prospecting, discovery, quotations, negotiation, closing, and post-Sales follow-through.", "Full-cycle B2B sales professional covering prospecting, discovery, quotations, negotiation, closing, and post-sale follow-through.", he="איש מכירות B2B במחזור מכירה מלא, משלב איתור לקוחות, אפיון צרכים, הצעות מחיר, משא ומתן, סגירה וליווי לאחר המכירה.", tags=["sales", "new-business", "full-sales-cycle", "summary"], provenance=HANDOFF, style="paragraph"),
    _fact("sales.summary.leadership", "Verified player-coach Sales leadership combines team management and active direct Sales in an approximately 50/50 mix.", "Player-coach B2B sales leader combining team leadership, coaching, pipeline management, and active account ownership in an approximately 50/50 management and direct-sales role.", he="מנהל מכירות B2B במודל player-coach, המשלב ניהול צוות, אימון, ניהול pipeline ואחריות ישירה על לקוחות בחלוקה משוערת של 50/50 בין ניהול למכירות.", tags=["sales", "leadership", "summary"], provenance=HANDOFF, style="paragraph"),
    _fact("sales.summary.tech", "Verified Tech Sales positioning combines B2B mobile-device Sales experience with separate hands-on professional software-development experience, without claiming prior SaaS Sales.", "Commercial and technical professional combining full-cycle B2B sales and account leadership with hands-on professional Full-Stack development experience.", he="איש מקצוע מסחרי וטכנולוגי המשלב מכירות B2B וניהול לקוחות לאורך מחזור המכירה המלא עם ניסיון מקצועי מעשי ב-Full-Stack Development.", tags=["sales", "development", "tech-sales", "summary"], provenance=HANDOFF, style="paragraph"),
    _fact("sales.summary.tenure", "Total B2B Sales experience runs from March 2019 to January 2025 - nearly six years across field Sales and Sales leadership; the span follows from the canonical role dates.", "Nearly 6 years of B2B sales experience across full-cycle sales and team leadership.", he="כמעט 6 שנות ניסיון במכירות B2B, לאורך מחזור מכירה מלא וניהול צוות.", tags=["sales", "summary", "tenure", "verified-quantitative"], provenance="User confirmation 2026-08-17; span follows from canonical role dates 2019-03/2025-01", style="paragraph", dates="2019-03/2025-01"),
    _fact("sales.cycle.prospecting", "Prospecting used cold leads, proactive calls, field activity, referrals, customer databases, business relationships, and tenders.", "Prospected through proactive calls, field activity, referrals, customer databases, business relationships, and tenders.", he="איתור לקוחות באמצעות שיחות יזומות, פעילות שטח, הפניות, מאגרי לקוחות, קשרים עסקיים ומכרזים.", tags=["sales", "prospecting", "new-business"], provenance=HANDOFF),
    _fact("sales.cycle.outreach", "Initial outreach used phone, email, WhatsApp, physical meetings, and business visits.", "Engaged prospects by phone, email, WhatsApp, physical meetings, and business visits.", he='יצירת קשר עם לקוחות בטלפון, בדוא"ל, ב-WhatsApp, בפגישות ובביקורים עסקיים.', tags=["sales", "prospecting", "communication"], provenance=HANDOFF),
    _fact("sales.cycle.discovery", "Needs discovery covered quantities, budget, device types, delivery timing, and payment terms.", "Led needs discovery across quantities, budgets, device types, delivery timing, and payment terms.", he="אפיון צרכים הכולל כמויות, תקציב, סוגי מכשירים, מועדי אספקה ותנאי תשלום.", tags=["sales", "discovery", "consultative"], provenance=HANDOFF),
    _fact("sales.cycle.quotations", "Independently prepared quotations, matched price and quantity, checked inventory, and reviewed commercial terms.", "Prepared quotations independently, aligned price and quantity, checked inventory, and reviewed commercial terms.", he="הכנת הצעות מחיר באופן עצמאי, התאמת מחיר וכמות, בדיקת מלאי ובחינת תנאים מסחריים.", tags=["sales", "quotations", "commercial"], provenance=HANDOFF),
    _fact("sales.cycle.negotiation", "Negotiated price, credit, payment terms, quantity, delivery, and discounts.", "Negotiated pricing, credit, payment terms, quantities, delivery, and discounts.", he="ניהול משא ומתן על מחיר, אשראי, תנאי תשלום, כמויות, אספקה והנחות.", tags=["sales", "negotiation", "closing"], provenance=HANDOFF),
    _fact("sales.cycle.closing", "Closed deals and handed orders into execution, then followed inventory, delivery, billing, collection, and order issues.", "Closed deals and coordinated execution across inventory, delivery, billing, collection, and order issues.", he="סגירת עסקאות ותיאום הביצוע מול מלאי, אספקה, חיוב, גבייה וטיפול בתקלות הזמנה.", tags=["sales", "closing", "post-sales"], provenance=HANDOFF),
    _fact("sales.cycle.account_management", "Managed repeat orders, retention, upsell, and cross-sell across an existing account portfolio.", "Managed ongoing accounts through repeat orders, retention, upsell, and cross-sell.", he="ניהול שוטף של תיק לקוחות באמצעות הזמנות חוזרות, שימור, upsell ו-cross-sell.", tags=["sales", "account-management", "account-growth"], provenance=HANDOFF),
    _fact("sales.metric.recurring_customers", "Managed approximately 40-50 recurring customers, plus occasional deals.", "Managed approximately 40-50 recurring customers in addition to occasional deals.", he="ניהול של כ-40-50 לקוחות חוזרים, נוסף על עסקאות מזדמנות.", tags=["sales", "account-management", "verified-quantitative"], provenance=HANDOFF),
    _fact("sales.metric.new_customers", "Acquired approximately 4-8 new customers per quarter on average.", "Acquired approximately 4-8 new customers per quarter on average.", he="גיוס ממוצע של כ-4-8 לקוחות חדשים ברבעון.", tags=["sales", "new-business", "verified-quantitative"], provenance=HANDOFF),
    _fact("sales.metric.team_size", "Managed a team of approximately 2-3 Sales representatives.", "Managed a team of 2-3 sales representatives.", he="ניהול צוות של כ-2-3 נציגי מכירות.", tags=["sales", "leadership", "verified-quantitative"], provenance=HANDOFF, replaces="legacy.team_size.3-4"),
    _fact("sales.metric.performance", "Delivered approximately 30% improvement in team performance and Sales revenue over the full management period, not annually.", "Delivered approximately 30% improvement in team performance and sales revenue over the management period.", he="שיפור של כ-30% בביצועי הצוות ובהכנסות ממכירות לאורך תקופת הניהול.", tags=["sales", "leadership", "verified-quantitative"], provenance=HANDOFF, replaces="legacy.revenue.30-yoy"),
    _fact("sales.metric.portfolio_growth", "Expanded the customer portfolio by approximately 30% over the management period.", "Expanded the customer portfolio by approximately 30% over the management period.", he="הרחבת תיק הלקוחות בכ-30% לאורך תקופת הניהול.", tags=["sales", "account-growth", "verified-quantitative"], provenance=HANDOFF),
    _fact("sales.leadership.player_coach", "The Team Leader role was approximately 50% team management and 50% direct Sales/account management.", "Operated as a player-coach, splitting the role approximately 50% team management and 50% direct sales and account management.", he="עבודה במודל player-coach בחלוקה משוערת של 50% ניהול צוות ו-50% מכירות ישירות וניהול לקוחות.", tags=["sales", "leadership", "player-coach"], provenance=HANDOFF),
    _fact("sales.leadership.pipeline", "Leadership scope included goals, lead/account/territory allocation, team meetings, KPI monitoring, pipeline management, forecasting, and management reporting.", "Set goals, allocated leads and accounts, monitored KPIs, and managed pipeline, forecasts, and recurring team reviews.", he="קביעת יעדים, חלוקת לידים ולקוחות, מעקב KPIs וניהול pipeline, תחזיות וישיבות צוות שוטפות.", tags=["sales", "leadership", "pipeline", "forecasting"], provenance=HANDOFF),
    _fact("sales.leadership.coaching", "Leadership scope included onboarding, training, call/meeting accompaniment, performance reviews, and feedback.", "Onboarded and trained representatives, coached calls and meetings, and delivered performance reviews and feedback.", he="קליטה והכשרת נציגים, ליווי בשיחות ובפגישות ומתן משוב והערכות ביצועים.", tags=["sales", "leadership", "coaching"], provenance=HANDOFF),
    _fact("sales.leadership.commercial_approval", "Approved discounts, pricing, credit, and commercial terms and supported exceptional deals and strategic customers.", "Approved discounts, pricing, credit, and commercial terms while supporting exceptional deals and strategic customers.", he="אישור הנחות, תמחור, אשראי ותנאים מסחריים וליווי עסקאות חריגות ולקוחות אסטרטגיים.", tags=["sales", "leadership", "commercial"], provenance=HANDOFF),
    _fact("sales.leadership.strategic_customers", "Handled exceptional deals and strategic customers and assisted negotiation and closing.", "Supported negotiations and closing for exceptional deals and strategic customers.", he="ליווי משא ומתן וסגירה בעסקאות חריגות ועם לקוחות אסטרטגיים.", tags=["sales", "leadership", "strategic-accounts"], provenance=HANDOFF),
    _fact("sales.tool.priority", "Used Priority ERP for orders, inventory checks, invoices, collection, and delivery-status tracking.", "Priority ERP: orders, inventory, invoices, collection, and delivery-status tracking.", he="Priority ERP: הזמנות, מלאי, חשבוניות, גבייה ומעקב אספקות.", tags=["sales", "tool", "erp"], provenance=HANDOFF, style="item"),
    _fact("sales.tool.excel", "Used Excel for Sales reports, KPI tracking, forecasts, performance tracking, and data analysis.", "Excel: sales reporting, KPI tracking, forecasts, performance monitoring, and data analysis.", he="Excel: דוחות מכירה, מעקב KPIs, תחזיות, ביצועים וניתוח נתונים.", tags=["sales", "tool", "analytics"], provenance=HANDOFF, style="item"),
    _fact("sales.tool.communication", "Used Outlook, Gmail, WhatsApp, and Teams for customer and internal communication and deal follow-through.", "Outlook, Gmail, WhatsApp, and Teams: customer communication, internal collaboration, and deal follow-through.", he="Outlook, Gmail, WhatsApp ו-Teams: תקשורת עם לקוחות, שיתוף פעולה פנימי וקידום עסקאות.", tags=["sales", "tool", "communication"], provenance=HANDOFF, style="item"),
    _fact("sales.activity.lead_mix", "Approximate lead-source mix: proactive outbound 25%, inbound 20%, referrals/business relationships 50%, tenders 5%.", "Lead sources were approximately 25% outbound, 20% inbound, 50% referrals and business relationships, and 5% tenders, reflecting a broad relationship-led role.", he="מקורות הלידים היו בקירוב 25% outbound, 20% inbound, 50% הפניות וקשרים עסקיים ו-5% מכרזים, כחלק מתפקיד רחב ומבוסס מערכות יחסים.", tags=["sales", "prospecting", "verified-quantitative"], provenance=HANDOFF),
    _fact("sales.activity.work_mode", "Approximate work-mode mix: 60% phone/email/WhatsApp/digital and 40% meetings/field Sales.", "Worked approximately 60% through phone, email, WhatsApp, and digital channels and 40% through meetings and field sales.", he='עבודה של כ-60% בטלפון, בדוא"ל, ב-WhatsApp ובערוצים דיגיטליים וכ-40% בפגישות ובמכירות שטח.', tags=["sales", "field-sales", "verified-quantitative"], provenance=HANDOFF, style="item"),
    _fact("sales.cycle.velocity", "New deals often closed the same day or within days; larger deals, chains, and tenders ranged from one day to about one month.", "Closed typical new deals the same day or within several days, while larger deals, chains, and tenders ranged from one day to approximately one month.", he="עסקאות חדשות טיפוסיות נסגרו באותו יום או בתוך מספר ימים, בעוד עסקאות גדולות, רשתות ומכרזים נמשכו מיום ועד כחודש.", tags=["sales", "sales-cycle", "velocity"], provenance=HANDOFF),
    _fact("sales.achievement.account_expansion", "Expanded activity within existing accounts and increased Pcom Solutions' share of customer purchasing without an unverified amount.", "Expanded activity within existing accounts and increased share of customer purchasing.", he="הרחבת פעילות בתוך לקוחות קיימים והגדלת חלק החברה בהיקף הרכש שלהם.", tags=["sales", "account-growth", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.reactivation", "Reactivated inactive customers.", "Reactivated inactive customers and restored repeat business.", he="החזרת לקוחות לא פעילים לפעילות עסקית חוזרת.", tags=["sales", "account-growth", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.retention", "Resolved commercial and operational crises that retained customers.", "Resolved commercial and operational crises to retain customers.", he="פתרון משברים מסחריים ותפעוליים לצורך שימור לקוחות.", tags=["sales", "retention", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.complex_deals", "Won complex deals and tenders without a verified amount or ranking.", "Won complex deals and tenders.", he="זכייה בעסקאות מורכבות ובמכרזים.", tags=["sales", "closing", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.difficult_market", "Closed business in difficult market conditions without an unverified amount.", "Closed business in difficult market conditions.", he="סגירת עסקאות בתנאי שוק מאתגרים.", tags=["sales", "closing", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.process", "Improved pipeline management and follow-up processes.", "Improved pipeline management and follow-up processes.", he="שיפור תהליכי ניהול pipeline ומעקב.", tags=["sales", "leadership", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.achievement.performance", "Coached Sales representatives and improved their performance without an additional unverified metric.", "Coached sales representatives and improved their performance.", he="אימון נציגי מכירות ושיפור ביצועיהם.", tags=["sales", "leadership", "coaching", "verified-qualitative"], provenance=HANDOFF),
    _fact("sales.tech_sales.boundary", "Verified combination is mobile-device B2B Sales plus separate professional software Development; direct SaaS/software Sales is not verified.", "B2B mobile-device sales and separate professional software-development experience; no claim of prior direct SaaS sales.", he="מכירות B2B של מכשירים סלולריים לצד ניסיון מקצועי נפרד בפיתוח תוכנה, ללא טענה לניסיון ישיר קודם במכירות SaaS.", tags=["sales", "development", "tech-sales", "boundary"], provenance=HANDOFF, style="item"),
    _fact("sales.career_narrative", "Career narrative is expansion: substantial B2B Sales career followed by technical depth at PH.Digital, then a deliberate return to Sales strengths.", "Built a substantial B2B sales career and later added hands-on technical depth at PH.Digital, strengthening the ability to understand products, systems, and technology customers.", he="בניית קריירת מכירות B2B משמעותית ולאחריה העמקה טכנולוגית מעשית ב-PH.Digital, שחיזקה את היכולת להבין מוצרים, מערכות ולקוחות טכנולוגיים.", tags=["sales", "development", "career-narrative"], provenance="v1 handoff Section 8; binding narrative", style="paragraph"),
]


DEVELOPMENT_FACTS = [
    _fact("development.summary", "Full-Stack Developer specializing in Python/FastAPI and React with production CRM and workflow experience and business-process understanding.", "Full-Stack Developer specializing in Python/FastAPI and React, with production experience building CRM and workflow systems end to end and a strong understanding of business processes.", he="מפתח Full-Stack המתמחה ב-Python/FastAPI וב-React, עם ניסיון מקצועי בבניית מערכות CRM ותהליכי עבודה מקצה לקצה והבנה חזקה של תהליכים עסקיים.", tags=["development", "summary"], provenance=LEGACY, style="paragraph"),
    _fact("development.phdigital.role", "Historical title: Full-Stack Developer at PH.Digital, Herzliya.", "Full-Stack Developer | PH.Digital, Herzliya", he="Full-Stack Developer | PH.Digital, הרצליה", tags=["development", "historical-title"], provenance=LEGACY, style="heading", dates="2025/2026"),
    _fact("development.phdigital.dates", "PH.Digital role dates are 2025-2026.", "2025 - 2026", he="2025 - 2026", tags=["development", "date"], provenance=LEGACY, style="date", dates="2025/2026"),
    _fact("development.phdigital.fullstack", "Built and maintained production applications with React and Python/FastAPI from PostgreSQL data models and APIs through frontend implementation.", "Built and maintained production applications with React and Python/FastAPI, owning features from PostgreSQL data modeling and APIs through frontend implementation.", he="פיתוח ותחזוקה של מערכות production ב-React וב-Python/FastAPI, כולל אחריות על פיצ'רים ממודלי נתונים ב-PostgreSQL ו-APIs ועד המימוש בצד הלקוח.", tags=["development", "technical", "full-stack"], provenance=LEGACY),
    _fact("development.phdigital.crm", "Architected a production CRM on PostgreSQL with workflow automation, role-based authentication, scheduled jobs, and state-driven processes.", "Architected a production CRM on PostgreSQL with workflow automation, role-based authentication, scheduled jobs, and state-driven business processes.", he="תכנון מערכת CRM ב-production על PostgreSQL עם אוטומציית תהליכים, הרשאות מבוססות תפקיד, משימות מתוזמנות ותהליכים עסקיים מבוססי state.", tags=["development", "backend", "databases"], provenance=LEGACY),
    _fact("development.phdigital.cicd", "Set up GitHub Actions CI/CD for linting, tests, migration checks, and OpenAPI contract sync.", "Set up GitHub Actions CI/CD covering linting, automated tests, database migration checks, and OpenAPI contract sync.", he="הקמת CI/CD ב-GitHub Actions עבור linting, בדיקות אוטומטיות, בדיקות migrations וסנכרון חוזי OpenAPI.", tags=["development", "devops", "testing"], provenance=LEGACY),
    _fact("development.phdigital.nextjs", "Built a customer marketing site with Next.js App Router, React Server Components, TypeScript, Tailwind CSS, RTL Hebrew, Sentry, and Vitest.", "Built a customer-facing site with Next.js App Router, React Server Components, TypeScript, Tailwind CSS, RTL Hebrew, Sentry, and Vitest.", tags=["development", "frontend", "nextjs"], provenance=LEGACY),
    _fact("development.phdigital.integrations", "Built WhatsApp/email integrations and asynchronous PDF/Excel generation with services, jobs, retries, scheduling, and status tracking.", "Built WhatsApp and email integrations plus asynchronous PDF/Excel generation using reusable services, background jobs, retries, scheduling, and status tracking.", he='פיתוח אינטגרציות WhatsApp ודוא"ל ותהליכי יצירת PDF/Excel אסינכרוניים באמצעות שירותים חוזרים, background jobs, retries, תזמון ומעקב סטטוס.', tags=["development", "integrations", "backend"], provenance=LEGACY),
    _fact("development.phdigital.agile", "Delivered features in Agile sprints with frontend and product teams.", "Delivered features in Agile sprints, collaborating with frontend and product teams.", tags=["development", "collaboration", "agile"], provenance=LEGACY),
    _fact("development.skills.backend", "Backend skills: Python, FastAPI, Flask, Node.js, Express, REST APIs.", "Backend: Python, FastAPI, Flask, Node.js, Express, REST APIs", he="Backend: Python, FastAPI, Flask, Node.js, Express, REST APIs", tags=["development", "skill", "backend"], provenance=LEGACY, style="item"),
    _fact("development.skills.frontend", "Frontend skills: React, Next.js, TypeScript, JavaScript.", "Frontend: React, Next.js, TypeScript, JavaScript", he="Frontend: React, Next.js, TypeScript, JavaScript", tags=["development", "skill", "frontend"], provenance=LEGACY, style="item"),
    _fact("development.skills.ai", "AI integration skills: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering.", "AI and LLM Integrations: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering", he="AI ו-LLM Integrations: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering", tags=["development", "skill", "ai"], provenance=LEGACY, style="item"),
    _fact("development.skills.databases", "Database skills: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL.", "Databases: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL", he="Databases: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL", tags=["development", "skill", "databases"], provenance=LEGACY, style="item"),
    _fact("development.skills.devops", "DevOps/tool skills: Docker, GitHub Actions, Git, GitHub, Postman, AWS EC2.", "DevOps and Tools: Docker, GitHub Actions, Git, GitHub, Postman, AWS EC2", he="DevOps וכלים: Docker, GitHub Actions, Git, GitHub, Postman, AWS EC2", tags=["development", "skill", "devops"], provenance=LEGACY, style="item"),
    _fact("development.project.mami", "Personal Mami Supermarket project is a full-stack grocery platform using Flask, PostgreSQL, SQLAlchemy, React, TypeScript, Vite, Tailwind, JWT, Alembic, and Pydantic.", "Mami Supermarket: full-stack grocery delivery and operations platform built with Flask, PostgreSQL, SQLAlchemy, React, TypeScript, Vite, Tailwind CSS, JWT, Alembic, and Pydantic.", tags=["development", "project", "full-stack"], provenance=LEGACY),
    _fact("development.project.bar_exam", "Personal Bar Exam Practice App uses FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic, JWT, slowapi, Sentry, PDF parsing, React, TypeScript, React Query, Zod, Tailwind, and pytest.", "Bar Exam Practice App: FastAPI/PostgreSQL backend and React/TypeScript frontend with authentication, migrations, rate limiting, monitoring, PDF ingestion, and pytest coverage.", tags=["development", "project", "backend"], provenance=LEGACY),
    _fact("development.project.gd", "Freelance G.D Financial Services responsive marketing site used React, Vite, Tailwind CSS, Radix UI, React Hook Form, and Zod.", "G.D Financial Services: responsive freelance marketing site built with React, Vite, Tailwind CSS, Radix UI, React Hook Form, and Zod.", tags=["development", "project", "frontend", "freelance"], provenance=LEGACY),
]


SITUATIONAL_FACTS = [
    _fact("situational.testing", "Wrote unit and integration tests with pytest at PH.Digital.", "Wrote unit and integration tests with pytest as part of the PH.Digital development workflow.", tags=["development", "situational", "testing"], provenance=LEGACY),
    _fact("situational.ai_assisted", "Uses Claude Code, GitHub Copilot, Cursor, and Codex with critical review before merging.", "Uses AI coding assistants including Claude Code, GitHub Copilot, Cursor, and Codex, with critical review before merging.", tags=["development", "situational", "ai-assisted"], provenance=LEGACY),
    _fact("situational.html_css", "Used HTML5 and CSS3 in React frontend work at PH.Digital.", "Used HTML5 and CSS3 as part of React frontend work at PH.Digital.", tags=["development", "situational", "frontend"], provenance=LEGACY),
    _fact("situational.yaml_json", "Used YAML and JSON configuration files to drive application behavior at PH.Digital.", "Used YAML and JSON configuration files to drive application behavior at PH.Digital.", tags=["development", "situational", "configuration"], provenance=LEGACY),
    _fact("situational.alembic", "Designed and applied Alembic migrations in personal projects.", "Designed and applied Alembic schema migrations in personal projects.", tags=["development", "situational", "databases"], provenance=LEGACY),
    _fact("situational.pydantic", "Used Pydantic v2 for validation and settings in personal FastAPI/Flask backends.", "Used Pydantic v2 for request/response validation and settings management in personal FastAPI and Flask backends.", tags=["development", "situational", "validation"], provenance=LEGACY),
    _fact("situational.vite_tailwind", "Used Vite and Tailwind CSS across personal and freelance frontend projects.", "Used Vite and Tailwind CSS across personal and freelance frontend projects.", tags=["development", "situational", "frontend"], provenance=LEGACY),
    _fact("situational.sentry_slowapi", "Integrated Sentry and slowapi in a personal FastAPI backend.", "Integrated Sentry monitoring and slowapi rate limiting in a personal FastAPI backend.", tags=["development", "situational", "monitoring"], provenance=LEGACY),
    _fact("situational.sse", "Built async FastAPI endpoints with Server-Sent Events in a personal project.", "Built async FastAPI endpoints with Server-Sent Events for live updates in a personal project.", tags=["development", "situational", "async"], provenance=LEGACY),
    _fact("situational.gmail_oauth", "Implemented Gmail API OAuth for automated email scanning in a personal project.", "Implemented a Gmail API OAuth flow for automated email scanning in a personal project.", tags=["development", "situational", "oauth"], provenance=LEGACY),
    _fact("situational.ml", "Built a PyTorch transfer-learning image classifier with ResNet as a personal project.", "Built a PyTorch image-classification pipeline using transfer learning with ResNet as a personal project.", tags=["development", "situational", "machine-learning"], provenance=LEGACY),
]


CANONICAL_SOURCES = {
    "common.md": ("Common Canonical Facts", COMMON_FACTS),
    "sales.md": ("Sales Canonical Facts", SALES_FACTS),
    "development.md": ("Development Canonical Facts", DEVELOPMENT_FACTS),
    "situational_skills.md": ("Situational Canonical Facts", SITUATIONAL_FACTS),
}


def source_texts() -> dict[str, str]:
    result = {}
    for name, (title, facts) in CANONICAL_SOURCES.items():
        source = FactSource.model_validate({"source_version": "1.0.0", "facts": facts})
        result[name] = render_fact_source(title, source)
    return result


def write_canonical_sources(base_dir: Path) -> list[Path]:
    base_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in source_texts().items():
        path = base_dir / name
        if path.exists():
            raise FileExistsError(f"refusing to overwrite canonical source: {path}")
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
