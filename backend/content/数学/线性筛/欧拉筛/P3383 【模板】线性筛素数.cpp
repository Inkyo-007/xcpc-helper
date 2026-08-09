#include<bits/stdc++.h>
#define inf 0x3f3f3f3f

using namespace std;

constexpr int N = 1e8 + 5;

int pri[N], d[N];

void sieve(int n)
{
	d[1] = 1;
	int cnt = 0;
	for(int i = 2; i <= n; i ++){
		if(!d[i]) d[i] = i, pri[++ cnt] = i;
		for(int j = 1; j <= cnt && i * pri[j] <= n; j ++){
			d[i * pri[j]] = d[i]; //= d[i]: 最大质因子, = pri[j]: 最小质因子
			if(i % pri[j] == 0) break;
		}
	}
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); cout.tie(0);
	int n, q; 
	cin >> n >> q;
	sieve(n);
	while(q --)
	{
		int k; cin >> k;
		cout << pri[k] << '\n';
	}
	return 0;
}
