#include <bits/stdc++.h>
using namespace std;
const int N = 1e5 + 10;

int fa[N];
long long d[N]; // d[x]: x 到父节点的权值

void init(int n) {
    for (int i = 1; i <= n; i++) fa[i] = i, d[i] = 0;
}

int find(int x) {
    if (fa[x] == x) return x;
    int root = find(fa[x]);
    d[x] += d[fa[x]];
    return fa[x] = root;
}

// 将 y 接到 x 下，权值关系 w = d[y] - d[x]
void merge(int x, int y, long long w) {
    int rx = find(x), ry = find(y);
    if (rx == ry) return;
    fa[ry] = rx;
    d[ry] = d[x] + w - d[y];
}

// 查询 d[y] - d[x]，不连通返回 LLONG_MIN
long long query(int x, int y) {
    if (find(x) != find(y)) return LLONG_MIN;
    return d[y] - d[x];
}
