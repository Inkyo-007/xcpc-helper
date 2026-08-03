#include <bits/stdc++.h>
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
            printf("%d\n", i - m + 1); // 匹配起点（1-indexed）
            j = nxt[j];
        }
    }
}
