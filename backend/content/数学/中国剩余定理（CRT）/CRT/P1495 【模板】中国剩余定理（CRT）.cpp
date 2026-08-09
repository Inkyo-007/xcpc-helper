#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define llinf 0x3f3f3f3f3f3f3f3f
#define endl '\n'
#define ll long long
using namespace std;

constexpr int mod = 998244353, N = 2e5 + 5, M = 2e5 + 5;

using i128 = __int128;

void exgcd(i128 a, i128 b, i128 &x, i128 &y)
{
	if(b == 0) x = 1, y = 0;
	else exgcd(b, a % b, y, x), y -= a / b * x;
}

i128 CRT(vector <ll> a, vector <ll> r)
{
	int k = a.size() - 1;
	i128 n = 1;
	for(int i = 1; i <= k; i ++) n *= r[i];
	i128 ans = 0;
	for(int i = 1; i <= k; i ++){
		i128 m = n / r[i], b, y;
		exgcd(m, r[i], b, y);
		ans = (ans + a[i] * (m * b % n) % n) % n;
	}
	return (ans + n) % n;
}

void solve()
{
	int n; cin >> n;
	vector <ll> a(n + 1), b(n + 1);
	for(int i = 1; i <= n; i ++) cin >> a[i] >> b[i];
	cout << (ll)CRT(b, a) << endl;
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); //cout.tie(0);
	
	int t = 1;
	//cin >> t; 
	while(t --) solve();
	
	return 0;
}
