# DDW Email Assistant

> Enterprise-grade email automation plugin for DDW AI Hub — AI-powered email classification, smart drafts, and audit-ready auto-reply.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![DDW Platform](https://img.shields.io/badge/platform-DDW_AI_Hub-green.svg)](https://github.com/ccch713/ddw-ai-hub)

**[中文说明](#中文说明)** | English

## Overview

DDW Email Assistant is an enterprise-level email automation plugin for the [DDW AI Hub](https://github.com/ccch713/ddw-ai-hub) platform. It uses AI to classify, filter, and draft replies to emails — reducing your email processing time by 60-80%.

### Why DDW Email Assistant?

Most email AI tools force you to choose between **privacy** and **convenience**. DDW Email Assistant gives you both:

| Feature | DDW Email Assistant | OpenClaw / WorkBuddy | Inbox Zero |
|:--------|:-------------------|:---------------------|:-----------|
| **Data Security** | Self-hosted, data stays in your network | Cloud processing | Cloud/Gmail only |
| **Permission Control** | Built-in RBAC + audit logs | None | None |
| **Vendor Lock-in** | Zero (Apache 2.0 OSS) | Platform dependent | AGPL-3.0 |
| **China Email Support** | QQ / 163 / Tencent & Alibaba Enterprise | Limited | Gmail only |
| **LLM Cost** | ~¥0.02/month (100 emails/day) | Varies | ~$25+/month |
| **Deployment** | DDW plugin (server-side) | Local install | Docker + OAuth |

## Core Features

- **AI Email Classification** — Automatically categorizes emails into 5 types:
  - `need_reply` — Requires a response (direct questions, action items)
  - `simple_confirm` — Can be auto-replied (acknowledgments, confirmations)
  - `info_only` — FYI only (CC, system notifications, announcements)
  - `newsletter` — Subscriptions and marketing
  - `spam` — Junk and phishing

- **Smart Draft Generation** — AI generates professional reply drafts; you review and confirm before sending

- **Multi-Account IMAP/SMTP** — Supports unlimited email accounts with provider presets for Chinese email services

- **Encrypted Credential Storage** — AES-256 encryption for all stored credentials

- **Audit Trail** — Every automated action is logged for compliance and traceability

- **Web Dashboard** — Configure accounts, manage rules, review pending drafts

## Architecture

```
┌─────────────────────────────────────────────┐
│           DDW Email Assistant                │
├─────────────────────────────────────────────┤
│  Web Dashboard (FastAPI + HTML/JS)          │
├─────────────────────────────────────────────┤
│  AI Engine                                  │
│  ├── Email Classifier (LLM)                │
│  ├── Draft Generator (LLM)                 │
│  └── Rule Engine                            │
├─────────────────────────────────────────────┤
│  Email Layer                                │
│  ├── IMAP Client (Python stdlib)           │
│  ├── SMTP Client (Python stdlib)           │
│  └── Provider Adapters                      │
│      ├── QQ Mail (imap.qq.com)             │
│      ├── 163 Mail (imap.163.com)           │
│      ├── Tencent Enterprise Mail            │
│      ├── Alibaba Enterprise Mail            │
│      └── Generic IMAP/SMTP                 │
├─────────────────────────────────────────────┤
│  Storage (SQLite + AES-256 Encryption)      │
└─────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- DDW AI Hub platform (or standalone FastAPI server)
- Python 3.9+
- An email account with IMAP/SMTP enabled

### Installation

```bash
# Via DDW Plugin Marketplace
ddw plugin install ddw-email-assistant

# Or manual installation
cd plugins/
git clone https://github.com/ccch713/ddw-email-assistant.git
cd ddw-email-assistant
pip install -r requirements.txt
```

### Configuration

1. Access DDW dashboard → Plugins → Email Assistant
2. Add your email account (select provider from preset list)
3. Enter authorization code (see [获取授权码](#obtaining-authorization-codes) for Chinese email providers)
4. Configure LLM provider (API key for MiniMax/DeepSeek, or local Ollama)
5. Enable auto-classification and draft generation
6. Review and confirm drafts in the dashboard

### Obtaining Authorization Codes

Chinese email providers require authorization codes (not your regular password):

| Provider | Steps |
|:---------|:------|
| **QQ Mail** | Settings → Account → Enable IMAP/SMTP → Generate Authorization Code (requires SMS verification) |
| **163 Mail** | Settings → POP3/SMTP → Enable IMAP → Generate Authorization Code |
| **Tencent Enterprise** | Settings → Client Settings → Generate Client Password |
| **Alibaba Enterprise** | Settings → Email Client → Generate Client Password |

## API Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| GET | `/api/email/accounts` | List all email accounts |
| POST | `/api/email/accounts` | Add email account |
| PUT | `/api/email/accounts/{id}` | Update account |
| DELETE | `/api/email/accounts/{id}` | Delete account |
| POST | `/api/email/accounts/{id}/test` | Test connection |
| GET | `/api/email/messages` | List messages (paginated) |
| GET | `/api/email/messages/{id}` | Get message detail |
| POST | `/api/email/messages/{id}/classify` | Reclassify message |
| POST | `/api/email/messages/{id}/draft` | Generate reply draft |
| POST | `/api/email/messages/{id}/reply` | Send reply (after confirmation) |
| POST | `/api/email/messages/{id}/archive` | Archive message |
| POST | `/api/email/sync/{account_id}` | Manual sync |
| GET | `/api/email/stats` | Email statistics |
| GET | `/api/email/audit` | Audit log query |

## LLM Cost

Email processing is extremely lightweight:

| Scenario | Tokens/day | Monthly Cost (MiniMax Max) |
|:---------|:-----------|:---------------------------|
| Classification (100 emails) | ~20,000 | ~¥0.01 |
| Draft generation (10 replies) | ~5,000 | ~¥0.003 |
| Auto-reply (simple) | ~3,000 | ~¥0.002 |
| **Total** | **~28,000** | **~¥0.02** |

Works with any OpenAI-compatible API: MiniMax, DeepSeek, Qwen, or local LLM via Ollama.

## Security

- **AES-256 credential encryption** — All authorization codes encrypted at rest
- **Untrusted input handling** — Email body treated as untrusted data
- **Draft-first mode** — Auto-reply disabled by default; user confirms each reply
- **Audit logging** — All operations logged, logs retained for 90 days
- **No data leakage** — Self-hosted; email data never leaves your network

## Development

```bash
# Run tests
cd plugins/ddw-email-assistant
python -m pytest tests/ -v

# 34 tests covering models, services, providers, and API routes
```

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

---

## 中文说明

DDW 邮件助手是 [DDW AI 底座平台](https://github.com/ccch713/ddw-ai-hub) 的企业级邮件自动化插件，通过 AI 智能分类、草稿生成、自动回复，帮助企业和团队大幅降低邮件处理负担。

### 三大核心优势

1. **企业数据安全** — 自托管部署，邮件数据不出企业内网
2. **权限控制 + 审计日志** — 每封自动回复可追溯，基于 DDW 权限引擎
3. **无厂商锁定** — Apache 2.0 开源，可自由修改和部署

### 中国邮箱支持

原生支持 QQ 邮箱、163、腾讯企业邮、阿里企业邮，一键配置 IMAP/SMTP。

### LLM 成本

处理 100 封邮件/天，月成本仅 ¥0.02（MiniMax Max 套餐内）。兼容 MiniMax、DeepSeek、通义千问或任何 OpenAI 兼容 API，也支持本地 Ollama 小模型。

### 更多信息

- [DDW AI Hub 主项目](https://github.com/ccch713/ddw-ai-hub)
- [插件开发指南](https://github.com/ccch713/ddw-ai-hub/blob/main/docs/DDW_Plugin_Development_Guide.md)
