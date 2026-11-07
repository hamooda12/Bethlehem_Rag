import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, RefreshCw, Upload } from 'lucide-react'
import { ErrorMessage, Loading } from '../components/Feedback.jsx'
import { createUniversity, getDocuments, getHealth, getUniversities, uploadDocument } from '../services/api.js'

function useResource(load) {
  const [state, setState] = useState({ loading: true })
  const sequence = useRef(0)
  const refresh = useCallback(async () => {
    const id = ++sequence.current
    setState({ loading: true })
    try {
      const data = await load()
      if (id === sequence.current) setState({ data })
    } catch (error) {
      if (id === sequence.current) setState({ error: error.message })
    }
  }, [load])
  useEffect(() => {
    refresh()
    return () => { sequence.current++ }
  }, [refresh])
  return { ...state, refresh }
}

function DocumentList({ resource }) {
  const { loading, error, data, refresh } = resource
  const documents = data?.documents
  return <section className="panel space-y-4" aria-labelledby="document-heading">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 id="document-heading" className="text-xl font-bold">المستندات المفهرسة</h2>
      <button className="secondary" disabled={loading} onClick={refresh}>
        <RefreshCw size={16} aria-hidden="true" /> تحديث
      </button>
    </div>
    {loading && <Loading>جارٍ تحميل المستندات…</Loading>}
    {error && <ErrorMessage>{error}</ErrorMessage>}
    {documents && <>
      <p className="connection-label">عدد المستندات <strong>{documents.length}</strong></p>
      {documents.length === 0 ? <p className="chat-empty">لا توجد مستندات متاحة حالياً.</p> :
        <ul className="divide-y divide-slate-200">{documents.map(document =>
          <li key={document.document_id} className="flex items-start gap-3 py-3">
            <FileText size={20} className="mt-1 shrink-0 text-blue-700" aria-hidden="true" />
            <div className="min-w-0">
              <bdi className="break-all font-semibold">{document.filename}</bdi>
              <p className="text-sm text-slate-600">عدد المقاطع المفهرسة {document.chunks}</p>
            </div>
          </li>
        )}</ul>}
    </>}
  </section>
}

function AdminAuthForm({ token, onChange }) {
  return <div className="space-y-1">
    <label htmlFor="admin-token" className="block font-semibold">رمز الإدارة</label>
    <input id="admin-token" type="password" autoComplete="off" value={token}
      onChange={event => onChange(event.target.value)} />
  </div>
}

