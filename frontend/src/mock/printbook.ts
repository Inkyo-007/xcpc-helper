/** 打印册原型使用的本地模拟数据（后端接入后由 API 取代）。 */

import type {
  BookBlock,
  ImageBlock,
  PrintBookDetail,
  ResolvedTemplateInfo,
  TemplateDetail,
  TemplateSummary,
  TemplateVariant,
} from '@/types'

const CODE = `#include <bits/stdc++.h>
using namespace std;
using ll = long long;

ll qpow(ll a, ll b, ll m) {
  ll r = 1;
  while (b) {
    if (b & 1) r = r * a % m;
    a = a * a % m;
    b >>= 1;
  }
  return r;
}`

const SIEVE = `const int N = 1e6 + 5;
int lp[N];
vector<int> primes;

void linear_sieve(int n) {
  for (int i = 2; i <= n; ++i) {
    if (!lp[i]) lp[i] = i, primes.push_back(i);
    for (int p : primes) {
      if (p > lp[i] || i * p > n) break;
      lp[i * p] = p;
    }
  }
}`

const DSU = `struct DSU {
  vector<int> fa, sz;
  DSU(int n) : fa(n + 1), sz(n + 1, 1) { iota(fa.begin(), fa.end(), 0); }
  int find(int x) { return fa[x] == x ? x : fa[x] = find(fa[x]); }
  void unite(int a, int b) {
    a = find(a), b = find(b);
    if (a == b) return;
    if (sz[a] < sz[b]) swap(a, b);
    fa[b] = a, sz[a] += sz[b];
  }
};`

const DSU_WEIGHT = `struct DSU {
  vector<int> fa, val;
  DSU(int n) : fa(n + 1), val(n + 1) { iota(fa.begin(), fa.end(), 0); }
  int find(int x) {
    if (fa[x] == x) return x;
    int root = find(fa[x]);
    val[x] += val[fa[x]];
    return fa[x] = root;
  }
};`

const KMP = `vector<int> kmp(const string& s) {
  int n = s.size();
  vector<int> pi(n);
  for (int i = 1; i < n; ++i) {
    int j = pi[i - 1];
    while (j && s[i] != s[j]) j = pi[j - 1];
    if (s[i] == s[j]) ++j;
    pi[i] = j;
  }
  return pi;
}`

/** 长代码模板：验证跨页分行渲染（行数守恒、行号连续）。 */
const SCC = [
  '// 缩点（Tarjan 强连通分量）',
  'struct SCC {',
  '  int n, timer = 0, top = 0, cnt = 0;',
  '  vector<vector<int>> g, cg;',
  '  vector<int> dfn, low, stk, bel, siz;',
  '  vector<bool> ins;',
  '',
  '  explicit SCC(int n) : n(n), g(n + 1), dfn(n + 1), low(n + 1),',
  '      stk(n + 1), bel(n + 1), siz(n + 1), ins(n + 1) {}',
  '',
  '  void add_edge(int u, int v) { g[u].push_back(v); }',
  '',
  '  void tarjan(int u) {',
  '    dfn[u] = low[u] = ++timer;',
  '    stk[++top] = u;',
  '    ins[u] = true;',
  '    for (int v : g[u]) {',
  '      if (!dfn[v]) {',
  '        tarjan(v);',
  '        low[u] = min(low[u], low[v]);',
  '      } else if (ins[v]) {',
  '        low[u] = min(low[u], dfn[v]);',
  '      }',
  '    }',
  '    if (dfn[u] == low[u]) {',
  '      ++cnt;',
  '      int v;',
  '      do {',
  '        v = stk[top--];',
  '        ins[v] = false;',
  '        bel[v] = cnt;',
  '        ++siz[cnt];',
  '      } while (v != u);',
  '    }',
  '  }',
  '',
  '  void run() {',
  '    for (int i = 1; i <= n; ++i)',
  '      if (!dfn[i]) tarjan(i);',
  '    cg.assign(cnt + 1, {});',
  '    for (int u = 1; u <= n; ++u)',
  '      for (int v : g[u])',
  '        if (bel[u] != bel[v]) cg[bel[u]].push_back(bel[v]);',
  '    for (auto& adj : cg) {',
  '      sort(adj.begin(), adj.end());',
  '      adj.erase(unique(adj.begin(), adj.end()), adj.end());',
  '    }',
  '  }',
  '};',
  '',
  ...Array.from(
    { length: 120 },
    (_, i) =>
      `// 注释行 ${i + 1}：缩点后的 DAG 上通常按拓扑序递推，bel[i] 为点 i 所属分量编号。`,
  ),
  '',
  'int main() {',
  '  int n, m;',
  '  scanf("%d%d", &n, &m);',
  '  SCC scc(n);',
  '  for (int i = 0; i < m; ++i) {',
  '    int u, v;',
  '    scanf("%d%d", &u, &v);',
  '    scc.add_edge(u, v);',
  '  }',
  '  scc.run();',
  '  printf("%d\\n", scc.cnt);',
  '  return 0;',
  '}',
].join('\n')

