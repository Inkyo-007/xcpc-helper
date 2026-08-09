class Hash
{
private:
	using ull = unsigned long long;
	int n;
	ull base = 167, hmod = 998244353;
	vector <ull> hs, rhs, p;
public:
	Hash() {}
	Hash(string s){
		init(s);
	};
	Hash(string s, ull a, ull b){
		base = a, hmod = b;
		init(s);
	}
	void init(string s){
		n = s.size();
		s = " " + s;
		hs.resize(n + 1), rhs.resize(n + 1), p.resize(n + 1);
		p[0] = 1;
		for(int i = 1; i <= n; i ++) hs[i] = (hs[i - 1] * base + s[i]) % hmod;
		for(int i = 1, j = n; i <= n; i ++, j --) rhs[i] = (rhs[i - 1] * base + s[j]) % hmod;
		for(int i = 1; i <= n; i ++) p[i] = p[i - 1] * base % hmod;	
	}
	ull hs_get(int l, int r){
		return (hs[r] + hmod - hs[l - 1] * p[r - l + 1] % hmod) % hmod;
	}
	ull rhs_get(int l, int r){
		int tl = n - r + 1, tr = n - l + 1;
		return (rhs[tr] + hmod - rhs[tl - 1] * p[tr - tl + 1] % hmod) % hmod;
	}
	bool ispal(int l, int r){
		return hs_get(l, r) == rhs_get(l, r);
	}
};
