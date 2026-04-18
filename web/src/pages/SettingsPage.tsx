import { useState } from 'react'
import { Moon, Globe, Bell, Shield, Database, Palette } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { hermesApi } from '@/services/api'
import toast from 'react-hot-toast'

const settingsGroups = [
  {
    title: '外观',
    icon: Palette,
    items: [
      { key: 'theme', label: '主题', type: 'select', options: ['dark', 'light', 'auto'] },
      { key: 'fontSize', label: '字体大小', type: 'select', options: ['small', 'medium', 'large'] },
    ],
  },
  {
    title: '语言',
    icon: Globe,
    items: [
      { key: 'language', label: '界面语言', type: 'select', options: ['zh-CN', 'en-US'] },
      { key: 'translation', label: '翻译服务', type: 'switch', default: true },
    ],
  },
  {
    title: '通知',
    icon: Bell,
    items: [
      { key: 'pushEnabled', label: '推送通知', type: 'switch', default: true },
      { key: 'soundEnabled', label: '声音提醒', type: 'switch', default: false },
    ],
  },
  {
    title: '安全',
    icon: Shield,
    items: [
      { key: 'autoLock', label: '自动锁定', type: 'switch', default: false },
      { key: 'encryptHistory', label: '加密历史记录', type: 'switch', default: true },
    ],
  },
  {
    title: '数据',
    icon: Database,
    items: [
      { key: 'autoSync', label: '自动同步', type: 'switch', default: true },
      { key: 'cacheSize', label: '缓存大小', type: 'text', value: '256 MB' },
    ],
  },
]

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, any>>({
    theme: 'dark',
    fontSize: 'medium',
    language: 'zh-CN',
    translation: true,
    pushEnabled: true,
    soundEnabled: false,
    autoLock: false,
    encryptHistory: true,
    autoSync: true,
    cacheSize: '256 MB',
  })

  const { data: statusData } = useQuery({
    queryKey: ['system-status'],
    queryFn: () => hermesApi.getStatus(),
  })

  const handleToggle = (key: string) => {
    setSettings((prev) => ({
      ...prev,
      [key]: !prev[key],
    }))
    toast.success('设置已更新')
  }

  const handleSelect = (key: string, value: string) => {
    setSettings((prev) => ({
      ...prev,
      [key]: value,
    }))
    toast.success('设置已更新')
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="h-14 px-4 flex items-center border-b border-border bg-surface">
        <h1 className="text-lg font-semibold">设置</h1>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* System Status */}
        <div className="bg-surface rounded-xl p-4 border border-border">
          <h2 className="text-sm font-medium mb-3">系统状态</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-surface-light rounded-lg p-3">
              <div className="text-xs text-text-secondary">连接节点</div>
              <div className="text-lg font-semibold">{statusData?.data?.connected_nodes || 0}</div>
            </div>
            <div className="bg-surface-light rounded-lg p-3">
              <div className="text-xs text-text-secondary">活跃路由</div>
              <div className="text-lg font-semibold">{statusData?.data?.active_routes || 0}</div>
            </div>
            <div className="bg-surface-light rounded-lg p-3">
              <div className="text-xs text-text-secondary">网络质量</div>
              <div className="text-lg font-semibold">{statusData?.data?.network_quality || '良好'}</div>
            </div>
            <div className="bg-surface-light rounded-lg p-3">
              <div className="text-xs text-text-secondary">版本</div>
              <div className="text-lg font-semibold">v2.0</div>
            </div>
          </div>
        </div>

        {/* Settings Groups */}
        {settingsGroups.map((group) => (
          <div key={group.title} className="bg-surface rounded-xl p-4 border border-border">
            <div className="flex items-center space-x-2 mb-4">
              <group.icon size={18} className="text-primary" />
              <h2 className="text-sm font-medium">{group.title}</h2>
            </div>

            <div className="space-y-3">
              {group.items.map((item) => (
                <div
                  key={item.key}
                  className="flex items-center justify-between py-2 border-b border-border last:border-0"
                >
                  <span className="text-sm">{item.label}</span>

                  {item.type === 'switch' && (
                    <button
                      onClick={() => handleToggle(item.key)}
                      className={`w-12 h-6 rounded-full transition-colors relative ${
                        settings[item.key] ? 'bg-primary' : 'bg-surface-light'
                      }`}
                    >
                      <span
                        className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                          settings[item.key] ? 'translate-x-7' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  )}

                  {item.type === 'select' && (
                    <select
                      value={settings[item.key]}
                      onChange={(e) => handleSelect(item.key, e.target.value)}
                      className="bg-surface-light rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                    >
                      {item.options?.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  )}

                  {item.type === 'text' && (
                    <span className="text-sm text-text-secondary">{item.value}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* About */}
        <div className="bg-surface rounded-xl p-4 border border-border">
          <h2 className="text-sm font-medium mb-3">关于</h2>
          <div className="text-xs text-text-secondary space-y-1">
            <p>Hermes Desktop v2.0</p>
            <p>基于 PyQt6 的桌面 AI 编程助手</p>
            <p>© 2024-2026 Hermes Team</p>
          </div>
        </div>
      </div>
    </div>
  )
}
