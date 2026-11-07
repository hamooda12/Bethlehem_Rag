import { useEffect, useRef, useState } from 'react'
import { ArrowUpLeft, BookOpen, GraduationCap, MessageCircle, Send, Trash2 } from 'lucide-react'
import { ErrorMessage, Loading } from '../components/Feedback.jsx'
import { askQuestion, getDocuments, getHealth, getUniversities } from '../services/api.js'

const suggestions = [
  'شو شروط الانسحاب من مادة؟',
  'كيف بحسب معدلي التراكمي؟',
  'كم ساعة بقدر أسجل بالفصل؟',
  'شو بصير إذا رسبت بمادة؟',
  'ما متطلبات التخرج؟',
]

function inlineAnswer(text) {
  return text.split(/(\*\*[^*\n]+\*\*|\[S\d+(?:\s*[,،]\s*S\d+)*\])/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (/^\[S\d/.test(part)) return <bdi key={index} className="citation-tag">{part}</bdi>
    return part
  })
}

function Answer({ text }) {
  const blocks = []
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue
    const item = line.match(/^\s*([0-9٠-٩۰-۹]+)[.)]\s+(.+)$/)
    if (!item) {
      blocks.push({ text: line })
    } else {
      const digits = item[1].replace(/[٠-٩۰-۹]/g, digit => '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹'.indexOf(digit) % 10)
      if (!blocks.at(-1)?.items) blocks.push({ items: [] })
      blocks.at(-1).items.push({ number: Number(digits), text: item[2] })
    }
  }
  return <div className="answer-text">{blocks.map((block, index) => block.items
    ? <ol key={index}>{block.items.map((item, number) => <li key={number} value={item.number}>{inlineAnswer(item.text)}</li>)}</ol>
    : <p key={index}>{inlineAnswer(block.text)}</p>)}</div>
}

function SourceCard({ source }) {
  const excerpt = typeof source.excerpt === 'string' ? source.excerpt : ''
  return <li className="source-card">
    <div className="source-heading">
      {source.citation_id && <bdi className="citation-tag">[{source.citation_id}]</bdi>}
      <bdi className="font-bold">{source.filename}</bdi>
      {Number.isInteger(source.page) && source.page > 0 && <span className="source-page">الصفحة {source.page}</span>}
    </div>
    {excerpt.length > 160 ? <details className="source-excerpt">
      <summary>
        <span className="excerpt-preview">{excerpt.slice(0, 160).trimEnd()}…</span>
        <span className="excerpt-expand">عرض المقتطف كاملاً</span>
        <span className="excerpt-collapse">طيّ المقتطف</span>
      </summary>
      <blockquote>{excerpt}</blockquote>
    </details> : excerpt && <blockquote className="source-excerpt">{excerpt}</blockquote>}
  </li>
}

function ChatMessage({ turn, onRetry, busy }) {
  return <li className="chat-turn">
    <p className="student-message whitespace-pre-wrap">
      <strong className="block text-sm">أنت · {turn.universityName}</strong>{turn.question}
    </p>
    <div className="assistant-message">
      <strong className="assistant-label"><GraduationCap size={18} aria-hidden="true" /> المرشد الأكاديمي</strong>
      {turn.error ? <>
        <ErrorMessage>{turn.error}</ErrorMessage>
        <button className="secondary mt-2" disabled={busy} onClick={onRetry}>إعادة المحاولة</button>
      </> : turn.result ? <>
        <Answer text={turn.result.answer} />
        {turn.result.grounded && (turn.result.sources.length > 0 ? <>
          <h2 className="source-title"><BookOpen size={17} aria-hidden="true" /> المصادر <span>{turn.result.sources.length}</span></h2>
          <ul className="mt-2 grid gap-2">{turn.result.sources.map((source, index) =>
            <SourceCard key={index} source={source} />
          )}</ul>
        </> : <p className="mt-2 text-sm text-slate-600">المراجع غير متوفرة لهذه الإجابة.</p>)}
      </> : <Loading>جارٍ إعداد الإجابة، قد يستغرق الرد لحظات…</Loading>}
    </div>
  </li>
}

function ChatInput({ value, onChange, disabled, onSend }) {
  return <form className="chat-composer" onSubmit={event => { event.preventDefault(); onSend(value) }}>
    <label htmlFor="question" className="block font-semibold">سؤالك الأكاديمي</label>
    <textarea id="question" rows={3} value={value} onChange={event => onChange(event.target.value)}
      placeholder="اكتب سؤالك الأكاديمي هنا..." onKeyDown={event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
          event.preventDefault()
          onSend(value)
        }
      }} />
    <div className="composer-actions"><span>اضغطي <kbd>Enter</kbd> للإرسال</span><button className="primary" disabled={disabled || !value.trim()}><Send size={16} aria-hidden="true" /> إرسال</button></div>
  </form>
}

