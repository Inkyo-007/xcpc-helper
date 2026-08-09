#include<bits/stdc++.h>
#define inf 0x3f3f3f3f
#define llinf 0x3f3f3f3f3f3f3f3f
#define endl '\n'
#define ll long long
using namespace std;

constexpr int mod = 998244353, N = 2e5 + 5, M = 2e5 + 5;

const double PI = acos(-1);
using cd = complex<double>;

void fft(vector <cd> &a, bool flag) //false : DFT; true : IDFT
{
	int n = a.size();
	assert((n & (n - 1)) == 0);
	vector <int> rev(n, 0);
	int k = __builtin_ctz(n);
	for(int i = 0; i < n; i ++){
		rev[i] = (rev[i >> 1] >> 1) | ((i & 1) << (k - 1));
	}
	for(int i = 0; i < n; i ++){
		if(i < rev[i]) swap(a[i], a[rev[i]]);
	}
	for(int l = 1; l < n; l <<= 1){
		cd wn(cos(2 * PI / (2 * l)), (flag ? -1 : 1) * sin(2 * PI / (2 * l)));
		for(int i = 0; i < n; i += l * 2){
			cd w(1, 0);
			for(int k = 0; k < l; k ++){
				cd u = a[i + k];
				cd v = w * a[i + k + l];
				a[i + k] = u + v;
				a[i + k + l] = u - v;
				w *= wn;
			}
		}
	}
	if(flag){
		for(int i = 0; i < n; i ++) a[i] /= n;
	}
}

void solve()
{
	int n, m; cin >> n >> m;
	int s = 1;
	while(s < n + m + 1) s <<= 1;
	vector <cd> a(s, 0), b(s, 0);
	for(int i = 0; i <= n; i ++) cin >> a[i];
	for(int i = 0; i <= m; i ++) cin >> b[i];
	fft(a, 0), fft(b, 0);
	for(int i = 0; i < s; i ++) a[i] *= b[i];
	fft(a, 1);
	for(int i = 0; i <= n + m; i ++){
		int x = a[i].real() + 0.5;
		cout << x << ' ';
	}
	cout << endl;
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
