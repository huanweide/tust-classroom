// ═══════════════════════════════════════
// TUST 空闲教室 — 微信小程序
// 数据源: GitHub Pages 静态 JSON
// 查询逻辑在本地执行，不依赖后端
// ═══════════════════════════════════════

const DATA = 'https://huanweide.github.io/tust-classroom/data'
const WDAY = ['日', '一', '二', '三', '四', '五', '六']

Page({
  data: {
    campuses: [],
    campusIdx: 0,
    dates: [],
    selDate: '',
    selDateIdx: 0,
    periods: {},
    periodLabels: [],
    periodKeys: [],
    buildings: {},
    buildingList: ['全部教学楼'],
    updated: '--',

    // Mode 1
    mode1Period: 0,

    // Mode 2
    mode2Start: 0,
    mode2End: 12, // last period (13 total, index 12)
    mode2Building: 0,

    // Mode 3
    mode3Room: '',
    suggestions: [],

    // Results
    loading: false,
    loadingText: '',
    results: [],
    resultSummary: '',
    emptyMsg: '',
    emptyHint: '',

    // Date cache
    _dateCache: {}
  },

  // Utilities exposed to WXML
  util: {
    mmdd(d) { const dt = new Date(d + 'T00:00:00'); return (dt.getMonth()+1) + '/' + dt.getDate() },
    wday(d) { return WDAY[new Date(d + 'T00:00:00').getDay()] }
  },

  // ═══════════════════════════
  // Lifecycle
  // ═══════════════════════════
  onLoad() {
    this.loadIndex()
  },

  async loadIndex() {
    this.setData({ loading: true, loadingText: '加载数据中...' })
    try {
      const index = await this._fetch(DATA + '/index.json')
      const periodLabels = Object.entries(index.periods).map(([p, t]) => `第${p}节 ${t}`)
      const periodKeys = Object.keys(index.periods)

      this.setData({
        loading: false,
        campuses: index.campuses,
        dates: index.dates,
        periods: index.periods,
        periodLabels,
        periodKeys,
        buildings: index.buildings,
        updated: index.updated,
        mode2End: periodKeys.length - 1
      })

      // Load search index
      this.loadSearch()

      // Default: today or first available date
      this.goToday()
    } catch (e) {
      console.error('加载失败:', e)
      this.setData({
        loading: false,
        emptyMsg: '数据加载失败',
        emptyHint: '请检查网络连接后重试'
      })
    }
  },

  async loadSearch() {
    try {
      const raw = await this._fetch(DATA + '/search.json')
      // search.json is [{c, b, r}, ...] — build flat name list by campus
      const byCampus = {}
      raw.forEach(({ c, b, r }) => {
        if (!byCampus[c]) byCampus[c] = []
        byCampus[c].push(b + r)
      })
      this._searchData = byCampus
    } catch (e) {
      console.warn('搜索索引加载失败，自动补全不可用')
    }
  },

  // ═══════════════════════════
  // Fetch helper
  // ═══════════════════════════
  _fetch(url) {
    return new Promise((resolve, reject) => {
      wx.request({
        url,
        timeout: 8000,
        success: res => resolve(res.data),
        fail: reject
      })
    })
  },

  // ═══════════════════════════
  // Campus
  // ═══════════════════════════
  onCampusChange(e) {
    const idx = parseInt(e.detail.value)
    const campus = this.data.campuses[idx]
    const list = ['全部教学楼', ...(this.data.buildings[campus] || [])]
    this.setData({ campusIdx: idx, buildingList: list, mode2Building: 0 })
  },

  // ═══════════════════════════
  // Date Navigation
  // ═══════════════════════════
  pickDate(e) {
    const d = e.currentTarget.dataset.date
    if (!d) return
    const idx = this.data.dates.indexOf(d)
    this.setData({ selDate: d, selDateIdx: idx >= 0 ? idx : 0, results: [], emptyMsg: '', emptyHint: '' })
    this._loadDateData(d)
  },

  shiftDate(e) {
    const dir = parseInt(e.currentTarget.dataset.dir)
    const newIdx = Math.max(0, Math.min(this.data.dates.length - 1, this.data.selDateIdx + dir))
    const d = this.data.dates[newIdx]
    if (d) this.pickDate({ currentTarget: { dataset: { date: d } } })
  },

  goToday() {
    const today = new Date()
    const ts = today.getFullYear() + '-' +
      String(today.getMonth() + 1).padStart(2, '0') + '-' +
      String(today.getDate()).padStart(2, '0')
    const d = this.data.dates.includes(ts) ? ts : this.data.dates[0]
    if (d) this.pickDate({ currentTarget: { dataset: { date: d } } })
  },

  async _loadDateData(d) {
    if (this.data._dateCache[d]) return
    try {
      const data = await this._fetch(DATA + '/' + d + '.json')
      this.data._dateCache[d] = data
    } catch (e) {
      console.warn('加载日期数据失败:', d)
    }
  },

  _getDateData() {
    return this.data._dateCache[this.data.selDate] || null
  },

  _getCampusData() {
    const all = this._getDateData()
    if (!all) return null
    return all[this.data.campuses[this.data.campusIdx]] || null
  },

  // ═══════════════════════════
  // Mode 1: 按节次查空闲教室
  // ═══════════════════════════
  onMode1Period(e) {
    this.setData({ mode1Period: parseInt(e.detail.value) })
  },

  queryMode1() {
    const campusData = this._getCampusData()
    if (!campusData) { this._noData(); return }

    const pKey = this.data.periodKeys[this.data.mode1Period]
    if (!pKey) { this._showEmpty('请选择节次'); return }

    this.setData({ loading: true, loadingText: '查询中...' })

    const results = []
    for (const [building, rooms] of Object.entries(campusData)) {
      for (const [room, freePeriods] of Object.entries(rooms)) {
        if (freePeriods.includes(parseInt(pKey))) {
          results.push({
            name: building + room,
            detail: building,
            periods: [{ label: `第${pKey}节 空闲`, free: true }]
          })
        }
      }
    }
    results.sort((a, b) => a.name.localeCompare(b.name, 'zh'))

    this.setData({
      loading: false,
      results,
      resultSummary: results.length > 0 ? `找到 ${results.length} 间空闲教室` : '',
      emptyMsg: results.length === 0 ? '该节次没有空闲教室' : '',
      emptyHint: results.length === 0 ? '试试换一个节次或日期' : ''
    })
  },

  // ═══════════════════════════
  // Mode 2: 查连续空闲教室
  // ═══════════════════════════
  onMode2Start(e) { this.setData({ mode2Start: parseInt(e.detail.value) }) },
  onMode2End(e) { this.setData({ mode2End: parseInt(e.detail.value) }) },
  onMode2Building(e) { this.setData({ mode2Building: parseInt(e.detail.value) }) },

  queryMode2() {
    const campusData = this._getCampusData()
    if (!campusData) { this._noData(); return }

    const startP = this.data.periodKeys[this.data.mode2Start]
    const endP = this.data.periodKeys[this.data.mode2End]
    if (!startP || !endP) { this._showEmpty('请选择时间范围'); return }
    if (parseInt(startP) > parseInt(endP)) {
      this._showEmpty('开始节次不能晚于结束节次')
      return
    }

    this.setData({ loading: true, loadingText: '查询中...' })

    const needed = []
    for (let p = parseInt(startP); p <= parseInt(endP); p++) needed.push(p)

    const filterBuilding = this.data.buildingList[this.data.mode2Building] || '全部教学楼'
    const results = []

    for (const [building, rooms] of Object.entries(campusData)) {
      if (filterBuilding !== '全部教学楼' && building !== filterBuilding) continue
      for (const [room, freePeriods] of Object.entries(rooms)) {
        if (needed.every(p => freePeriods.includes(p))) {
          results.push({
            name: building + room,
            detail: `第${startP}-${endP}节 连续空闲`,
            periods: needed.map(p => ({ label: `第${p}节`, free: true }))
          })
        }
      }
    }
    results.sort((a, b) => a.name.localeCompare(b.name, 'zh'))

    this.setData({
      loading: false,
      results,
      resultSummary: results.length > 0 ? `找到 ${results.length} 间教室连续空闲` : '',
      emptyMsg: results.length === 0 ? '没有教室在该时段连续空闲' : '',
      emptyHint: results.length === 0 ? '试试扩大时间范围或去掉教学楼筛选' : ''
    })
  },

  // ═══════════════════════════
  // Mode 3: 查某教室空闲时段
  // ═══════════════════════════
  onMode3Input(e) {
    const val = e.detail.value.trim()
    this.setData({ mode3Room: val })
    if (val.length >= 1) {
      this._autoComplete(val)
    } else {
      this.setData({ suggestions: [] })
    }
  },

  onMode3Focus() {
    if (this.data.mode3Room.length >= 1) {
      this._autoComplete(this.data.mode3Room)
    }
  },

  pickSuggestion(e) {
    const name = e.currentTarget.dataset.name
    this.setData({ mode3Room: name, suggestions: [] })
  },

  _autoComplete(q) {
    const campus = this.data.campuses[this.data.campusIdx]
    const names = (this._searchData || {})[campus]
    if (!names || names.length === 0) { this.setData({ suggestions: [] }); return }

    const results = []

    // Tier 1: exact match
    if (names.includes(q)) results.push(q)

    // Tier 2: starts with
    for (const n of names) {
      if (n.startsWith(q) && !results.includes(n)) results.push(n)
      if (results.length >= 10) break
    }

    // Tier 3: contains (only if few results)
    if (results.length < 5) {
      for (const n of names) {
        if (n.includes(q) && !results.includes(n)) results.push(n)
        if (results.length >= 10) break
      }
    }

    this.setData({ suggestions: results.slice(0, 10) })
  },

  queryMode3() {
    const campusData = this._getCampusData()
    if (!campusData) { this._noData(); return }

    const roomName = this.data.mode3Room.trim()
    if (!roomName) { this._showEmpty('请输入教室名'); return }

    this.setData({ loading: true, loadingText: '查询中...', suggestions: [] })

    let found = null
    let foundBuilding = ''
    let foundRoom = ''

    // Tier 1: exact match (full "building+room" string)
    for (const [building, rooms] of Object.entries(campusData)) {
      if (rooms[roomName]) {
        found = rooms[roomName]; foundBuilding = building; foundRoom = roomName; break
      }
    }

    // Tier 2: split by building prefix (e.g. "3-101" → building "3-", room "101")
    if (!found) {
      for (const [building, rooms] of Object.entries(campusData)) {
        if (roomName.startsWith(building)) {
          const short = roomName.slice(building.length)
          if (rooms[short]) { found = rooms[short]; foundBuilding = building; foundRoom = short; break }
        }
      }
    }

    // Tier 3: partial prefix match (e.g. "12" finds "12阶梯(d)")
    if (!found) {
      for (const [building, rooms] of Object.entries(campusData)) {
        // If input starts with a building, check rooms in that building first
        if (roomName.startsWith(building)) {
          const short = roomName.slice(building.length)
          for (const r of Object.keys(rooms)) {
            if (r.startsWith(short)) { found = rooms[r]; foundBuilding = building; foundRoom = r; break }
          }
          if (found) break
        }
      }
    }

    // Tier 4: full scan — any room that contains the query
    if (!found) {
      for (const [building, rooms] of Object.entries(campusData)) {
        for (const r of Object.keys(rooms)) {
          if (r.includes(roomName)) { found = rooms[r]; foundBuilding = building; foundRoom = r; break }
        }
        if (found) break
      }
    }

    if (!found) {
      // Build flat list for suggestions
      const allRooms = []
      for (const [building, rooms] of Object.entries(campusData)) {
        for (const r of Object.keys(rooms)) allRooms.push(building + r)
      }
      // Sort by shared prefix length with query
      const similar = allRooms
        .filter(r => r.includes(roomName))
        .sort((a, b) => {
          const ai = a.indexOf(roomName), bi = b.indexOf(roomName)
          return ai - bi // earlier match = more similar
        })
        .slice(0, 5)

      this.setData({
        loading: false,
        emptyMsg: `未找到教室「${roomName}」`,
        emptyHint: similar.length > 0 ? `你可能想找: ${similar.join(', ')}` : '请检查教室名是否正确'
      })
      return
    }

    const building = foundBuilding
    const room = foundRoom

    // Build period display (13 periods)
    const allPeriods = this.data.periodKeys.map((k, i) => {
      const isFree = found.includes(parseInt(k))
      return { label: isFree ? `第${k}节` : '——', free: isFree }
    })

    const freeCount = found.length
    this.setData({
      loading: false,
      results: [{
        name: building + room,
        detail: `${freeCount}/13 节次空闲`,
        periods: allPeriods
      }],
      resultSummary: `「${building}${room}」空闲时段`,
      emptyMsg: '',
      emptyHint: ''
    })
  },

  // ═══════════════════════════
  // Helpers
  // ═══════════════════════════
  _noData() {
    this.setData({
      emptyMsg: '请先选择日期',
      emptyHint: '数据加载完成后选择日期再查询',
      results: []
    })
  },

  _showEmpty(msg) {
    this.setData({ emptyMsg: msg, emptyHint: '', results: [] })
  }
})
