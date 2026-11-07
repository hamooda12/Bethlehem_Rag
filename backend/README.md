# تشغيل المرشد الأكاديمي

الواجهة ترسل الطلبات إلى Flask على المنفذ 5000. يتصل Flask بخدمة RAG على المنفذ 8001. خدمة RAG تدير الفهرس في ChromaDB وتستخدم Gemini للتضمين والتوليد.

## الإعداد من PowerShell

### ترحيل الفهرس الحالي مرة واحدة

أوقفي **كل** عمليات RAG التي تستخدم مجلد الفهرس، بما فيها أي نسخة شغالة على 8000 وأي نسخة على 8001. من مجلد الخدمة شغّلي:

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag\rag-service')
& ..\.venv\Scripts\python.exe -B migrate_universities.py
```

يعمل الأمر على إنشاء نسخة احتياطية كاملة للفهرس قبل تعديل البيانات الوصفية. يربط الملفين الموثّقين حسب الاسم وبصمة المحتوى، ويحتفظ بالمقاطع والمتجهات ومعرّفات الوثائق. المقاطع ذات الملكية غير المؤكدة تبقى خارج نتائج المحادثة. راجعي الأعداد المطبوعة قبل تشغيل الخدمة. استخدمي عملية RAG واحدة للفهرس.

### الإعداد

من مجلد المشروع، أنشئي البيئة وانسخي أمثلة الإعداد إذا كانت الملفات غير موجودة.

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag')
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r rag-service\requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path rag-service\.env)) { Copy-Item rag-service\.env.example rag-service\.env }
```

في `.env` بمجلد المشروع، اضبطي `RAG_SERVICE_URL=http://127.0.0.1:8001` وضعي قيمة قوية لـ`RAG_ADMIN_TOKEN`. يستخدمها Flask وخدمة RAG لتأمين الرفع. الرمز الفارغ يعطّل الرفع. في `rag-service/.env`، ضعي مفتاح `GEMINI_API_KEY` واضبطي `GEMINI_LLM_MODEL` على النموذج المستخدم في بيئة فريقك. اتركي المفاتيح في ملفات الإعداد المحلية.

افتحي ثلاث نوافذ PowerShell:

**خدمة RAG**

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag\rag-service')
& ..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
```

شغّلي الأمر من مجلد `rag-service` لأن مكان فهرس ChromaDB نسبي لمجلد التشغيل.

**Flask**

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag')
& .\.venv\Scripts\python.exe -m flask --app backend.app run --host 127.0.0.1 --port 5000
```

**React**

```powershell
Set-Location (Join-Path ([Environment]::GetFolderPath('Desktop')) 'IEEE\Bethlehem_Rag\frontend')
npm.cmd ci
$env:VITE_API_BASE_URL = 'http://localhost:5000'
$env:VITE_USE_MOCK_API = 'false'
npm.cmd run dev -- --port 5175
```

افتحي `http://localhost:5175`. يدعم إعداد CORS الافتراضي 5173 و5175. في صفحة الإدارة أدخلي قيمة الرمز من ملف الإعداد المشترك. أضيفي الجامعة باسم ومعرّف ثابت، ثم اختاريها عند رفع الوثيقة. حد الرفع 10 ميغابايت. صفحة المستندات تعرض بيانات الفهرس العام. هذه الخدمة مخصصة للوثائق الأكاديمية العامة لأن المحادثة تعرض مقتطفات للطلاب.

## إدارة الجامعات

يخزن RAG دليل الجامعات في `chroma_db/universities.sqlite3` ويخزن `university_id` مع كل مقطع في ChromaDB. البحث يمرر معرّف الجامعة إلى فلتر ChromaDB. Flask يطبق مصادقة التعديلات ويمررها للخدمة الداخلية، التي تتحقق من الرمز أيضاً.

| المسار | العقد |
| --- | --- |
| `GET /universities` | `{universities: [{id, name}]}` |
| `POST /universities` | رمز الإدارة وJSON بالشكل `{id, name}`. يرجع 201 عند الإنشاء أو 409 إذا استُخدم المعرّف. |
| `POST /documents` | رمز الإدارة وحقلا multipart `file` و`university_id`. يرجع `{document_id, filename, status, university_id}`. الطلب القديم بدون معرّف يدعم تأكيد ملف مطابق موجود إذا كانت نتيجة المطابقة غير ملتبسة. |
| `GET /documents` | `?university_id=birzeit` اختياري. يرجع قائمة الوثائق مع معرّف الجامعة حيث يتوفر. |

## عقد المحادثة

`POST /chat` يستقبل `university` بقيمة معرّف جامعة مسجلة، و`question`، و`top_k` الاختياري من 1 إلى 10. النتيجة `{answer, grounded, sources}`. المراجع تحمل `citation_id` و`filename` و`page` و`excerpt`. للملفات النصية تكون الصفحة فارغة. القيمة `grounded: false` تعرض ردّ عدم كفاية المعلومات من خدمة RAG.

للتحقق السريع:

```powershell
Invoke-RestMethod http://localhost:5000/health
$body = @{ university = 'birzeit'; question = 'ما شروط الانسحاب؟' } | ConvertTo-Json
Invoke-RestMethod http://localhost:5000/chat -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
```
