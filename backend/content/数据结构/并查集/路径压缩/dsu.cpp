#include <bits/stdc++.h>
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
}
