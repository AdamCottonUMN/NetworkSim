const PALETTE_ITEMS = [
  {
    type: 'load_balancer',
    label: 'Load Balancer',
    abbr: 'LB',
    color: '#d97706',
    desc: 'Distributes incoming traffic',
  },
  {
    type: 'app_server',
    label: 'App Server',
    abbr: 'APP',
    color: '#2563eb',
    desc: 'Processes requests',
  },
  {
    type: 'database',
    label: 'Database',
    abbr: 'DB',
    color: '#16a34a',
    desc: 'Persistent storage layer',
  },
  {
    type: 'cache',
    label: 'Cache',
    abbr: 'CACHE',
    color: '#7c3aed',
    desc: 'Fast in-memory lookup',
  },
  {
    type: 'cdn',
    label: 'CDN',
    abbr: 'CDN',
    color: '#0d9488',
    desc: 'Edge servers, static assets',
  },
  {
    type: 'payment_gateway',
    label: 'Payment Gateway',
    abbr: 'PAY',
    color: '#db2777',
    desc: 'External payment API',
  },
  {
    type: 'message_queue',
    label: 'Message Queue',
    abbr: 'QUEUE',
    color: '#4f46e5',
    desc: 'Async job processing',
  },
] as const

function PaletteItem({ item }: { item: (typeof PALETTE_ITEMS)[number] }) {
  function onDragStart(e: React.DragEvent) {
    e.dataTransfer.setData('application/reactflow', item.type)
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="flex items-center gap-3 p-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-500 cursor-grab active:cursor-grabbing transition-colors select-none"
    >
      <span
        className="text-white text-xs font-bold px-2 py-0.5 rounded shrink-0"
        style={{ background: item.color }}
      >
        {item.abbr}
      </span>
      <div className="min-w-0">
        <div className="text-slate-200 text-xs font-semibold">{item.label}</div>
        <div className="text-slate-500 text-xs truncate">{item.desc}</div>
      </div>
    </div>
  )
}

export function NodePalette() {
  return (
    <div className="w-52 shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-800">
        <p className="text-slate-400 text-xs font-semibold uppercase tracking-widest">
          Components
        </p>
      </div>

      <div className="p-3 flex flex-col gap-2 overflow-y-auto flex-1">
        {PALETTE_ITEMS.map((item) => (
          <PaletteItem key={item.type} item={item} />
        ))}
      </div>

      <div className="px-4 py-3 border-t border-slate-800">
        <p className="text-slate-600 text-xs text-center">Drag onto canvas to add</p>
      </div>
    </div>
  )
}
