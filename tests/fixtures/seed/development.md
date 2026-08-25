# Development Canonical Facts

This file is an authoritative fact source. Edit facts through the fact lifecycle; profiles may reference IDs but must not copy content.

```json
{
  "source_version": "1.0.4",
  "facts": [
    {
      "fact_id": "development.summary",
      "meaning": "Full-Stack Developer specializing in Python/FastAPI and React with production CRM and workflow experience and business-process understanding.",
      "renderings": {
        "en": "Full-Stack Developer specializing in Python/FastAPI and React, with production experience building CRM and workflow systems end to end and a strong understanding of business processes.",
        "he": "מפתח Full-Stack המתמחה ב-Python/FastAPI וב-React, עם ניסיון מקצועי בבניית מערכות CRM ותהליכי עבודה מקצה לקצה והבנה חזקה של תהליכים עסקיים."
      },
      "tags": [
        "development",
        "summary"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "paragraph",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.role",
      "meaning": "Historical title: Full-Stack Developer at PH.Digital, Herzliya.",
      "renderings": {
        "en": "Full-Stack Developer | PH.Digital, Herzliya",
        "he": "Full-Stack Developer | PH.Digital, הרצליה"
      },
      "tags": [
        "development",
        "historical-title"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": "2025-02/2026-06",
      "replaces": null,
      "source_file": "",
      "resume_style": "heading",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.dates",
      "meaning": "PH.Digital role dates are February 2025 to June 2026, approximately 1 year and 5 months.",
      "renderings": {
        "en": "February 2025 - June 2026",
        "he": "פברואר 2025 - יוני 2026"
      },
      "tags": [
        "development",
        "date"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; months supplied by the user 2026-08-17 from their LinkedIn employment record (Feb 2025 - Jun 2026, 1 yr 5 mos)",
      "confirmed_at": null,
      "effective_dates": "2025-02/2026-06",
      "replaces": null,
      "source_file": "",
      "resume_style": "date",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.fullstack",
      "meaning": "Built and maintained full-stack applications with React, TypeScript, and Python/FastAPI from PostgreSQL data models and APIs through frontend implementation.",
      "renderings": {
        "en": "Built and maintained full-stack applications with React, TypeScript, and Python/FastAPI, owning features from PostgreSQL data modeling and APIs through frontend implementation.",
        "he": "פיתוח ותחזוקה של אפליקציות full-stack ב-React, ב-TypeScript וב-Python/FastAPI, כולל אחריות על פיצ'רים ממודלי נתונים ב-PostgreSQL ו-APIs ועד המימוש בצד הלקוח."
      },
      "tags": [
        "development",
        "technical",
        "full-stack"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; TypeScript added on explicit user confirmation 2026-08-17 that the main PH.Digital production applications were written in TypeScript",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.crm",
      "meaning": "Architected a production CRM on PostgreSQL with workflow automation, role-based authentication, scheduled jobs, and state-driven processes.",
      "renderings": {
        "en": "Architected a production CRM on PostgreSQL with workflow automation, role-based authentication, scheduled jobs, and state-driven business processes.",
        "he": "תכנון מערכת CRM ב-production על PostgreSQL עם אוטומציית תהליכים, הרשאות מבוססות תפקיד, משימות מתוזמנות ותהליכים עסקיים מבוססי state."
      },
      "tags": [
        "development",
        "backend",
        "databases"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.cicd",
      "meaning": "Set up GitHub Actions CI/CD for linting, tests, migration checks, and OpenAPI contract sync.",
      "renderings": {
        "en": "Set up GitHub Actions CI/CD covering linting, automated tests, database migration checks, and OpenAPI contract sync.",
        "he": "הקמת CI/CD ב-GitHub Actions עבור linting, בדיקות אוטומטיות, בדיקות migrations וסנכרון חוזי OpenAPI."
      },
      "tags": [
        "development",
        "devops",
        "testing"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.nextjs",
      "meaning": "Built a customer marketing site with Next.js App Router, React Server Components, TypeScript, Tailwind CSS, RTL Hebrew, Sentry, and Vitest.",
      "renderings": {
        "en": "Built a customer-facing site with Next.js App Router, React Server Components, TypeScript, Tailwind CSS, RTL Hebrew, Sentry, and Vitest."
      },
      "tags": [
        "development",
        "frontend",
        "nextjs"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.integrations",
      "meaning": "Built WhatsApp/email integrations and asynchronous PDF/Excel generation with services, jobs, retries, scheduling, and status tracking.",
      "renderings": {
        "en": "Built WhatsApp and email integrations plus asynchronous PDF/Excel generation using reusable services, background jobs, retries, scheduling, and status tracking.",
        "he": "פיתוח אינטגרציות WhatsApp ודוא\"ל ותהליכי יצירת PDF/Excel אסינכרוניים באמצעות שירותים חוזרים, background jobs, retries, תזמון ומעקב סטטוס."
      },
      "tags": [
        "development",
        "integrations",
        "backend"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.phdigital.agile",
      "meaning": "Delivered features in Agile sprints with frontend and product teams.",
      "renderings": {
        "en": "Delivered features in Agile sprints, collaborating with frontend and product teams."
      },
      "tags": [
        "development",
        "collaboration",
        "agile"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.skills.backend",
      "meaning": "Backend skills: Python, FastAPI, Flask, Node.js, Express, REST APIs.",
      "renderings": {
        "en": "Backend: Python, FastAPI, Flask, Node.js, Express, REST APIs",
        "he": "Backend: Python, FastAPI, Flask, Node.js, Express, REST APIs"
      },
      "tags": [
        "development",
        "skill",
        "backend"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "item",
      "link_target": null
    },
    {
      "fact_id": "development.skills.frontend",
      "meaning": "Frontend skills: React, Next.js, TypeScript, JavaScript, Tailwind CSS.",
      "renderings": {
        "en": "Frontend: React, Next.js, TypeScript, JavaScript, Tailwind CSS",
        "he": "Frontend: React, Next.js, TypeScript, JavaScript, Tailwind CSS"
      },
      "tags": [
        "development",
        "skill",
        "frontend"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; Tailwind CSS surfaced on user confirmation 2026-08-17 from canonical development.phdigital.nextjs and situational.vite_tailwind",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "item",
      "link_target": null
    },
    {
      "fact_id": "development.skills.ai",
      "meaning": "AI integration skills: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering.",
      "renderings": {
        "en": "AI and LLM Integrations: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering",
        "he": "AI ו-LLM Integrations: OpenAI API, Anthropic API, LLM integrations, Prompt Engineering"
      },
      "tags": [
        "development",
        "skill",
        "ai"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "item",
      "link_target": null
    },
    {
      "fact_id": "development.skills.databases",
      "meaning": "Database skills: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL.",
      "renderings": {
        "en": "Databases: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL",
        "he": "Databases: PostgreSQL, MySQL, MongoDB, SQLAlchemy, SQL"
      },
      "tags": [
        "development",
        "skill",
        "databases"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "item",
      "link_target": null
    },
    {
      "fact_id": "development.skills.devops",
      "meaning": "DevOps and testing tool skills: Docker, GitHub Actions, Git, AWS EC2, pytest, Vitest, Postman.",
      "renderings": {
        "en": "DevOps & Testing: Docker, GitHub Actions, Git, AWS EC2, pytest, Vitest, Postman",
        "he": "DevOps ובדיקות: Docker, GitHub Actions, Git, AWS EC2, pytest, Vitest, Postman"
      },
      "tags": [
        "development",
        "skill",
        "devops"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; pytest and Vitest surfaced on user confirmation 2026-08-17 from canonical situational.testing and development.phdigital.nextjs",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "item",
      "link_target": null
    },
    {
      "fact_id": "development.project.mami",
      "meaning": "Personal Mami Supermarket project is a full-stack grocery platform using Flask, PostgreSQL, SQLAlchemy, React, TypeScript, Vite, Tailwind, JWT, Alembic, and Pydantic.",
      "renderings": {
        "en": "Mami Supermarket: full-stack grocery delivery and operations platform built with Flask, PostgreSQL, SQLAlchemy, React, TypeScript, Vite, Tailwind CSS, JWT, Alembic, and Pydantic."
      },
      "tags": [
        "development",
        "project",
        "full-stack"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.project.bar_exam",
      "meaning": "Personal Bar Exam Practice App uses FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic, JWT, slowapi, Sentry, PDF parsing, React, TypeScript, React Query, Zod, Tailwind, and pytest.",
      "renderings": {
        "en": "Bar Exam Practice App: FastAPI/PostgreSQL backend and React/TypeScript frontend with authentication, migrations, rate limiting, monitoring, PDF ingestion, and pytest coverage."
      },
      "tags": [
        "development",
        "project",
        "backend"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.project.gd",
      "meaning": "Freelance G.D Financial Services responsive marketing site used React, Vite, Tailwind CSS, Radix UI, React Hook Form, and Zod.",
      "renderings": {
        "en": "G.D Financial Services: responsive freelance marketing site built with React, Vite, Tailwind CSS, Radix UI, React Hook Form, and Zod."
      },
      "tags": [
        "development",
        "project",
        "frontend",
        "freelance"
      ],
      "status": "canonical",
      "provenance": "base/cv_base.md; migrated without strengthening",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet",
      "link_target": null
    },
    {
      "fact_id": "development.summary.frontend",
      "meaning": "Summary-level frontend positioning: builds user-facing applications with React, Next.js, and TypeScript.",
      "renderings": {
        "en": "Full-Stack Developer experienced in React, Next.js, and TypeScript.",
        "he": "מפתח Full-Stack עם ניסיון ב-React, ב-Next.js וב-TypeScript."
      },
      "tags": [
        "development",
        "summary",
        "frontend",
        "nextjs"
      ],
      "status": "canonical",
      "provenance": "Summary restatement of canonical development.phdigital.nextjs and development.skills.frontend; no new claim. User request 2026-08-17 to lead with TypeScript/React positioning.",
      "confirmed_at": "2026-08-17",
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "paragraph"
    },
    {
      "fact_id": "development.summary.backend",
      "meaning": "Summary-level backend positioning: production APIs, workflow systems, and PostgreSQL-based applications built with Python/FastAPI.",
      "renderings": {
        "en": "Strong backend experience building production APIs, workflow systems, and PostgreSQL-based applications with Python/FastAPI.",
        "he": "ניסיון backend חזק בבניית APIs ב-production, מערכות workflow ואפליקציות מבוססות PostgreSQL עם Python/FastAPI."
      },
      "tags": [
        "development",
        "summary",
        "backend",
        "databases"
      ],
      "status": "canonical",
      "provenance": "Summary restatement of canonical development.phdigital.fullstack and development.phdigital.crm; no new claim. User request 2026-08-17.",
      "confirmed_at": "2026-08-17",
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "paragraph"
    },
    {
      "fact_id": "development.summary.delivery",
      "meaning": "Summary-level delivery positioning: owns features from architecture and data modeling through frontend implementation, testing, and CI/CD.",
      "renderings": {
        "en": "Takes features from architecture and data modeling through frontend implementation, testing, and CI/CD.",
        "he": "מוביל פיצ׳רים מארכיטקטורה ומידול נתונים ועד למימוש frontend, בדיקות ו-CI/CD."
      },
      "tags": [
        "development",
        "summary",
        "full-stack",
        "testing",
        "devops"
      ],
      "status": "canonical",
      "provenance": "Summary restatement of canonical development.phdigital.fullstack and development.phdigital.cicd; no new claim. User request 2026-08-17.",
      "confirmed_at": "2026-08-17",
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "paragraph"
    },
    {
      "fact_id": "development.project.mm_backend_core.title",
      "meaning": "Project name and shape: mm-backend-core is a Node.js/Express CLI.",
      "renderings": {
        "en": "mm-backend-core — Node.js / Express CLI",
        "he": "mm-backend-core — CLI ב-Node.js / Express"
      },
      "tags": [
        "development",
        "project",
        "project-title",
        "backend",
        "nodejs"
      ],
      "status": "canonical",
      "provenance": "Project name as published; verified against https://github.com/matanmalka1/mm-backend-core and npm mm-backend-core@2.0.2.",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "heading"
    },
    {
      "fact_id": "development.project.mm_backend_core.links",
      "meaning": "mm-backend-core is publicly published on npm and public on GitHub; both are verifiable by a reader.",
      "renderings": {
        "en": "npmjs.com/package/mm-backend-core | github.com/matanmalka1/mm-backend-core",
        "he": "npmjs.com/package/mm-backend-core | github.com/matanmalka1/mm-backend-core"
      },
      "tags": [
        "development",
        "project",
        "open-source"
      ],
      "status": "canonical",
      "provenance": "Both URLs resolved 2026-08-17: npm registry returned mm-backend-core@2.0.2 (MIT, node>=18); GitHub API returned a public JavaScript repository.",
      "confirmed_at": null,
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "date"
    },
    {
      "fact_id": "development.project.mm_backend_core",
      "meaning": "Personal open-source project: built and published mm-backend-core, an npm-distributed Node.js/Express CLI that scaffolds a MongoDB REST API template with JWT auth and refresh tokens, RBAC, Passport OAuth, file uploads, Zod validation, Helmet/rate-limiting/mongo-sanitize security middleware, Winston logging, and Vitest/Supertest tests. Not PH.Digital work.",
      "renderings": {
        "en": "Built and published mm-backend-core on npm, a Node.js/Express backend scaffolding CLI generating a MongoDB REST API with JWT/RBAC authentication, OAuth, validation, security middleware, and automated testing.",
        "he": "פיתוח ופרסום של mm-backend-core ב-npm — CLI ליצירת שלד backend ב-Node.js/Express, המייצר REST API על MongoDB עם אימות JWT/RBAC, OAuth, ולידציה, middleware אבטחה ובדיקות אוטומטיות."
      },
      "tags": [
        "development",
        "project",
        "backend",
        "nodejs",
        "open-source",
        "testing"
      ],
      "status": "canonical",
      "provenance": "User statement 2026-08-17, independently verified against https://github.com/matanmalka1/mm-backend-core (public, JavaScript, MIT) and the npm registry (mm-backend-core@2.0.2, engines node>=18); template package.json confirms express@5, mongoose, passport OAuth, jsonwebtoken, multer, zod, helmet, express-rate-limit, express-mongo-sanitize, winston, vitest, supertest. Personal/open-source work; not attributable to PH.Digital.",
      "confirmed_at": "2026-08-17",
      "effective_dates": null,
      "replaces": null,
      "source_file": "",
      "resume_style": "bullet"
    }
  ]
}
```
