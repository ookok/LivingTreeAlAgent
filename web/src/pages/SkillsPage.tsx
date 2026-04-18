import { useState } from 'react'
import { Wrench, Play, Search, Filter } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { hermesApi } from '@/services/api'
import toast from 'react-hot-toast'

const categoryIcons: Record<string, string> = {
  writing: '✍️',
  coding: '💻',
  design: '🎨',
  data: '📊',
  default: '🛠️',
}

export default function SkillsPage() {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<string | null>(null)
  const [selectedSkill, setSelectedSkill] = useState<any>(null)

  const { data: skillsData, isLoading } = useQuery({
    queryKey: ['skills', category],
    queryFn: () => hermesApi.listSkills(category || undefined),
  })

  const skills = skillsData?.data?.skills || []

  const filteredSkills = skills.filter((skill: any) =>
    skill.name?.toLowerCase().includes(search.toLowerCase()) ||
    skill.description?.toLowerCase().includes(search.toLowerCase())
  )

  const categories = ['writing', 'coding', 'design', 'data']

  const handleExecute = async (skillId: string) => {
    try {
      const response = await hermesApi.executeSkill(skillId)
      if (response.success) {
        toast.success('技能执行成功')
      } else {
        toast.error(response.error || '执行失败')
      }
    } catch (error) {
      toast.error('执行出错')
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="h-14 px-4 flex items-center border-b border-border bg-surface">
        <h1 className="text-lg font-semibold">技能市场</h1>
      </header>

      {/* Search & Filter */}
      <div className="p-4 space-y-3 border-b border-border bg-surface">
        <div className="relative">
          <Search
            size={20}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索技能..."
            className="w-full bg-surface-light rounded-xl pl-10 pr-4 py-3 text-sm focus:ring-2 focus:ring-primary/50"
          />
        </div>

        <div className="flex items-center space-x-2 overflow-x-auto pb-1">
          <Filter size={16} className="text-text-secondary flex-shrink-0" />
          <button
            onClick={() => setCategory(null)}
            className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
              !category
                ? 'bg-primary text-white'
                : 'bg-surface-light text-text-secondary hover:text-text-primary'
            }`}
          >
            全部
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap transition-colors ${
                category === cat
                  ? 'bg-primary text-white'
                  : 'bg-surface-light text-text-secondary hover:text-text-primary'
              }`}
            >
              {categoryIcons[cat]} {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Skills Grid */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="text-center text-text-secondary py-8">加载中...</div>
        ) : filteredSkills.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filteredSkills.map((skill: any) => (
              <div
                key={skill.id}
                className="bg-surface rounded-xl p-4 border border-border hover:border-primary/50 transition-colors"
              >
                <div className="flex items-start space-x-3">
                  <div className="w-10 h-10 bg-surface-light rounded-lg flex items-center justify-center text-xl">
                    {skill.icon || '🛠️'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">{skill.name}</h3>
                    <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">
                      {skill.description}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <span className="text-xs px-2 py-0.5 bg-surface-light rounded">
                    {skill.category || 'general'}
                  </span>
                  <button
                    onClick={() => handleExecute(skill.id)}
                    className="px-3 py-1.5 bg-primary/20 text-primary rounded-lg text-sm hover:bg-primary/30 transition-colors flex items-center space-x-1"
                  >
                    <Play size={14} />
                    <span>执行</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-text-secondary py-8">
            <Wrench size={48} className="mx-auto mb-4 opacity-50" />
            <p>没有找到相关技能</p>
          </div>
        )}
      </div>
    </div>
  )
}