function variant(
  templateId: string,
  name: string,
  file: string,
  code: string,
  body: string,
  extra: Partial<TemplateVariant> = {},
): TemplateVariant {
  const root = name === templateId.split('/').pop()
  return {
    id: root ? templateId : `${templateId}/${name}`,
    name,
    lang: 'cpp',
    file,
    code,
    body,
    tags: [],
    src: null,
    page: null,
    updated: '2026-07-05',
    priority: 2,
    ...extra,
  }
}

function summary(detail: TemplateDetail): TemplateSummary {
  const primary = detail.variants[0]
  return {
    id: detail.id,
    name: detail.name,
    cat: detail.cat,
    lang: primary?.lang ?? null,
    file: primary?.file ?? null,
    tags: detail.tags,
    src: primary?.src ?? null,
    page: primary?.page ?? null,
    updated: detail.updated,
    priority: detail.priority,
    variant_count: detail.variant_count,
  }
}

export const MOCK_TEMPLATE_DETAILS: TemplateDetail[] = [
  {
    id: '数学/快速幂',
    name: '快速幂',
    cat: '数学',
    lang: 'cpp',
    file: 'qpow.cpp',
    tags: ['数论'],
    src: '洛谷 P1226',
    page: 'https://www.luogu.com.cn/problem/P1226',
    updated: '2026-07-05',
    priority: 5,
    variant_count: 1,
    desc: '二分倍增实现 $O(\\log b)$ 幂运算，模意义下与整数快速幂通用。',
    variants: [
      variant('数学/快速幂', '快速幂', 'qpow.cpp', CODE, '递归与迭代两种写法等价，注意取模。', {
        tags: ['数论'],
        src: '洛谷 P1226',
        page: 'https://www.luogu.com.cn/problem/P1226',
        priority: 5,
      }),
    ],
  },
  {
    id: '数学/线性筛',
    name: '线性筛',
    cat: '数学',
    lang: 'cpp',
    file: 'euler_sieve.cpp',
    tags: ['素数'],
    src: '洛谷 P3383',
    page: 'https://www.luogu.com.cn/problem/P3383',
    updated: '2026-07-09',
    priority: 4,
    variant_count: 1,
    desc: '每个合数只被最小质因子筛掉一次。',
    variants: [
      variant('数学/线性筛', '线性筛', 'euler_sieve.cpp', SIEVE, '同时可以维护最小质因子与积性函数。', {
        tags: ['素数'],
        src: '洛谷 P3383',
        page: 'https://www.luogu.com.cn/problem/P3383',
        priority: 4,
        updated: '2026-07-09',
      }),
    ],
  },
  {
    id: '数据结构/并查集',
    name: '并查集',
    cat: '数据结构',
    lang: 'cpp',
    file: 'dsu.cpp',
    tags: ['连通性'],
    src: '洛谷 P3367',
    page: 'https://www.luogu.com.cn/problem/P3367',
    updated: '2026-07-10',
    priority: 4,
    variant_count: 2,
    desc: '路径压缩与按秩合并；带权版本维护到根的边权。',
    variants: [
      variant('数据结构/并查集', '路径压缩', 'dsu.cpp', DSU, '路径压缩 + 按大小合并。', {
        tags: ['连通性'],
        priority: 4,
        updated: '2026-07-08',
      }),
      variant('数据结构/并查集', '带权', 'dsu_weight.cpp', DSU_WEIGHT, '边权可加减，维护相对关系。', {
        tags: ['连通性', '带权'],
        priority: 4,
        updated: '2026-07-10',
      }),
    ],
  },
  {
    id: '字符串/KMP',
    name: 'KMP',
    cat: '字符串',
    lang: 'cpp',
    file: 'kmp.cpp',
    tags: ['匹配'],
    src: null,
    page: null,
    updated: '2026-07-12',
    priority: 3,
    variant_count: 1,
    desc: '前缀函数实现，支持单串匹配与周期推导。',
    variants: [
      variant('字符串/KMP', 'KMP', 'kmp.cpp', KMP, '$O(n)$ 计算前缀函数。', {
        tags: ['匹配'],
        priority: 3,
        updated: '2026-07-12',
      }),
    ],
  },
  {
    id: '图论/缩点',
    name: '缩点',
    cat: '图论',
    lang: 'cpp',
    file: 'scc.cpp',
    tags: ['强连通'],
    src: '洛谷 P3387',
    page: 'https://www.luogu.com.cn/problem/P3387',
    updated: '2026-07-15',
    priority: 4,
    variant_count: 1,
    desc: 'Tarjan 缩点后得到 DAG，可在其上拓扑递推。长代码示例，用于验证跨页渲染。',
    variants: [
      variant('图论/缩点', '缩点', 'scc.cpp', SCC, '复杂度 $O(n + m)$，注意栈空间。', {
        tags: ['强连通'],
        src: '洛谷 P3387',
        page: 'https://www.luogu.com.cn/problem/P3387',
        priority: 4,
        updated: '2026-07-15',
      }),
    ],
  },
]