function UniversityCreate({ token, onCreated }) {
  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const pending = useRef(false)

  async function submit(event) {
    event.preventDefault()
    if (pending.current || !token.trim() || !name.trim()) return
    pending.current = true
    setBusy(true)
    setFeedback(null)
    try {
      await createUniversity({ id: id.trim(), name: name.trim() }, token.trim())
      setId('')
      setName('')
      setFeedback({ message: 'تمت إضافة الجامعة.' })
      onCreated()
    } catch (error) {
      setFeedback({ error: error.message })
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return <section className="panel space-y-3">
    <h2 className="text-xl font-bold">إضافة جامعة</h2>
    <form className="upload-form space-y-3" onSubmit={submit}>
      <label htmlFor="university-name" className="block font-semibold">اسم الجامعة</label>
      <input id="university-name" value={name} onChange={event => setName(event.target.value)} maxLength={120} required />
      <label htmlFor="university-id" className="block font-semibold">معرّف الجامعة</label>
      <input id="university-id" dir="ltr" placeholder="najah" value={id}
        onChange={event => setId(event.target.value)} pattern="[a-z0-9](?:[a-z0-9]|-){0,63}" maxLength={64} required />
      <p className="text-sm text-slate-600">استخدمي أحرفاً إنجليزية صغيرة أو أرقاماً أو شرطات.</p>
      <button className="primary" disabled={busy || !token.trim() || !id || !name.trim()}>إضافة الجامعة</button>
      {busy && <Loading>جارٍ إضافة الجامعة…</Loading>}
      {feedback?.error && <ErrorMessage>{feedback.error}</ErrorMessage>}
      {feedback?.message && <p role="status">{feedback.message}</p>}
    </form>
  </section>
}

function DocumentUpload({ token, catalog, onIndexed }) {
  const [university, setUniversity] = useState('')
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const pending = useRef(false)
  const picker = useRef(null)

  async function submit(event) {
    event.preventDefault()
    if (pending.current || !file || !token.trim() || !university) return
    const error = !/\.(pdf|txt)$/i.test(file.name) ? 'صيغة الملف غير مدعومة. اختر PDF أو TXT.'
      : file.size > 10 * 1024 * 1024 ? 'الملف أكبر من الحجم المسموح (10 ميغابايت).'
      : !file.size ? 'الملف فارغ.' : null
    if (error) {
      setFeedback({ error })
      return
    }
    pending.current = true
    setBusy(true)
    setFeedback(null)
    try {
      const result = await uploadDocument(file, token.trim(), university)
      if (result.status === 'indexed') {
        setFeedback({ message: 'تمت فهرسة المستند بنجاح.' })
      } else if (result.status === 'already_indexed') {
        setFeedback({ message: 'هذا المستند مفهرس مسبقاً.' })
      } else {
        throw new Error('لم يؤكد الخادم حالة فهرسة المستند.')
      }
      setFile(null)
      picker.current.value = ''
      onIndexed()
    } catch (error) {
      setFeedback({ error: error.message })
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return <section className="panel space-y-3">
    <h2 className="text-xl font-bold">رفع مستند أكاديمي</h2>
    <p className="text-sm text-slate-600">اختاري الجامعة التي تتبع لها الوثيقة حتى تظهر في نتائج البحث الخاصة بها.</p>
    <form className="upload-form space-y-3" onSubmit={submit}>
      <label htmlFor="document-university" className="block font-semibold">جامعة المستند</label>
      <select id="document-university" className="university-select" value={university}
        onChange={event => setUniversity(event.target.value)} disabled={busy || catalog.loading} required>
        <option value="">اختاري الجامعة</option>
        {catalog.data?.universities.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select>
      <label htmlFor="document" className="block font-semibold">المستند (PDF أو TXT، حتى 10 ميغابايت)</label>
      <input ref={picker} id="document" type="file" accept=".pdf,.txt" disabled={busy} required
        onChange={event => { setFile(event.target.files[0] ?? null); setFeedback(null) }} />
      {file && <p className="break-all text-sm text-slate-700"><bdi>{file.name}</bdi> · {new Intl.NumberFormat('ar').format(file.size)} بايت</p>}
      <button className="primary" disabled={!file || !token.trim() || !university || busy}><Upload size={16} aria-hidden="true" /> رفع المستند</button>
      {busy && <Loading>جارٍ رفع المستند وفهرسته…</Loading>}
      {feedback?.error && <ErrorMessage>{feedback.error}</ErrorMessage>}
      {feedback?.message && <p role="status" className="rounded-lg bg-blue-50 p-3">{feedback.message}</p>}
    </form>
  </section>
}

export function Documents() {
  const documents = useResource(getDocuments)
  return <>
    <h1 className="text-3xl font-extrabold text-[#12355B]">الوثائق الأكاديمية</h1>
    <DocumentList resource={documents} />
  </>
}

export function Admin() {
  const documents = useResource(getDocuments)
  const health = useResource(getHealth)
  const catalog = useResource(getUniversities)
  const [token, setToken] = useState('')
  return <>
    <h1 className="text-3xl font-extrabold text-[#12355B]">إدارة الوثائق الأكاديمية</h1>
    <section className="panel space-y-2">
      <h2 className="text-xl font-bold">حالة الخادم</h2>
      {health.loading && <Loading>جارٍ التحقق من الاتصال…</Loading>}
      {health.error && <ErrorMessage>{health.error}</ErrorMessage>}
      {health.data && <p>{health.data.status === 'ok' ? 'متصل' : 'الخدمة غير متاحة'} · المقاطع المفهرسة <strong>{health.data.indexed_chunks}</strong></p>}
      <button className="secondary" disabled={health.loading} onClick={health.refresh}>إعادة التحقق</button>
    </section>
    <section className="panel space-y-2">
      <AdminAuthForm token={token} onChange={setToken} />
      <p className="text-sm text-slate-600">الرمز مطلوب لإضافة الجامعات ورفع المستندات.</p>
      {catalog.loading && <Loading>جارٍ تحميل الجامعات…</Loading>}
      {catalog.error && <>
        <ErrorMessage>{catalog.error}</ErrorMessage>
        <button className="secondary" onClick={catalog.refresh}>إعادة تحميل الجامعات</button>
      </>}
    </section>
    <UniversityCreate token={token} onCreated={catalog.refresh} />
    <DocumentUpload token={token} catalog={catalog} onIndexed={() => { documents.refresh(); health.refresh() }} />
    <DocumentList resource={documents} />
  </>
}
