# NexShift

# SmartShift

A smart shift-scheduling backend built with **Django, Django REST Framework and Google OR-Tools**. It generates an optimized work schedule automatically while respecting leave, skills, rest hours, overtime limits and fairness between employees. It was designed for hospitals (nurse scheduling), but the model is generic: departments, employees, skills and shift types are all configurable, so it also fits factories, call centers and any shift-based team.

> Status: backend prototype. The frontend, open-shift board, preferences, carry-over and background solving are on the roadmap below.

## The problem it solves

A hospital may have 200 nurses and 12 departments. Every department needs a set number of staff per shift, and every employee has constraints: one works only in intensive care, one is on leave for three days, one is near the overtime limit, one has worked too many night shifts, and the ER needs experienced staff at night. Building a schedule that satisfies all of this by hand is slow and error-prone. SmartShift searches for the **best** valid schedule, not just any valid one.

## Features

**Scheduling engine (OR-Tools CP-SAT)**
- Automatic schedule generation from demand rules (employees per department per shift).
- Hard rules that are never broken: approved leave, department eligibility, no overlapping shifts, minimum rest after each shift, monthly hour cap, night-shift cap, locked assignments.
- Soft rules that are optimized: overtime cost, working outside the home department, and fairness (night shifts, weekend/holiday shifts, total hours).
- Requirements: minimum headcount, minimum experienced staff, and required skills per shift.
- When staffing is too low the solver still returns a schedule, records every unfilled requirement as a **shortage**, and explains why in one sentence.
- Locked (manual) assignments are preserved when the solver re-runs.

**Scenarios**
- Duplicate a schedule, generate it with different options, and compare solver statistics side by side.

**Employees and requests**
- Employees log in and see only their own shifts.
- Leave requests with an approval workflow.
- Objections, change requests and shift swaps between colleagues (colleague accepts, scheduler approves, rules are re-checked before the swap is applied).

**Flexible configuration**
- Admin-defined shift types (start time, duration, minimum rest after the shift, night flag). Default pattern: 12 hours work, 24 hours rest.
- Departments, skills with levels, holidays, global work rules with per-employee overrides.
- Persian (Jalali) calendar: the database stores Gregorian dates, and the API accepts and returns Jalali dates (Persian digits accepted).

**Notifications and audit**
- In-app notifications (schedule published, shift changed, leave approved, requests).
- Audit log of who did what and when.

**Security**
- Accounts are created only by the admin; there is no public signup.
- JWT authentication, forced password change on first login and after admin reset.
- Account lockout after repeated failed logins (django-axes) and an offline captcha (django-simple-captcha, no external service).
- HTTPS through Caddy when running in Docker.

## Tech stack

Python 3.12, Django 5.2, Django REST Framework, SimpleJWT, django-filter, drf-spectacular (Swagger), OR-Tools, PostgreSQL (SQLite for local development), Docker Compose, Caddy, Gunicorn, WhiteNoise.

## Project structure

```
smartshift/
├── manage.py
├── ozzy/                  settings.py, urls.py
└── apps/
    ├── core/              Jalali dates, permissions, shared mixins
    ├── accounts/          users, JWT login, captcha, password rules
    ├── department/        departments, skills, shift types, holidays, work rules
    ├── staff/             employees, skills per employee, leave requests
    ├── schedule/        schedules, demand rules, assignments, shortages
    ├── shiftreq/    objections, change requests, swaps
    ├── solver/            OR-Tools engine and generate endpoint
    ├── notif/     in-app notifications
    └── audit/             audit log
```

## Quick start (local)

```bat
git clone <your-repo-url>
cd smartshift
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` (set a real `SECRET_KEY`; keep `USE_SQLITE=True` for an easy start), then:

```bat
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/api/docs/` for the interactive API docs. Demo employees are `employee01`, `employee02`, ... with the password `Employee12345!`.

## Quick start (Docker, PostgreSQL + HTTPS)

```bat
copy .env.example .env
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

Open `https://localhost/api/v1/docs/`.

## How to generate a schedule

