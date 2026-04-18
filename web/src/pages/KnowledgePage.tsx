import { useState } from 'react'
import { Search, Plus, FileText, Trash2 } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { hermesApi } from '@/services/api'
import toast from 'react-hot-toast'

export default function KnowledgePage() {
  const [query, setQuery] = useState('')
  const [selectedTab, setSelectedTab] = useState<'search' | 'store'>('search')
  const queryClient = useQueryClient()

  // 搜索记忆
  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: ['memory-search', query],
    queryFn: () => hermesApi.searchMemory(query),
    enabled: query.length > 0,
  })

  // 存储记忆
  const [newMemory, setNewMemory] = useState('')
  const [memoryType, setMemoryType] = useState<'permanent' | 'session' | 'working'>('permanent')

  const storeMutation = useMutation({
    mutationFn: () => hermesApi.storeMemory(newMemory, memoryType),
    onSuccess: () => {
      toast.success('记忆已存储')
      setNewMemory('')
      queryClient.invalidateQueries({ queryKey: ['memory-search'] })
    },
    onError: () => {
      toast.error('存储失败')
    },
  })

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="h-14 px-4 flex items-center border-b border-border bg-surface">
        <h1 className="text-lg font-semibold">知识库</h1>
      </header>

      {/* Tabs */}
      <div className="flex border-b border-border bg-surface">
        <button
          onClick={() => setSelectedTab('search')}
          className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
            selectedTab === 'search'
              ? 'border-primary text-primary'
              : 'border-transparent text-text-secondary hover:text-text-primary'
          }`}
        >
          搜索记忆
        </button>
        <button
          onClick={() => setSelectedTab('store')}
          className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors ${
            selectedTab === 'store'
              ? 'border-primary text-primary'
              : 'border-transparent text-text-secondary hover:text-text-primary'
          }`}
        >
          存储记忆
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {selectedTab === 'search' ? (
          <div className="space-y-4">
            {/* Search Input */}
            <div className="relative">
              <Search
                size={20}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="搜索记忆..."
                className="w-full bg-surface-light rounded-xl pl-10 pr-4 py-3 text-sm focus:ring-2 focus:ring-primary/50"
              />
            </div>

            {/* Results */}
            {searching && (
              <div className="text-center text-text-secondary py-8">搜索中...</div>
            )}

            {searchResults?.data?.results?.length > 0 ? (
              <div className="space-y-2">
                {searchResults.data.results.map((result: any, index: number) => (
                  <div
                    key={index}
                    className="bg-surface rounded-xl p-4 border border-border"
                  >
                    <div className="flex items-start space-x-3">
                      <FileText size={20} className="text-primary mt-1" />
                      <div className="flex-1">
                        <p className="text-sm">{result.content}</p>
                        <div className="mt-2 flex items-center space-x-2">
                          <span className="text-xs px-2 py-0.5 bg-surface-light rounded">
                            {result.type || 'permanent'}
                          </span>
                          <span className="text-xs text-text-secondary">
                            {result.score?.toFixed(2) || '1.0'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : query && !searching ? (
              <div className="text-center text-text-secondary py-8">
                未找到相关记忆
              </div>
            ) : (
              <div className="text-center text-text-secondary py-8">
                输入关键词搜索记忆
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Memory Type */}
            <div>
              <label className="block text-sm text-text-secondary mb-2">记忆类型</label>
              <div className="flex space-x-2">
                {(['permanent', 'session', 'working'] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setMemoryType(type)}
                    className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                      memoryType === type
                        ? 'bg-primary text-white'
                        : 'bg-surface-light text-text-secondary hover:text-text-primary'
                    }`}
                  >
                    {type === 'permanent' ? '永久' : type === 'session' ? '会话' : '工作'}
                  </button>
                ))}
              </div>
            </div>

            {/* Content */}
            <div>
              <label className="block text-sm text-text-secondary mb-2">记忆内容</label>
              <textarea
                value={newMemory}
                onChange={(e) => setNewMemory(e.target.value)}
                placeholder="输入要存储的记忆..."
                rows={6}
                className="w-full bg-surface-light rounded-xl px-4 py-3 text-sm resize-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            {/* Submit */}
            <button
              onClick={() => storeMutation.mutate()}
              disabled={!newMemory.trim() || storeMutation.isPending}
              className="w-full py-3 bg-primary rounded-xl font-medium hover:bg-primary-hover disabled:opacity-50 transition-colors flex items-center justify-center space-x-2"
            >
              <Plus size={20} />
              <span>{storeMutation.isPending ? '存储中...' : '存储记忆'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