export const MOCK_TEMPLATES: TemplateSummary[] = MOCK_TEMPLATE_DETAILS.map(summary)

export const MOCK_TEMPLATE_DETAIL_MAP: Record<string, TemplateDetail> = Object.fromEntries(
  MOCK_TEMPLATE_DETAILS.map((d) => [d.id, d]),
)

/** 按打印册条目的 version 约定解析版本（null=主版本，'~'=顶层单版本）。 */
export function resolveTemplateInfo(
  templateId: string,
  version: string | null,
): ResolvedTemplateInfo | null {
  const detail = MOCK_TEMPLATE_DETAIL_MAP[templateId]
  if (!detail || !detail.variants.length) return null
  const target =
    version === null
      ? detail.variants[0]
      : detail.variants.find((v) => v.id === templateId || v.name === version)
  if (!target) return null
  return {
    name: detail.name,
    cat: detail.cat,
    version_name: target.name,
    lang: target.lang,
    file: target.file,
    code: target.code,
    body: target.body,
    tags: target.tags,
    src: target.src,
    page: target.page,
    updated: target.updated,
    priority: target.priority,
  }
}

function tplBlock(
  id: string,
  templateId: string,
  version: string | null,
  heading_level: number,
  title: string | null = null,
  include_body: boolean | null = null,
) {
  return {
    id,
    type: 'template' as const,
    template: templateId,
    version,
    title,
    heading_level,
    include_body,
    resolved: resolveTemplateInfo(templateId, version),
  }
}

const DEFAULT_OPTIONS = {
  include_toc: true,
  include_meta: true,
  include_body: true,
  h1_page_break: true,
}

const ICPC_BLOCKS: BookBlock[] = [
  { id: 'b-head-math', type: 'heading', title: '数学', heading_level: 1 },
  tplBlock('b-tpl-qpow', '数学/快速幂', null, 2),
  tplBlock('b-tpl-sieve', '数学/线性筛', null, 2),
  {
    id: 'b-md-note',
    type: 'markdown',
    title: '赛前注意事项',
    content: '先写朴素版本保证正确性，再逐步优化常数。\n\n复杂度过高时优先检查循环边界。',
  },
  { id: 'b-head-ds', type: 'heading', title: '数据结构', heading_level: 1 },
  tplBlock('b-tpl-dsu', '数据结构/并查集', '带权', 2),
  { id: 'b-break-1', type: 'page_break' },
  { id: 'b-head-str', type: 'heading', title: '字符串', heading_level: 1 },
  tplBlock('b-tpl-kmp', '字符串/KMP', null, 2),
  { id: 'b-head-graph', type: 'heading', title: '图论', heading_level: 1 },
  tplBlock('b-tpl-scc', '图论/缩点', null, 2),
  {
    id: 'b-img-1',
    type: 'image',
    src: 'assets/complexity.png',
    caption: '常用复杂度对照',
    width: '80%',
  } satisfies ImageBlock,
]

const SCHOOL_BLOCKS: BookBlock[] = [
  { id: 's-head-base', type: 'heading', title: '基础', heading_level: 1 },
  tplBlock('s-tpl-dsu', '数据结构/并查集', '路径压缩', 2, '并查集'),
]

export const MOCK_BOOKS: PrintBookDetail[] = [
  {
    name: 'ICPC区域赛版',
    cover: {
      title: 'ICPC 区域赛版',
      subtitle: '2026 赛季',
      author: 'Ink',
      logo: null,
    },
    options: DEFAULT_OPTIONS,
    blocks: ICPC_BLOCKS,
  },
  {
    name: '校内赛版',
    cover: {
      title: '校内赛版',
      subtitle: null,
      author: null,
      logo: null,
    },
    options: { ...DEFAULT_OPTIONS, include_meta: false },
    blocks: SCHOOL_BLOCKS,
  },
]
