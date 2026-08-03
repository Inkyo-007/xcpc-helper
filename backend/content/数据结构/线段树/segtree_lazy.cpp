#include <bits/stdc++.h>
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
    if (qr > mid) update(p << 1, l, mid + 1, qr, v);
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
}
