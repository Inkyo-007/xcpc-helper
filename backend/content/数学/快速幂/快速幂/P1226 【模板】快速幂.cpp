#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define maxn 500050
#define maxm 500050 
#define endl '\n'
#define ll long long
using namespace std;

ll a, b, mod; 

ll qpow(ll x, ll n)
{
	ll res = 1;
	while(n)
	{
		if(n & 1) res = res * x % mod;
		x = x * x % mod;
		n >>= 1;
	}
	return res;
}

int main()
{
	ios::sync_with_stdio(false);
	cin.tie(0); cout.tie(0);
	
	cin >> a >> b >> mod;
	cout << a << '^' << b << " mod " << mod << '=' << qpow(a, b);
	
	return 0;
}