export default function Chat() {
  const [turns, setTurns] = useState([])
  const [question, setQuestion] = useState('')
  const [university, setUniversity] = useState('')
  const [catalog, setCatalog] = useState({ loading: true })
  const [availability, setAvailability] = useState(null)
  const [busy, setBusy] = useState(false)
  const [connection, setConnection] = useState('جارٍ التحقق من اتصال الخادم…')
  const tail = useRef(null)
  const pending = useRef(false)
  const nextId = useRef(0)

  async function loadUniversities() {
    setCatalog({ loading: true })
    try {
      setCatalog(await getUniversities())
    } catch (error) {
      setCatalog({ error: error.message })
    }
  }

  useEffect(() => { loadUniversities() }, [])
  useEffect(() => {
    if (!university) return
    let active = true
    getDocuments(university).then(({ documents }) => {
      if (active) setAvailability({ university, empty: documents.length === 0 })
    }).catch(() => { if (active) setAvailability(null) })
    return () => { active = false }
  }, [university])

  useEffect(() => {
    getHealth().then(health => setConnection(health.status === 'ok'
      ? (health.indexed_chunks === 0 ? 'الخادم متصل. لا توجد مستندات مفهرسة حالياً.' : 'الخادم متصل.')
      : 'خدمة المرشد غير متاحة حالياً.'))
      .catch(() => setConnection('تعذر الاتصال بالخادم.'))
  }, [])
  useEffect(() => {
    if (turns.length) tail.current?.scrollIntoView({ block: 'nearest' })
  }, [turns])

  async function send(value, existingTurn) {
    const text = value.trim()
    const selectedUniversity = existingTurn?.university ?? university
    if (!text || !selectedUniversity || pending.current) return
    pending.current = true
    setBusy(true)
    const id = existingTurn?.id ?? nextId.current++
    const universityName = existingTurn?.universityName
      ?? catalog.universities?.find(item => item.id === selectedUniversity)?.name
      ?? selectedUniversity
    const turn = { id, question: text, university: selectedUniversity, universityName }
    const update = fields => setTurns(previous =>
      previous.map(item => item.id === id ? { ...turn, ...fields } : item)
    )
    if (!existingTurn) {
      setTurns(previous => [...previous, turn])
      setQuestion('')
    } else update({})
    try {
      update({ result: await askQuestion(text, selectedUniversity) })
    } catch (error) {
      update({ error: error.message })
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return <>
    <section className="chat-hero">
      <span className="hero-label"><GraduationCap size={17} aria-hidden="true" /> مساعدك الجامعي</span>
      <h1 className="text-2xl font-extrabold sm:text-3xl">مرحباً بك في المرشد الأكاديمي الذكي</h1>
      <p className="hero-copy">اسأل عن الأنظمة الجامعية والخطط الدراسية واحصل على إجابات مستندة إلى الوثائق الأكاديمية.</p>
      <p className="hero-note">تعتمد الإجابات على المستندات المفهرسة للجامعة التي تختارينها.</p>
    </section>
    <section className="panel chat-panel" aria-label="المحادثة">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p role="status" className="connection-label">{connection}</p>
        {turns.length > 0 && <button className="secondary" disabled={busy} onClick={() => { setTurns([]); setQuestion('') }}>
          <Trash2 size={16} aria-hidden="true" /> مسح المحادثة
        </button>}
      </div>
      <div className="university-field">
        <label htmlFor="university" className="block font-semibold">الجامعة</label>
        <select id="university" className="university-select"
          value={university} onChange={event => { setAvailability(null); setUniversity(event.target.value) }} disabled={busy || !catalog.universities?.length}>
          <option value="">{catalog.loading ? 'جارٍ تحميل الجامعات…' : 'اختاري الجامعة'}</option>
          {catalog.universities?.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
        </select>
        {catalog.error && <>
          <ErrorMessage>{catalog.error}</ErrorMessage>
          <button className="secondary" onClick={loadUniversities}>إعادة تحميل الجامعات</button>
        </>}
        {availability?.university === university && availability.empty &&
          <p role="status" className="text-sm text-slate-700">لا توجد مستندات مفهرسة لهذه الجامعة حالياً.</p>}
      </div>
      {turns.length === 0 && <div className="chat-empty">
        <h2><MessageCircle size={18} aria-hidden="true" /> أسئلة مقترحة</h2>
        <p>{university ? 'اختاري سؤالاً أو اكتبي سؤالك بالأسفل.' : 'اختاري الجامعة لتبدئي المحادثة.'}</p>
        <div className="flex flex-wrap gap-2">{suggestions.map(item =>
          <button key={item} className="secondary suggestion" onClick={() => send(item)} disabled={busy || !university}>{item}<ArrowUpLeft size={14} aria-hidden="true" /></button>
        )}</div>
      </div>}
      <div role="log" aria-label="رسائل المحادثة" className="chat-log">
        <ol className="space-y-3">{turns.map(turn =>
          <ChatMessage key={turn.id} turn={turn} busy={busy} onRetry={() => send(turn.question, turn)} />
        )}</ol>
        <div ref={tail} />
      </div>
      <ChatInput value={question} onChange={setQuestion} disabled={busy || !university} onSend={send} />
    </section>
  </>
}