1. Log in: `GET /api/accounts/captcha/`, then `POST /api/accounts/token/` with username, password, `captcha_key` and `captcha_value`.
2. Define departments, shift types and demand rules, and add employees.
3. Create a schedule: `POST /api/schedule/schedules/`.
4. Generate it: `POST /api/solver/schedules/{id}/generate/`.
5. Review assignments and shortages, then publish: `POST /api/schedule/schedules/{id}/publish/`.

## Main API endpoints

All endpoints are under `/api/`.

| Area | Endpoint |
|---|---|
| Auth | `accounts/captcha/`, `accounts/token/`, `accounts/token/refresh/`, `accounts/me/`, `accounts/me/change-password/` |
| Users (admin) | `accounts/users/` |
| Organization | `department/departments/`, `skills/`, `shift-types/`, `holidays/`, `work-rules/` |
| Employees | `staff/employees/`, `staff/employees/me/`, `staff/leave-requests/` |
| Scheduling | `schedule/schedules/` (`publish`, `archive`, `duplicate`, `compare`), `assignments/` (`my`), `demand-rules/`, `shortages/` |
| Requests | `requests/` (`accept`, `decline`, `approve`, `reject`, `cancel`) |
| Solver | `solver/schedules/{id}/generate/` |
| Notifications | `notif/` (`unread-count`, `mark-read`, `mark-all-read`) |
| Audit (admin) | `audit/logs/` |

## Roadmap

- [ ] Employee preferences (days off, extra availability) fed into the solver, balanced fairly when many people want the same day
- [ ] Open-shift board: absent employee's shift is released, colleagues claim it, auto-assignment 3 hours before the shift if nobody does
- [ ] Carry-over: rest rules across the month boundary
- [ ] Background solving with Celery and Redis
- [ ] Absence substitution suggestions and conflict reports
- [ ] Persian RTL web frontend (HTML, CSS, HTMX)
- [ ] Excel and PDF export
- [ ] Automated tests

## License
Nothing yet.

---

<a id="فارسی"></a>

<div dir="rtl" align="right">

# شیفت‌یار هوشمند (فارسی)

یک بک‌اند هوشمند برای **برنامه‌ریزی شیفت** که با **جنگو، Django REST Framework و OR-Tools گوگل** ساخته شده است. این سیستم به‌صورت خودکار یک برنامه‌ی شیفت بهینه تولید می‌کند و در عین حال مرخصی‌ها، مهارت‌ها، ساعت استراحت، سقف اضافه‌کاری و عدالت بین کارکنان را رعایت می‌کند. طراحی اولیه برای بیمارستان (برنامه‌ریزی پرستاران) است، اما مدل داده عمومی است: بخش‌ها، کارکنان، مهارت‌ها و انواع شیفت همگی قابل تنظیم‌اند، پس برای کارخانه، مرکز تماس و هر تیم شیفتی دیگری هم مناسب است.

> وضعیت: نمونه‌ی اولیه‌ی بک‌اند. رابط کاربری، تابلوی شیفت‌های باز، ترجیحات کارکنان، انتقال از ماه قبل و حل‌کردن در پس‌زمینه در نقشه‌ی راه (پایین) آمده‌اند.

## چه مشکلی را حل می‌کند؟

یک بیمارستان ممکن است ۲۰۰ پرستار و ۱۲ بخش داشته باشد. هر بخش در هر شیفت تعداد مشخصی نیرو لازم دارد و هر نفر محدودیت‌هایی دارد: یکی فقط در مراقبت‌های ویژه کار می‌کند، یکی سه روز مرخصی گرفته، یکی به سقف اضافه‌کاری نزدیک است، یکی شیفت شب زیاد داشته، و اورژانس در شب به نیروی باتجربه نیاز دارد. ساختن دستی برنامه‌ای که همه‌ی این‌ها را رعایت کند کند و پرخطاست. شیفت‌یار فقط یک برنامه‌ی معتبر نمی‌سازد؛ **بهترین** برنامه را جست‌وجو می‌کند.

## امکانات

