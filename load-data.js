// load-data.js — 数据加载层
// 优先从 CMS API 获取，失败则回退到 data.js 的全局变量

(async function() {
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 800)
    const res = await fetch('/api/state', { signal: ctrl.signal })
    clearTimeout(timer)
    if (res.ok) {
      const data = await res.json()
      window.photoGroups = data.photoGroups || []
      window.videos = data.videos || []
      window.commercialProjects = data.commercialProjects || []
      window.__DATA_SOURCE__ = 'api'
    }
  } catch {
    window.__DATA_SOURCE__ = 'static'
  }
  document.dispatchEvent(new CustomEvent('data-ready'))
})()
