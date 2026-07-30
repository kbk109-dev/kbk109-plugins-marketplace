# GA4 Recommended Events Reference

This reference lists GA4 recommended events relevant to mobile apps, especially content/reading apps.
Use recommended event names whenever possible — they get automatic reporting in GA4 dashboards.

## Table of Contents

1. [Screen & Navigation](#screen--navigation)
2. [Content Engagement](#content-engagement)
3. [Search](#search)
4. [User Lifecycle](#user-lifecycle)
5. [App Lifecycle](#app-lifecycle)
6. [Custom Event Naming Guide](#custom-event-naming-guide)
7. [Parameter Reference](#parameter-reference)

---

## Screen & Navigation

| Event Name    | Type        | Parameters                    | When to Use             |
| ------------- | ----------- | ----------------------------- | ----------------------- |
| `screen_view` | recommended | `screen_name`, `screen_class` | Every screen transition |

**Implementation note**: Firebase automatically logs `screen_view` on Android Activity changes, but React Native is single-Activity. You must log `screen_view` manually on every route change.

---

## Content Engagement

| Event Name       | Type        | Parameters                              | When to Use                                          |
| ---------------- | ----------- | --------------------------------------- | ---------------------------------------------------- |
| `select_content` | recommended | `content_type`, `item_id`               | User taps on a content item (book, chapter, summary) |
| `view_item`      | recommended | `item_id`, `item_name`, `item_category` | User views detail page of a book                     |
| `share`          | recommended | `content_type`, `item_id`, `method`     | User shares content                                  |

---

## Search

| Event Name            | Type        | Parameters    | When to Use                  |
| --------------------- | ----------- | ------------- | ---------------------------- |
| `search`              | recommended | `search_term` | User performs a search query |
| `view_search_results` | recommended | `search_term` | Search results are displayed |

**Privacy note**: Never include PII in `search_term`. If search content could contain personal data, hash or truncate it.

---

## User Lifecycle

| Event Name          | Type        | Parameters | When to Use                            |
| ------------------- | ----------- | ---------- | -------------------------------------- |
| `sign_up`           | recommended | `method`   | User completes registration/onboarding |
| `login`             | recommended | `method`   | User logs in (if applicable)           |
| `tutorial_begin`    | recommended | —          | User starts onboarding flow            |
| `tutorial_complete` | recommended | —          | User completes onboarding flow         |

---

## App Lifecycle

| Event Name   | Type      | Parameters | When to Use                           |
| ------------ | --------- | ---------- | ------------------------------------- |
| `app_open`   | automatic | —          | Logged automatically by Firebase      |
| `app_update` | automatic | —          | Logged automatically after app update |
| `first_open` | automatic | —          | Logged automatically on first launch  |

---

## Custom Event Naming Guide

When no GA4 recommended event fits, create a custom event following these rules:

### Naming Convention

- **Format**: `{domain}_{action}` or `{domain}_{object}_{action}`
- **Case**: snake_case
- **Max length**: 40 characters
- **Prefix**: use the app's domain prefix for clarity

### Examples for a Book/Reading App

| Event Name                | Parameters                                              | Description                               |
| ------------------------- | ------------------------------------------------------- | ----------------------------------------- |
| `book_register`           | `book_id`, `method` (barcode/manual/cover)              | User registers a new book                 |
| `book_delete`             | `book_id`                                               | User deletes a book                       |
| `toc_scan`                | `book_id`, `page_count`                                 | User scans table of contents              |
| `toc_edit`                | `book_id`, `action` (add/remove/reorder)                | User edits ToC structure                  |
| `chapter_capture`         | `book_id`, `chapter_id`, `page_count`                   | User captures chapter pages               |
| `summary_start`           | `book_id`, `chapter_id`, `model_used`                   | Summary generation begins                 |
| `summary_complete`        | `book_id`, `chapter_id`, `duration_ms`, `quality_score` | Summary generation completes              |
| `summary_view`            | `book_id`, `chapter_id`, `detail_level`                 | User views a summary                      |
| `summary_feedback`        | `book_id`, `chapter_id`, `rating`, `feedback_type`      | User rates summary quality                |
| `model_download_start`    | `model_name`, `model_size_mb`                           | AI model download begins                  |
| `model_download_complete` | `model_name`, `duration_ms`                             | AI model download completes               |
| `ocr_process`             | `book_id`, `page_count`, `duration_ms`                  | OCR processing completes                  |
| `consent_granted`         | `consent_type`                                          | User grants analytics consent             |
| `consent_revoked`         | `consent_type`                                          | User revokes analytics consent            |
| `image_extract`           | `book_id`, `chapter_id`, `image_count`                  | Images extracted from pages               |
| `font_size_change`        | `direction` (increase/decrease), `new_size`             | User changes font size in viewer          |
| `view_mode_change`        | `mode` (split/single)                                   | User toggles split-view in summary viewer |
| `onboarding_step`         | `step_index`, `step_name`                               | User progresses through onboarding        |

### Reserved Prefixes (Do Not Use)

- `firebase_` — reserved by Firebase
- `google_` — reserved by Google
- `ga_` — reserved by Google Analytics

---

## Parameter Reference

### GA4 Recommended Parameters

| Parameter       | Type   | Max Length | Used With                       |
| --------------- | ------ | ---------- | ------------------------------- |
| `screen_name`   | string | 100 chars  | `screen_view`                   |
| `screen_class`  | string | 100 chars  | `screen_view`                   |
| `content_type`  | string | 100 chars  | `select_content`, `share`       |
| `item_id`       | string | 100 chars  | `select_content`, `view_item`   |
| `item_name`     | string | 100 chars  | `view_item`                     |
| `item_category` | string | 100 chars  | `view_item`                     |
| `search_term`   | string | 100 chars  | `search`, `view_search_results` |
| `method`        | string | 100 chars  | `sign_up`, `login`, `share`     |

### Custom Parameter Limits

- Max **25 custom parameters** per event
- Parameter name: max 40 characters, snake_case
- Parameter value (string): max 100 characters
- Parameter value (number): standard double precision

### User Property Limits

- Max **25 custom user properties** per project
- Name: max 24 characters
- Value: max 36 characters