**موتور برنامه‌ریزی (OR-Tools CP-SAT)**
- تولید خودکار برنامه از روی قوانین نیازمندی (تعداد نیرو در هر بخش و هر شیفت).
- قوانین سخت که هرگز نقض نمی‌شوند: مرخصی تأییدشده، مجاز بودن بخش، نبودن شیفت هم‌پوشان، حداقل استراحت بعد از هر شیفت، سقف ساعت ماهانه، سقف شیفت شب، و شیفت‌های قفل‌شده.
- قوانین نرم که بهینه می‌شوند: هزینه‌ی اضافه‌کاری، کار در بخشی غیر از بخش اصلی، و عدالت (شیفت شب، شیفت تعطیل و آخر هفته، مجموع ساعت).
- نیازمندی‌ها: حداقل تعداد نیرو، حداقل نیروی باتجربه، و مهارت لازم در هر شیفت.
- اگر نیرو کم باشد، سیستم باز هم برنامه می‌دهد، هر نیازمندی پرنشده را به‌عنوان **کمبود** ثبت می‌کند و دلیلش را در یک جمله توضیح می‌دهد.
- شیفت‌های قفل‌شده (دستی) هنگام اجرای دوباره‌ی حل‌کننده حفظ می‌شوند.

**سناریوها**
- یک برنامه را کپی کنید، با تنظیمات دیگر دوباره تولید کنید و آمار حل‌کننده را کنار هم مقایسه کنید.

**کارکنان و درخواست‌ها**
- کارکنان وارد حساب خود می‌شوند و فقط شیفت‌های خودشان را می‌بینند.
- درخواست مرخصی با گردش کار تأیید.
- اعتراض، درخواست تغییر و جابه‌جایی شیفت بین همکاران (همکار می‌پذیرد، مسئول برنامه‌ریزی تأیید می‌کند و قبل از اعمال، قوانین دوباره بررسی می‌شوند).

**تنظیمات انعطاف‌پذیر**
- انواع شیفت توسط مدیر تعریف می‌شود (ساعت شروع، مدت، حداقل استراحت بعد از شیفت، شیفت شب). حالت پیش‌فرض: ۱۲ ساعت کار و ۲۴ ساعت استراحت.
- بخش‌ها، مهارت‌ها با سطح، تعطیلات، و قوانین کاری سراسری با امکان استثنا برای هر کارمند.
- تقویم شمسی: پایگاه داده تاریخ میلادی ذخیره می‌کند و API تاریخ شمسی دریافت و برمی‌گرداند (ارقام فارسی هم پذیرفته می‌شود).

**اعلان‌ها و ثبت رویدادها**
- اعلان درون‌برنامه‌ای (انتشار برنامه، تغییر شیفت، تأیید مرخصی، درخواست‌ها).
- گزارش حسابرسی از اینکه چه کسی چه کاری و کی انجام داده است.

**امنیت**
- حساب‌ها فقط توسط مدیر ساخته می‌شوند و ثبت‌نام عمومی وجود ندارد.
- احراز هویت با JWT، تغییر اجباری رمز در اولین ورود و بعد از بازنشانی رمز توسط مدیر.
- قفل‌شدن حساب پس از چند ورود ناموفق (django-axes) و کپچای آفلاین (django-simple-captcha) بدون هیچ سرویس خارجی.
- HTTPS با Caddy هنگام اجرا در داکر.

## فناوری‌ها

Python 3.12، Django 5.2، Django REST Framework، SimpleJWT، django-filter، drf-spectacular (Swagger)، OR-Tools، PostgreSQL (و SQLite برای توسعه‌ی محلی)، Docker Compose، Caddy، Gunicorn، WhiteNoise.

## ساختار پروژه

</div>

