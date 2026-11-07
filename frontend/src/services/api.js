const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000').replace(/\/$/, '')
export const mockEnabled = import.meta.env.DEV && import.meta.env.VITE_USE_MOCK_API === 'true'

const statusMessages = {
  401: 'رمز الإدارة غير صحيح أو غير موجود.',
  409: 'معرّف الجامعة مستخدم مسبقاً.',
  403: 'غير مصرح برفع المستند.',
  413: 'الملف أكبر من الحجم المسموح (10 ميغابايت).',
  415: 'صيغة الملف غير مدعومة. اختر PDF أو TXT.',
  429: 'وصلت خدمة المرشد إلى حد الطلبات. حاولي مرة أخرى لاحقاً.',
  503: 'خدمة المرشد غير متاحة حالياً.',
  504: 'انتهت مهلة انتظار خدمة المرشد.',
}

async function request(path, options = {}, timeout = 20000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetch(base + path, { ...options, signal: controller.signal })
    const payload = await response.json().catch(error => {
      if (error.name === 'AbortError') throw error
      return undefined
    })
    if (!response.ok) {
      const detail = payload?.detail
      const validation = Array.isArray(detail) ? detail.map(item => item.loc?.at(-1)) : []
      let message = detail === 'Document upload is disabled'
        ? 'رفع المستندات معطّل حتى يتم ضبط رمز الإدارة على الخادم.'
        : statusMessages[response.status]
      if (response.status === 422) {
        if (validation.includes('top_k') || detail === 'Invalid top_k') message = 'عدد المقاطع يجب أن يكون بين 1 و10.'
        else if (validation.includes('university') || detail === 'Unsupported university') message = 'الرجاء اختيار جامعة مدعومة.'
        else if (validation.includes('question') || detail === 'Question cannot be empty') message = 'الرجاء إدخال السؤال.'
        else if (path === '/universities') message = 'تحققي من اسم الجامعة ومعرّفها.'
        else if (detail === 'Empty file') message = 'الملف فارغ.'
        else message = path === '/chat' ? 'تعذر معالجة السؤال.' : 'تعذرت قراءة محتوى المستند أو فهرسته.'
      }
      if (!message) message = path === '/chat' ? 'تعذر توليد الإجابة.' : 'تعذر إكمال العملية على الخادم.'
      throw new Error(message)
    }
    if (payload === undefined) throw new Error('أعاد الخادم استجابة غير قابلة للقراءة.')
    return payload
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('انتهت مهلة الاتصال بالخادم.')
    if (error instanceof TypeError) throw new Error('تعذر الاتصال بالخادم.')
    throw error
  } finally {
    clearTimeout(timer)
  }
}

const real = {
  getHealth: () => request('/health'),
  getDocuments: university => request(university ? '/documents?' + new URLSearchParams({ university_id: university }) : '/documents'),
  getUniversities: () => request('/universities'),
  createUniversity: (data, token) => request('/universities', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
    body: JSON.stringify(data),
  }),
  askQuestion: (question, university, top_k) => request('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, university, top_k }),
  }, 90000),
  uploadDocument: (file, token, university) => {
    const body = new FormData()
    body.append('file', file)
    body.append('university_id', university)
    return request('/documents', {
      method: 'POST', headers: { Authorization: 'Bearer ' + token }, body,
    }, 180000)
  },
}

const mock = mockEnabled ? import('./mock.js') : null
export const getHealth = async () => (mock ? (await mock).api : real).getHealth()
export const getDocuments = async university => (mock ? (await mock).api : real).getDocuments(university)
export const getUniversities = async () => (mock ? (await mock).api : real).getUniversities()
export const createUniversity = async (data, token) => (mock ? (await mock).api : real).createUniversity(data, token)
export const uploadDocument = async (file, token, university) => (mock ? (await mock).api : real).uploadDocument(file, token, university)

export async function askQuestion(question, university, topK = 4) {
  if (!university) throw new Error('الرجاء اختيار جامعة مدعومة.')
  if (!question.trim()) throw new Error('الرجاء إدخال السؤال.')
  if (!Number.isInteger(topK) || topK < 1 || topK > 10) throw new Error('عدد المقاطع يجب أن يكون بين 1 و10.')
  const result = await (mock ? (await mock).api : real).askQuestion(question.trim(), university, topK)
  if (typeof result?.answer !== 'string' || !result.answer.trim() || typeof result.grounded !== 'boolean') {
    throw new Error('صيغة إجابة خدمة المرشد غير مدعومة.')
  }
  const sources = result.grounded && Array.isArray(result.sources) ? result.sources.filter(source =>
    typeof source?.filename === 'string' && source.filename.trim()
  ) : []
  return { answer: result.answer, grounded: result.grounded, sources }
}
