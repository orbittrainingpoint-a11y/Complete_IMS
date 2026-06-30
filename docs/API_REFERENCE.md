# API Reference Document
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25  
**Type:** Internal Django Views / AJAX Endpoints

---

## 1. Overview

Orbit ERP is a server-rendered Django application with a set of AJAX endpoints for dynamic interactions. All endpoints require an authenticated session (cookie-based). There is no REST API or token-based authentication.

**Base URL:** `http://localhost:8000/` (development)  
**Authentication:** Session-based (`sessionid` cookie)  
**CSRF:** Required on all POST/PUT/DELETE requests (Django CSRF middleware)

---

## 2. Authentication Endpoints

### `GET /accounts/login/`
Display login form.

**Response:** HTML login page

### `POST /accounts/login/`
Authenticate user.

| Parameter | Type | Required |
|-----------|------|----------|
| username | string | Yes |
| password | string | Yes |
| csrfmiddlewaretoken | string | Yes |

**Success:** Redirect to `/` (302)  
**Failure:** Login form with error message

### `GET /logout/`
Log out current user.

**Response:** Redirect to login page (302)

### `GET /signup/`
**Access:** Admin only

Display user creation form.

### `POST /signup/`
**Access:** Admin only

Create new user account.

---

## 3. Dashboard Endpoints

### `GET /`
Main orbit dashboard with KPI overview.

**Response:** HTML — registration stats, invoice totals, lead summary

### `GET /dashboard/`
Invoice dashboard with tabbed invoice lists.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| invoice_number | string | Filter by invoice number |
| registration_number | string | Filter by registration number |
| name | string | Filter by client name |
| due_date | date | Filter by due date |
| payment_status | string | Filter by payment status |

**Response:** HTML — paginated invoice list

---

## 4. Invoice Endpoints

### `GET /create_invoice/`
Display invoice creation form.

### `POST /create_invoice/`
Create new sales invoice.

**Form Data:**
| Field | Type | Required |
|-------|------|----------|
| registration | integer | No |
| client | integer | Yes |
| course | integer | No |
| date | date | Yes |
| due_date | date | Yes |
| class_type | string | Yes |
| status | string | Yes |
| payment | string | Yes |
| total_amount | decimal | Yes |
| amount_paid | decimal | Yes |
| discount | decimal | No |
| number_of_person | integer | Yes |
| po_number | string | No |

**Success:** Redirect to `/add_invoice_items/{id}/`

### `GET /add_invoice_items/<invoice_id>/`
Display item addition form for invoice.

### `POST /add_invoice_items/<invoice_id>/`
Add line items to invoice.

**Formset Data (repeated per item):**
| Field | Type |
|-------|------|
| form-{n}-course | integer |
| form-{n}-description | string |
| form-{n}-quantity | integer |
| form-{n}-unit_price | decimal |
| form-{n}-vat_rate | decimal |

### `GET /invoice/<id>/edit/`
Display invoice edit form.

### `POST /invoice/<id>/edit/`
Update invoice.

### `GET /invoice/<id>/delete/`
Display delete confirmation.

### `POST /invoice/<id>/delete/`
**Access:** Admin only  
Delete invoice and all line items.

---

## 5. Purchase Invoice Endpoints

Same pattern as sales invoices:

- `GET/POST /create_purchase_invoice/`
- `GET/POST /invoice_purchase/<id>/edit/`
- `GET/POST /invoice_purchase/<id>/delete/`

---

## 6. Registration Endpoints

### `GET /register/`
Display student registration form.

### `POST /register/`
Create new student registration.

**Key Form Data:**
| Field | Type | Notes |
|-------|------|-------|
| registration_type | string | 'OT' or 'OC' |
| class_type | string | online/offline/batch/private |
| first_name | string | |
| last_name | string | |
| passport_no | string | |
| email | email | |
| phone_no | string | |
| consultant_name | string | |
| courses | ManyToMany | Course IDs |

**Success:** Redirect to `/student-dashboard/` with registration number

### `GET /student-dashboard/`
List all individual registrations.

### `GET /corporate_dashboard/`
List all corporate registrations.

### `GET /edit-registration/<id>/`
Display registration edit form.

### `POST /edit-registration/<id>/`
Update registration.

### `GET /delete-registration/<id>/`
Confirmation page.

### `POST /delete-registration/<id>/`
**Access:** Admin only  
Delete registration.

### `GET /print-registration/<id>/`
Render printable registration form.

**Response:** Print-optimized HTML

---

## 7. AJAX Endpoints

### `GET /get_course_details/`
Get course pricing by course ID and class type.

**Query Parameters:**
| Parameter | Type | Required |
|-----------|------|----------|
| course_id | integer | Yes |
| class_type | string | Yes |

**Response:**
```json
{
    "rate": "1500.00",
    "batch_rate": "1200.00",
    "online_rate": "1000.00",
    "private_rate": "2000.00"
}
```

### `GET /get_registration_details/`
Get registration details including linked invoice.

**Query Parameters:**
| Parameter | Type |
|-----------|------|
| registration_id | integer |

**Response:**
```json
{
    "registration_number": "OT/24/06/001",
    "student_name": "John Doe",
    "invoice_id": 123,
    "invoice_number": "24/06/001",
    "total_amount": "1500.00",
    "amount_paid": "500.00"
}
```

### `GET /get_invoice_details/`
Get invoice line items as JSON.

**Query Parameters:**
| Parameter | Type |
|-----------|------|
| invoice_id | integer |