```
smartshift/
├── manage.py
├── ozzy/                  settings.py, urls.py
└── apps/
    ├── core/              تاریخ شمسی، دسترسی‌ها، ابزارهای مشترک
    ├── accounts/          کاربران، ورود JWT، کپچا، قوانین رمز
    ├── department/        بخش‌ها، مهارت‌ها، انواع شیفت، تعطیلات، قوانین کاری
    ├── staff/             کارکنان، مهارت‌ها، درخواست مرخصی
    ├── schedule/        برنامه‌ها، نیازمندی‌ها، شیفت‌ها، کمبودها
    ├── shiftreq/    اعتراض، تغییر، جابه‌جایی
    ├── solver/            موتور OR-Tools و مسیر تولید برنامه
    ├── notif/     اعلان‌ها
    └── audit/             گزارش حسابرسی
```

<div dir="rtl" align="right">

## شروع سریع (محلی)

</div>

```bat
git clone <your-repo-url>
cd smartshift
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

<div dir="rtl" align="right">

فایل `.env` را ویرایش کنید (یک `SECRET_KEY` واقعی بگذارید و برای شروع آسان `USE_SQLITE=True` را نگه دارید)، سپس:

</div>

```bat
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

<div dir="rtl" align="right">

آدرس `http://127.0.0.1:8000/api/docs/` مستندات تعاملی API را باز می‌کند. کارکنان نمونه `employee01`، `employee02` و ... هستند با رمز `Employee12345!`.

## شروع سریع (داکر، PostgreSQL و HTTPS)

</div>

```bat
copy .env.example .env
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
```

<div dir="rtl" align="right">

سپس `https://localhost/api/docs/` را باز کنید.

## چطور برنامه بسازیم؟

۱. ورود: ابتدا `GET /api/accounts/captcha/` و بعد `POST /api/accounts/token/` با نام کاربری، رمز، `captcha_key` و `captcha_value`.
۲. بخش‌ها، انواع شیفت و قوانین نیازمندی را تعریف کنید و کارکنان را اضافه کنید.
۳. برنامه بسازید: `POST /api/schedule/schedules/`.
۴. تولید خودکار: `POST /api/solver/schedules/{id}/generate/`.
۵. شیفت‌ها و کمبودها را بررسی کنید و منتشر کنید: `POST /api/schedule/schedules/{id}/publish/`.

## مسیرهای اصلی API

همه‌ی مسیرها زیر `/api/v1/` هستند.

| بخش | مسیر |
|---|---|
| احراز هویت | `accounts/captcha/`، `accounts/token/`، `accounts/token/refresh/`، `accounts/me/`، `accounts/me/change-password/` |
| کاربران (مدیر) | `accounts/users/` |
| سازمان | `department/departments/`، `skills/`، `shift-types/`، `holidays/`، `work-rules/` |
| کارکنان | `staff/employees/`، `staff/employees/me/`، `staff/leave-requests/` |
| برنامه‌ریزی | `schedule/schedules/` (`publish`، `archive`، `duplicate`، `compare`)، `assignments/` (`my`)، `demand-rules/`، `shortages/` |
| درخواست‌ها | `requests/` (`accept`، `decline`، `approve`، `reject`، `cancel`) |
| حل‌کننده | `solver/schedules/{id}/generate/` |
| اعلان‌ها | `notif/` (`unread-count`، `mark-read`، `mark-all-read`) |
| حسابرسی (مدیر) | `audit/logs/` |

## نقشه‌ی راه

- [ ] ترجیحات کارکنان (روز مرخصی، آمادگی برای کار اضافه) به‌عنوان ورودی حل‌کننده، با توزیع عادلانه وقتی چند نفر یک روز را می‌خواهند
- [ ] تابلوی شیفت‌های باز: شیفت فرد غایب آزاد می‌شود، همکاران آن را برمی‌دارند، و اگر تا ۳ ساعت قبل از شروع کسی برنداشت، سیستم خودکار تخصیص می‌دهد
- [ ] انتقال از ماه قبل: رعایت قوانین استراحت در مرز دو ماه
- [ ] حل‌کردن در پس‌زمینه با Celery و Redis
- [ ] پیشنهاد جایگزین برای غیبت و گزارش تعارض‌ها
- [ ] رابط وب فارسی و راست‌به‌چپ (HTML، CSS، HTMX)
- [ ] خروجی Excel و PDF
- [ ] تست‌های خودکار

## مجوز


</div>
