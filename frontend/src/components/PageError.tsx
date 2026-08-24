import { AlertTriangle } from 'lucide-react'

interface PageErrorProps {
  error: unknown
  resetErrorBoundary: () => void
}

export default function PageError({ error, resetErrorBoundary }: PageErrorProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <AlertTriangle className="h-8 w-8 text-amber-400" />
      <h2 className="text-sm font-bold text-text-primary">Algo salió mal</h2>
      <p className="max-w-sm text-xs text-text-muted">
        {error instanceof Error
          ? error.message
          : 'Error inesperado al renderizar esta página.'}
      </p>
      <button
        onClick={resetErrorBoundary}
        className="mt-1 rounded-lg border border-purple-500/30 bg-purple-500/10 px-6 py-2.5 text-xs font-bold text-purple-400 transition-colors hover:bg-purple-500/20"
      >
        Reintentar
      </button>
    </div>
  )
}
