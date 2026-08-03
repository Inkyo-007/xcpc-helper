#include <bits/stdc++.h>
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
}
