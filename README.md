# المرشد الأكاديمي الذكي | Bethlehem RAG

مشروع هاكاثون IEEE يساعد الطلاب على البحث في اللوائح الأكاديمية بالعربية. يختار الطالب الجامعة، ويعرض المرشد إجابة من وثائقها المفهرسة مع المراجع والمقتطفات وأرقام صفحات PDF عند توفرها. يستطيع المسؤول إضافة جامعات ورفع الوثائق من صفحة الإدارة.

## كيف يعمل المشروع؟

```text
React / Vite :5175 → Flask API :5000 → FastAPI RAG :8001
                                          ├── SQLite  · دليل الجامعات
                                          ├── ChromaDB · المقاطع والمتجهات
                                          └── Gemini  · التضمين وتوليد الإجابات
```

1. **الرفع.** يحدد المسؤول الجامعة ويرفع PDF أو TXT. يتحقق Flask وRAG من رمز الإدارة. تُستخرج النصوص، وتُقسّم إلى مقاطع من 1000 حرف بتداخل 150 حرفاً، وتُحفظ متجهات Gemini ذات 768 بُعداً مع معرّف الجامعة والوثيقة.
2. **البحث.** ترسل الواجهة السؤال ومعرّف الجامعة عبر Flask. يُطبّق RAG فلتر `university_id` داخل استعلام ChromaDB، ثم يعيد ترتيب المقاطع حسب التشابه الدلالي وتطابق الكلمات.
3. **الإجابة.** يولّد Gemini الرد من المقاطع المسترجعة. تتحقق الخدمة من معرّفات المراجع وتعرض رسالة عند عدم كفاية الأدلة. يمكن للطالب مقارنة الإجابة بالمقتطف الأصلي.

## هيكل المشروع

```text
Bethlehem_Rag/
├── frontend/
│   ├── src/pages/              # المحادثة والمستندات والإدارة
│   ├── src/services/           # عميل API والمحاكاة
│   └── package.json
├── backend/
│   ├── app.py                  # Flask ومصادقة الإدارة وتمرير الطلبات
│   ├── requirements.txt
│   └── README.md
├── rag-service/
│   ├── main.py                 # مسارات FastAPI
│   ├── ingestion.py            # استخراج النص وفهرسته
│   ├── retrieval.py            # عزل الجامعة والبحث وإعادة الترتيب
│   ├── generation.py           # توليد الإجابة والمراجع
│   ├── universities.py         # دليل الجامعات في SQLite
│   ├── migrate_universities.py  # النسخ الاحتياطي وترحيل الفهرس القديم
│   ├── requirements.txt
│   └── chroma_db/              # الفهرس المحلي ودليل الجامعات وقت التشغيل
└── .env.example
```

## الإعداد لأول مرة على Windows

المتطلبات هي **Python 3.12** و**Node.js 20 أو أحدث** مع npm، ومفتاح Gemini للتشغيل الفعلي. افتحي PowerShell في جذر المشروع. الأمر الأول يفتح نسخة المشروع داخل `IEEE` على سطح المكتب.

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag')
if (!(Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r rag-service\requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path rag-service\.env)) { Copy-Item rag-service\.env.example rag-service\.env }
npm.cmd --prefix frontend ci
```

| الملف | المتغيّر | القيمة |
| --- | --- | --- |
| `.env` في جذر المشروع | `RAG_SERVICE_URL` | `http://127.0.0.1:8001`. غيّري `8000` إلى `8001` إذا نسختِ القيمة القديمة من المثال. |
| `.env` في جذر المشروع | `RAG_ADMIN_TOKEN` | رمز عشوائي خاص تختارينه. القيمة الفارغة تعطّل إنشاء الجامعات والرفع. |
| `.env` في جذر المشروع | `RAG_CORS_ORIGINS` | عناوين الواجهة المسموح بها. الإعداد الافتراضي يشمل `http://localhost:5175`. |
| `rag-service/.env` | `GEMINI_API_KEY` | مفتاح Gemini الخاص بك. |
| `rag-service/.env` | `GEMINI_LLM_MODEL` | نموذج توليد متاح لحسابك. جرى التحقق سابقاً من `gemini-3.5-flash` على سؤال حقيقي في المشروع. |

احتفظي بالمفاتيح ورمز الإدارة في ملفات `.env` المحلية. بعد تغيير رمز الإدارة، أعيدي تشغيل Flask وRAG حتى تقرأ الخدمتان القيمة نفسها.

### ترحيل الفهرس القديم

نفّذي هذه الخطوة إذا كان عندك فهرس أُنشئ قبل إضافة `university_id`. أوقفي **كل عمليات RAG التي تستخدم الفهرس**، بما فيها أي نسخة على `8000` أو `8001`. من جذر المشروع:

```powershell
Push-Location rag-service
& ..\.venv\Scripts\python.exe -B migrate_universities.py
Pop-Location
```

