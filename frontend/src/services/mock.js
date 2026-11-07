const documents = []
const universities = [
  { id: 'birzeit', name: 'جامعة بيرزيت' },
  { id: 'aaup', name: 'الجامعة العربية الأمريكية' },
]
const scenario = import.meta.env.VITE_MOCK_SCENARIO
async function wait() {
  await new Promise(resolve => setTimeout(resolve, 450))
  if (scenario === 'offline') throw new Error('تعذر الاتصال بالخادم التجريبي.')
}

export const api = {
  async getHealth() {
    await wait()
    return { status: 'ok', indexed_chunks: documents.length }
  },
  async getDocuments(university) {
    await wait()
    return { documents: documents.filter(doc => !university || doc.university_id === university) }
  },
  async getUniversities() {
    await wait()
    return { universities: [...universities] }
  },
  async createUniversity(data, token) {
    await wait()
    if (!token) throw new Error('أدخل رمز الإدارة.')
    if (universities.some(university => university.id === data.id)) throw new Error('معرّف الجامعة مستخدم مسبقاً.')
    universities.push(data)
    return data
  },
  async askQuestion() {
    await wait()
    if (scenario === 'generation') throw new Error('تعذر توليد الإجابة التجريبية.')
    if (scenario === 'no-evidence') return { answer: 'لا توجد معلومات كافية في مستندات الجامعة المختارة للإجابة عن السؤال.', grounded: false, sources: [] }
    return { answer: 'هذه إجابة تجريبية لاستخدام الواجهة أثناء التطوير.', grounded: true, sources: [] }
  },
  async uploadDocument(file, token, university) {
    await wait()
    if (!token) throw new Error('أدخل رمز الإدارة لتجربة الرفع.')
    if (!/\.(pdf|txt)$/i.test(file.name)) throw new Error('صيغة الملف غير مدعومة.')
    if (file.size > 10 * 1024 * 1024) throw new Error('الملف أكبر من الحجم المسموح.')
    if (!file.size) throw new Error('الملف فارغ.')
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer())
    const id = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
    if (documents.some(document => document.document_id === university + ':' + id)) return { status: 'already_indexed' }
    documents.push({ document_id: university + ':' + id, filename: file.name, chunks: 1, university_id: university })
    return { status: 'indexed' }
  },
}
