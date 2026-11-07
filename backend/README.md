# Flask API

ابدئي من [README الرئيسي](../README.md) لمعرفة هيكل المشروع، وإعداد المتغيرات، وترحيل الفهرس، وتشغيل الخدمات الثلاث، وعقد API.

يعمل Flask كبوابة بين React وRAG. يقرأ `RAG_SERVICE_URL` و`RAG_CORS_ORIGINS` و`RAG_ADMIN_TOKEN` من ملف `.env` في جذر المشروع. يتحقق Flask وخدمة RAG من رمز الإدارة عند إنشاء الجامعات ورفع الملفات.

بعد تثبيت التبعيات وتشغيل RAG، شغّلي من جذر المشروع:

```powershell
& .\.venv\Scripts\python.exe -m flask --app backend.app run --host 127.0.0.1 --port 5000
```

استخدمي [مسار الصحة](http://127.0.0.1:5000/health) لفحص الاتصال مع RAG، ثم اتبعي خطوات «أول تجربة فعلية» في README الرئيسي للتحقق من الفهرسة والمحادثة.
