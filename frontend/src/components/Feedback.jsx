import { LoaderCircle } from 'lucide-react'

export function Loading({ children }) {
  return <p role="status" className="flex items-center gap-2 text-slate-700">
    <LoaderCircle size={18} aria-hidden="true" className="motion-safe:animate-spin" /> {children}
  </p>
}

export function ErrorMessage({ children }) {
  return <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-800">{children}</p>
}
