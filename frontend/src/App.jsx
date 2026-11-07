import { GraduationCap } from 'lucide-react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import Chat from './pages/Chat.jsx'
import { Admin, Documents } from './pages/Documents.jsx'
import { mockEnabled } from './services/api.js'

function Navbar() {
  return <header className="site-header">
    <div className="frame flex flex-wrap items-center justify-between gap-3 py-4">
      <Link to="/" className="brand">
        <span className="brand-mark"><GraduationCap size={22} aria-hidden="true" /></span> المرشد الأكاديمي الذكي
      </Link>
      <nav aria-label="التنقل الرئيسي" className="site-nav">
        <NavLink end to="/">المحادثة</NavLink>
        <NavLink to="/documents">المستندات</NavLink>
        <NavLink to="/admin">الإدارة</NavLink>
      </nav>
    </div>
  </header>
}

export default function App() {
  return <>
    <Navbar />
    <main className="frame space-y-5 py-7 sm:py-10">
      {mockEnabled && <p className="rounded-lg bg-amber-100 p-3 text-amber-950" role="status">
        وضع المحاكاة للتطوير. البيانات والإجابات تجريبية.
      </p>}
      <Routes>
        <Route path="/" element={<Chat />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<p>الصفحة غير موجودة. <Link className="underline" to="/">العودة للمحادثة</Link></p>} />
      </Routes>
    </main>
  </>
}
