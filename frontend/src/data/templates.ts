import type { Template } from '@/types'

export const TEMPLATES: Template[] = [
  {
    id: 1,
    name: '线段树（懒标记）',
    cat: 'ds',
    lang: 'cpp',
    file: 'segtree_lazy.cpp',
    cplx: '区间修改/查询 O(log n)',
    tags: ['区间加', '区间和'],
    src: '洛谷 P3372',
    updated: '2026-07-28',
    priority: 5,
    desc: '支持区间加、区间求和。下标从 1 开始，build 前读入原数组 a[]。注意 pushdown 时机，long long 必开。',
    lastUsedAt: '2026-07-30',
    code: `#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
const int N = 1e5 + 10;

ll a[N], tr[N << 2], lz[N << 2];

void pushup(int p) { tr[p] = tr[p << 1] + tr[p << 1 | 1]; }

void pushdown(int p, int l, int r) {
    if (!lz[p]) return;
    int mid = (l + r) >> 1;
    lz[p << 1] += lz[p]; lz[p << 1 | 1] += lz[p];
    tr[p << 1] += lz[p] * (mid - l + 1);
    tr[p << 1 | 1] += lz[p] * (r - mid);
    lz[p] = 0;
}

void build(int p, int l, int r) {
    if (l == r) { tr[p] = a[l]; return; }
    int mid = (l + r) >> 1;
    build(p << 1, l, mid);
    build(p << 1 | 1, mid + 1, r);
    pushup(p);
}

void update(int p, int l, int r, int ql, int qr, ll v) {
    if (ql <= l && r <= qr) {
        tr[p] += v * (r - l + 1);
        lz[p] += v;
        return;
    }
    pushdown(p, l, r);
    int mid = (l + r) >> 1;
    if (ql <= mid) update(p << 1, l, mid, ql, qr, v);
    if (qr > mid) update(p << 1 | 1, mid + 1, r, ql, qr, v);
    pushup(p);
}

ll query(int p, int l, int r, int ql, int qr) {
    if (ql <= l && r <= qr) return tr[p];
    pushdown(p, l, r);
    int mid = (l + r) >> 1;
    ll res = 0;
    if (ql <= mid) res += query(p << 1, l, mid, ql, qr);
    if (qr > mid) res += query(p << 1 | 1, mid + 1, r, ql, qr);
    return res;
}`,
  },
  {
    id: 2,
    name: '树状数组',
    cat: 'ds',
    lang: 'cpp',
    file: 'bit.cpp',
    cplx: '单点改/前缀和 O(log n)',
    tags: ['前缀和', '逆序对'],
    src: '洛谷 P3374',
    updated: '2026-07-20',
    priority: 4,
    desc: '经典 BIT，下标从 1 开始。求逆序对时先离散化。',
    lastUsedAt: '2026-07-22',
    code: `#include <bits/stdc++.h>
using namespace std;
const int N = 5e5 + 10;

int n, tr[N];

inline int lowbit(int x) { return x & -x; }

void add(int x, int v) {
    for (; x <= n; x += lowbit(x)) tr[x] += v;
}

int query(int x) {
    int res = 0;
    for (; x; x -= lowbit(x)) res += tr[x];
    return res;
}`,
  },
  {
    id: 3,
    name: '并查集（路径压缩 + 按秩合并）',
    cat: 'ds',
    lang: 'cpp',
    file: 'dsu.cpp',
    cplx: '近似 O(1)',
    tags: ['连通性'],
    src: '洛谷 P3367',
    updated: '2026-06-30',
    priority: 5,
    desc: '两个优化都写上，复杂度才有保证。可扩展为带权并查集。',
    lastUsedAt: '2026-07-05',
    code: `#include <bits/stdc++.h>
using namespace std;
const int N = 1e5 + 10;

int fa[N], rnk[N];

void init(int n) {
    for (int i = 1; i <= n; i++) fa[i] = i, rnk[i] = 0;
}

int find(int x) {
    return fa[x] == x ? x : fa[x] = find(fa[x]);
}

void merge(int x, int y) {
    x = find(x), y = find(y);
    if (x == y) return;
    if (rnk[x] < rnk[y]) swap(x, y);
    fa[y] = x;
    if (rnk[x] == rnk[y]) rnk[x]++;
}`,
  },
  {
    id: 4,
    name: 'Dijkstra（堆优化）',
    cat: 'graph',
    lang: 'cpp',
    file: 'dijkstra.cpp',
    cplx: 'O((n + m) log m)',
    tags: ['最短路', '非负权'],
    src: '洛谷 P4779',
    updated: '2026-07-15',
    priority: 4,
    desc: '非负边权最短路。注意链式前向星或 vector 邻接表均可，dis 初始化 INF。',
    lastUsedAt: '2026-07-29',
    code: `#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
typedef pair<ll, int> pli;
const int N = 1e5 + 10;
const ll INF = 0x3f3f3f3f3f3f3f3f;

vector<pli> g[N]; // (边权, 终点)
ll dis[N];
bool vis[N];

void dijkstra(int s) {
    memset(dis, 0x3f, sizeof dis);
    priority_queue<pli, vector<pli>, greater<pli>> q;
    dis[s] = 0;
    q.push({0, s});
    while (!q.empty()) {
        auto [d, u] = q.top(); q.pop();
        if (vis[u]) continue;
        vis[u] = true;
        for (auto [w, v] : g[u]) {
            if (dis[v] > dis[u] + w) {
                dis[v] = dis[u] + w;
                q.push({dis[v], v});
            }
        }
    }
}`,
  },
  {
    id: 5,
    name: 'Tarjan 强连通分量',
    cat: 'graph',
    lang: 'cpp',
    file: 'tarjan_scc.cpp',
    cplx: 'O(n + m)',
    tags: ['SCC', '缩点'],
    src: '洛谷 B3609',
    updated: '2026-05-12',
    priority: 3,
    desc: '缩点后得到 DAG。注意 instk 的维护，回溯时 low[u] = min(low[u], dfn[v]) 只在 v 在栈中时。',
    lastUsedAt: '2026-06-02',
    code: `#include <bits/stdc++.h>
using namespace std;
const int N = 1e5 + 10;

vector<int> g[N];
int dfn[N], low[N], timer_;
int stk[N], top_, scc[N], cnt;
bool instk[N];

void tarjan(int u) {
    dfn[u] = low[u] = ++timer_;
    stk[++top_] = u; instk[u] = true;
    for (int v : g[u]) {
        if (!dfn[v]) {
            tarjan(v);
            low[u] = min(low[u], low[v]);
        } else if (instk[v]) {
            low[u] = min(low[u], dfn[v]);
        }
    }
    if (dfn[u] == low[u]) {
        cnt++;
        int x;
        do {
            x = stk[top_--];
            instk[x] = false;
            scc[x] = cnt;
        } while (x != u);
    }
}`,
  },
  {
    id: 6,
    name: 'KMP',
    cat: 'string',
    lang: 'cpp',
    file: 'kmp.cpp',
    cplx: 'O(n + m)',
    tags: ['模式匹配'],
    src: '洛谷 P3375',
    updated: '2026-04-18',
    priority: 2,
    desc: 'next 数组即 border 长度。下标从 1 开始更不容易写错。',
    lastUsedAt: '2026-07-11',
    code: `#include <bits/stdc++.h>
using namespace std;
const int N = 1e6 + 10;

char s[N], p[N];
int nxt[N];

void get_next(char *p, int m) {
    nxt[1] = 0;
    for (int i = 2, j = 0; i <= m; i++) {
        while (j && p[i] != p[j + 1]) j = nxt[j];
        if (p[i] == p[j + 1]) j++;
        nxt[i] = j;
    }
}

void kmp(char *s, int n, char *p, int m) {
    for (int i = 1, j = 0; i <= n; i++) {
        while (j && s[i] != p[j + 1]) j = nxt[j];
        if (s[i] == p[j + 1]) j++;
        if (j == m) {
            printf("%d\\n", i - m + 1); // 匹配起点（1-indexed）
            j = nxt[j];
        }
    }
}`,
  },
  {
    id: 7,
    name: '快速幂',
    cat: 'math',
    lang: 'cpp',
    file: 'qpow.cpp',
    cplx: 'O(log n)',
    tags: ['取模'],
    src: '洛谷 P1226',
    updated: '2026-03-08',
    priority: 4,
    desc: '底数先取模。乘法溢出时用 __int128 或慢速乘。',
    lastUsedAt: '2026-07-31',
    code: `#include <bits/stdc++.h>
using namespace std;
typedef long long ll;

ll qpow(ll a, ll b, ll mod) {
    ll res = 1 % mod;
    a %= mod;
    while (b) {
        if (b & 1) res = res * a % mod;
        a = a * a % mod;
        b >>= 1;
    }
    return res;
}`,
  },
  {
    id: 8,
    name: '线性筛（欧拉筛）',
    cat: 'math',
    lang: 'cpp',
    file: 'euler_sieve.cpp',
    cplx: 'O(n)',
    tags: ['素数', '积性函数'],
    src: '洛谷 P3383',
    updated: '2026-06-01',
    priority: 3,
    desc: '每个合数只被最小质因子筛掉一次。可顺手筛 phi / mu。',
    lastUsedAt: '2026-06-18',
    code: `#include <bits/stdc++.h>
using namespace std;
const int N = 1e7 + 10;

int prime[N], cnt;
bool vis[N];

void sieve(int n) {
    for (int i = 2; i <= n; i++) {
        if (!vis[i]) prime[++cnt] = i;
        for (int j = 1; j <= cnt && 1LL * i * prime[j] <= n; j++) {
            vis[i * prime[j]] = true;
            if (i % prime[j] == 0) break;
        }
    }
}`,
  },
  {
    id: 9,
    name: '0-1 背包',
    cat: 'dp',
    lang: 'cpp',
    file: 'knapsack01.cpp',
    cplx: 'O(n · V)',
    tags: ['背包'],
    src: '洛谷 P1048',
    updated: '2026-02-14',
    priority: 4,
    desc: '一维滚动数组时体积必须倒序枚举，完全背包则正序。',
    lastUsedAt: '2026-05-09',
    code: `#include <bits/stdc++.h>
using namespace std;
const int V = 1e4 + 10;

int f[V]; // f[j] = 体积 j 内的最大价值

// w: 体积, v: 价值, m: 背包容量
void knapsack01(int w, int v, int m) {
    for (int j = m; j >= w; j--)
        f[j] = max(f[j], f[j - w] + v);
}`,
  },
  {
    id: 10,
    name: '快读 / 快写',
    cat: 'misc',
    lang: 'cpp',
    file: 'fastio.cpp',
    cplx: '比 cin 快约 10 倍',
    tags: ['卡常'],
    src: '通用',
    updated: '2026-01-20',
    priority: 3,
    desc: '数据量 1e6 以上建议换掉 cin/cout，或至少 sync_with_stdio(false)。',
    lastUsedAt: '2026-07-27',
    code: `#include <bits/stdc++.h>
using namespace std;

inline int read() {
    int x = 0, f = 1;
    char c = getchar();
    while (c < '0' || c > '9') {
        if (c == '-') f = -1;
        c = getchar();
    }
    while (c >= '0' && c <= '9') {
        x = x * 10 + c - '0';
        c = getchar();
    }
    return x * f;
}

inline void write(int x) {
    if (x < 0) putchar('-'), x = -x;
    if (x > 9) write(x / 10);
    putchar(x % 10 + '0');
}`,
  },
  {
    id: 11,
    name: '字符串哈希（双模）',
    cat: 'string',
    lang: 'cpp',
    file: 'str_hash.cpp',
    cplx: '预处理 O(n)，查询 O(1)',
    tags: ['哈希', '回文'],
    src: '洛谷 P3370',
    updated: '2026-05-27',
    priority: 4,
    desc: '双模基本不会撞。base 取 131 或 13331，模数用两个大质数。',
    lastUsedAt: '2026-06-25',
    code: `#include <bits/stdc++.h>
using namespace std;
typedef long long ll;
const int N = 1e6 + 10;
const ll B = 131, M1 = 1e9 + 7, M2 = 998244353;

ll h1[N], h2[N], p1[N], p2[N];

void init(char *s, int n) {
    p1[0] = p2[0] = 1;
    for (int i = 1; i <= n; i++) {
        p1[i] = p1[i - 1] * B % M1;
        p2[i] = p2[i - 1] * B % M2;
        h1[i] = (h1[i - 1] * B + s[i]) % M1;
        h2[i] = (h2[i - 1] * B + s[i]) % M2;
    }
}

pair<ll, ll> get(int l, int r) {
    ll x = (h1[r] - h1[l - 1] * p1[r - l + 1] % M1 + M1) % M1;
    ll y = (h2[r] - h2[l - 1] * p2[r - l + 1] % M2 + M2) % M2;
    return {x, y};
}`,
  },
  {
    id: 12,
    name: '离散化',
    cat: 'misc',
    lang: 'cpp',
    file: 'discretize.cpp',
    cplx: 'O(n log n)',
    tags: ['预处理'],
    src: '通用',
    updated: '2026-03-30',
    priority: 3,
    desc: '排序 + 去重 + lower_bound，返回 1-indexed 排名方便套树状数组。',
    lastUsedAt: '2026-04-02',
    code: `#include <bits/stdc++.h>
using namespace std;

vector<int> vals; // 先 push 所有可能出现的值

void build() {
    sort(vals.begin(), vals.end());
    vals.erase(unique(vals.begin(), vals.end()), vals.end());
}

int get(int x) { // 返回 1-indexed
    return lower_bound(vals.begin(), vals.end(), x) - vals.begin() + 1;
}`,
  },
]

TEMPLATES[0].variants = [
  {
    id: 'segtree-std',
    name: '标准版',
    lang: 'cpp',
    file: 'segtree_lazy.cpp',
    code: TEMPLATES[0].code,
  },
  {
    id: 'segtree-debug',
    name: '调试版',
    lang: 'cpp',
    file: 'segtree_lazy_debug.cpp',
    code: TEMPLATES[0].code,
  },
]

TEMPLATES[2].variants = [
  {
    id: 'dsu-rank',
    name: '路径压缩版',
    lang: 'cpp',
    file: 'dsu.cpp',
    code: TEMPLATES[2].code,
  },
  {
    id: 'dsu-weight',
    name: '带权版',
    lang: 'cpp',
    file: 'dsu_weight.cpp',
    code: TEMPLATES[2].code,
  },
]

TEMPLATES[3].variants = [
  {
    id: 'dijkstra-vector',
    name: 'vector 邻接表',
    lang: 'cpp',
    file: 'dijkstra.cpp',
    code: TEMPLATES[3].code,
  },
  {
    id: 'dijkstra-chain',
    name: '链式前向星',
    lang: 'cpp',
    file: 'dijkstra_chain.cpp',
    code: TEMPLATES[3].code,
  },
]