**Response:**
```json
{
    "items": [
        {
            "course_name": "Project Management",
            "quantity": 1,
            "unit_price": "1500.00",
            "vat_rate": "5.00",
            "subtotal": "1500.00",
            "vat_amount": "75.00",
            "total": "1575.00"
        }
    ]
}
```

---

## 8. Lead / CRM Endpoints

### `GET /lead/`
Lead dashboard with statistics.

**Query Parameters:** status, source, course, date_from, date_to

### `GET/POST /lead/create/`
Create new lead.

### `GET/POST /lead/edit/<id>/`
Edit lead.

### `POST /lead/delete/<id>/`
**Access:** Admin  
Delete lead.

### `GET /lead/<lead_id>/`
**AJAX endpoint**  
Get lead details.

**Response:**
```json
{
    "id": 1,
    "full_name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "+971 50 1234567",
    "status": "Qualified",
    "source": "Website",
    "interested_course": "Project Management",
    "quote_amount": "1500.00",
    "notes": "...",
    "follow_up_date": "2024-07-01"
}
```

### `GET/POST /lead/follow-up/<lead_id>/`
Create follow-up for lead.

**POST Body:**
```json
{
    "contact_date": "2024-07-01",
    "contact_time": "10:00:00",
    "priority": "High",
    "status": "Pending",
    "notes": "Call to discuss pricing"
}
```

### `POST /leads/<lead_id>/add_comment/`
Add comment to lead.

**POST Body:** `{ "text": "Comment text" }`

**Response:** `{ "success": true }`

### `GET /lead/<lead_id>/comments/`
Get all comments for lead.

**Response:**
```json
{
    "comments": [
        {
            "id": 1,
            "user": "admin",
            "text": "Called - interested",
            "timestamp": "2024-06-25T10:30:00",
            "is_flagged": false
        }
    ]
}
```

### `POST /leads/comments/<comment_id>/toggle_flag/`
Toggle flag status of a comment.

**Response:** `{ "is_flagged": true }`

### `POST /leads/<lead_id>/update_quote/`
Update quote amount on lead.

**POST Body:** `{ "quote_amount": "1500.00" }`

### `GET /lead/dashboard-stats/`
Get CRM statistics.

**Response:**
```json
{
    "total": 18,
    "interested_highly": 5,
    "qualified": 8,
    "register_soon": 3,
    "other": 2
}
```

---

## 9. Coupon Endpoints

### `POST /validate-coupon/`
Validate a coupon code.

**POST Body:** `{ "code": "SAVE10" }`

**Success Response:**
```json
{
    "valid": true,
    "discount_percentage": "10.00",
    "message": "Coupon applied successfully"
}
```

**Failure Response:**
```json
{
    "valid": false,
    "message": "Invalid or inactive coupon code"
}
```

---

## 10. Certificate Endpoints

### `GET /certificates/`
List all certificates.

### `GET/POST /certificates/create/`
Create new certificate.

### `GET /certificates/print/<id>/`
Print certificate.

**Response:** Print-optimized HTML

### `GET/POST /certificates/khda-form/`
KHDA certificate upload form.

### `GET/POST /upload-certificate/<registration_id>/`
Upload certificate file for a registration.

**POST Form Data:**
| Field | Type |
|-------|------|
| certificate_file | file (PDF/image) |

### `GET/POST /upload-form/<registration_id>/`
Upload registration form document.

---

## 11. Quotation Endpoints

### `GET/POST /quotation/create/`
Create quotation with items formset.

### `GET /quotation/`
List all quotations.

### `GET /quotation_detail/<id>/`
View/print quotation detail.

### `GET/POST /quotation/<id>/edit/`
Edit quotation.

### `GET/POST /quotation/<id>/delete/`
Delete quotation.

---

## 12. Proposal Endpoints

### `GET /proposals/`
List all proposals.

### `GET/POST /proposals/create/`
Create proposal with logo upload.

**POST Form Data (multipart/form-data):**
| Field | Type | Notes |
|-------|------|-------|
| client_name | string | |
| course | integer | |
| presenter_title | string | |
| date | date | |
| location | string | |
| trainer | integer | Optional |
| logo | file | PNG, 800×300px |

### `GET/POST /proposals/<id>/edit/`
Edit proposal.

### `GET /proposals/<id>/print/`
Print/view proposal PDF.

### `POST /remove_logo/<proposal_id>/`
Remove logo from proposal.

---

## 13. Course Endpoints

### `GET /courses/`
List all courses.

### `GET/POST /courses/create/`
Create course.

### `GET /courses/<id>/`
Course detail with enrolled students and content.

### `GET/POST /courses/<id>/update/`
Update course.

### `GET/POST /courses/<id>/delete/`
Delete course.

### `GET/POST /courses/<id>/content/create/`
Upload course material.

**POST Form Data (multipart/form-data):**
| Field | Type |
|-------|------|
| title | string |
| file | file |

### `GET/POST /content/<id>/delete/`
Delete course material.

---

## 14. Error Handling

| Status | Cause | Response |
|--------|-------|---------|
| 302 | Unauthenticated access | Redirect to `/accounts/login/?next={url}` |
| 403 | Non-admin attempts admin action | Redirect with error message |
| 404 | Object not found | Django 404 page |
| 500 | Server error | Django error page (DEBUG=True shows traceback) |

---

## 15. CSRF Token

All POST requests require CSRF token:

**Method 1 — Cookie:**
```javascript
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');
```

**Method 2 — Template tag:**
```html
<form method="post">
    {% csrf_token %}
    ...
</form>
```

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*