السكربت ينسخ الفهرس إلى `rag-service/chroma-backup-*` قبل التعديل، ويربط الوثائق القديمة المعروفة بالاسم وبصمة المحتوى. راجعي الأعداد المطبوعة قبل التشغيل. تبقى الوثائق مجهولة الملكية خارج نتائج المحادثة. في التثبيت الجديد تخطّي هذه الخطوة.

## تشغيل الخدمات الثلاث

ابدئي من جذر المشروع في كل نافذة PowerShell، ونفّذي كل مجموعة في نافذة منفصلة.

**1. خدمة RAG على `8001`**

```powershell
Set-Location rag-service
& ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

شغّلي نسخة واحدة من RAG من مجلد `rag-service` لأن مسار ChromaDB نسبي لمجلد التشغيل.

**2. باك إند Flask على `5000`**

```powershell
& .\.venv\Scripts\python.exe -m flask --app backend.app run --host 127.0.0.1 --port 5000
```

**3. واجهة React على `5175`**

```powershell
Set-Location frontend
$env:VITE_API_BASE_URL = 'http://127.0.0.1:5000'
$env:VITE_USE_MOCK_API = 'false'
npm.cmd run dev -- --port 5175
```

خلي النوافذ مفتوحة، وافتحي [المحادثة](http://localhost:5175/)، أو [المستندات](http://localhost:5175/documents)، أو [الإدارة](http://localhost:5175/admin). لمعاينة الواجهة وحدها، اضبطي `VITE_USE_MOCK_API='true'` قبل تشغيل Vite.

## أول تجربة فعلية

1. افتحي [فحص RAG](http://127.0.0.1:8001/health) و[فحص Flask](http://127.0.0.1:5000/health). توقّعي `status: ok` في الاثنين.
2. من صفحة الإدارة، أدخلي `RAG_ADMIN_TOKEN` واختاري جامعة موجودة، أو أضيفي جامعة باسم ومعرّف ثابت مثل `najah`.
3. اختاري جامعة المستند وارفعي PDF أو TXT حتى 10 ميغابايت. تأكدي أن الملف ظهر في القائمة وأن عدد المقاطع زاد. رفع المحتوى نفسه للجامعة نفسها يرجع حالة «مفهرس مسبقاً».
4. من المحادثة اختاري نفس الجامعة واسألي عن بند في الملف. قارني الإجابة والمقتطف بالنص الأصلي. استخدمي وثائق أكاديمية عامة لأن المحادثة تعرض مقتطفاتها للطلاب.

## عقد API

طلبات المتصفح تتجه إلى Flask على `5000`. عمليات الإدارة تحمل `Authorization: Bearer <RAG_ADMIN_TOKEN>`.

| المسار | الاستخدام |
| --- | --- |
| `GET /health` | حالة الخدمة وعدد المقاطع. |
| `GET /universities` | قائمة `universities` بعناصر فيها `id` و`name`. |
| `POST /universities` | إنشاء جامعة بواسطة `id` و`name`. يتطلب رمز الإدارة. |
| `GET /documents` | قائمة الوثائق. يمكن فلترتها بواسطة `?university_id=birzeit`. |
| `POST /documents` | رفع multipart بحقلَي `file` و`university_id`. يتطلب رمز الإدارة. |
| `POST /chat` | يستقبل `question` و`university` و`top_k` الاختياري من 1 إلى 10. يعيد `answer` و`grounded` و`sources`. |

المصدر يتضمن `citation_id` و`filename` و`page` و`excerpt`. الملفات النصية ترجع `page: null`. مثال لفحص المحادثة:

```powershell
$body = @{ university = 'birzeit'; question = 'ما الحد الأقصى للساعات في الدورة الصيفية؟'; top_k = 4 } | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:5000/chat -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## تشخيص المشاكل

| الحالة | شو تفحصي؟ |
| --- | --- |
| Flask يرجع `503` في `/health` | افحصي RAG مباشرة على `8001`، وتحققي من تطابقه مع `RAG_SERVICE_URL`. |
| فحص الصحة يعمل، والمحادثة أو الرفع يرجع `429` أو `503` | راجعي سجل RAG. قد تكون حصة Gemini أو توفر نموذج التوليد هي السبب. |
| الرفع معطّل أو الرمز مرفوض | افحصي رمز الإدارة في `.env` الرئيسي. أعيدي تشغيل Flask وRAG بعد تغييره. |
| تظهر رسالة عدم كفاية المعلومات | افحصي الجامعة المختارة والوثائق المفهرسة لها. راجعي الترحيل إذا كان الفهرس قديماً. |
| المنفذ مستخدم | أوقفي النسخة القديمة من نافذتها بـ`Ctrl+C` قبل إعادة التشغيل. |
| تظهر بيانات تجريبية | أعيدي تشغيل Vite بقيمة `VITE_USE_MOCK_API='false'`. |

لفحص بناء الواجهة من جذر المشروع شغّلي `npm.cmd --prefix frontend run build`. يوثّق `rag-service/evaluation_results.json` تقييماً سابقاً مرتبطاً بالفهرس والنموذج وقت الاختبار.
