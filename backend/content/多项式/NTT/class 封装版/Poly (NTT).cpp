struct Poly {
private:
	vector <ll> a;
	static constexpr int mod = 998244353, G = 3, invG = 332748118; //998244352 = 2^23 * 119
//	static constexpr int mod = 1004535809, G = 3, invG = 334845270; //1004535808 = 2^21 * 479
	void normalize() { //在题目保留后缀 0 项时不要使用该函数
		while (!a.empty() && a.back() == 0) a.pop_back();
	}
	
	static ll qpow(ll b, ll k){
		ll res = 1;
		while(k){
			if(k & 1) res = res * b % mod;
			b = b * b % mod;
			k >>= 1;
		}
		return res;
	}
	
	static void ntt(vector <ll> &a, bool flag) //false: DFT, true: IDFT
	{
		int n = a.size();
		assert((n & (n - 1)) == 0);
		assert(n <= (1 << 23));
		vector <int> rev(n, 0);
		int k = __builtin_ctz(n);
		for(int i = 0; i < n; i ++){
			rev[i] = (rev[i >> 1] >> 1) | ((i & 1) << (k - 1));
		}
		for(int i = 0; i < n; i ++){
			if(i < rev[i]) swap(a[i], a[rev[i]]);
		}
		for(int l = 1; l < n; l <<= 1){
			ll wn = qpow(flag ? invG : G, (mod - 1) / (l * 2));
			for(int i = 0; i < n; i += l * 2){
				ll w = 1;
				for(int k = 0; k < l; k ++){
					ll u = a[i + k];
					ll v = w * a[i + k + l] % mod;
					a[i + k] = (u + v) % mod;
					a[i + k + l] = (u - v + mod) % mod;
					w = w * wn % mod;
				}
			}
		}
		if(flag){
			ll invn = qpow(n, mod - 2);
			for(int i = 0; i < n; i ++) a[i] = a[i] * invn % mod;
		}
	}
	
public:
	Poly() {}
	Poly(int n) : a(n) {}
	
	template <typename T>
	Poly(const T& c) {
		a.reserve(c.size());
		for (auto&& x : c) {
			ll v = (ll)x % mod;
			if (v < 0) v += mod;
			a.push_back(v);
		}
		normalize();
	}
	
	int size() const { return a.size(); }
	ll get(int x) { return a[x]; }
	
	friend Poly operator + (const Poly& A, const Poly& B) {
		Poly C;
		int n = max(A.size(), B.size());
		C.a.resize(n);
		for (int i = 0; i < n; i++) {
			if (i < A.size()) C.a[i] = (C.a[i] + A.a[i]) % mod;
			if (i < B.size()) C.a[i] = (C.a[i] + B.a[i]) % mod;
		}
		C.normalize();
		return C;
	}
	
	friend Poly operator - (const Poly& A, const Poly& B) {
		Poly C;
		int n = max(A.size(), B.size());
		C.a.resize(n);
		for (int i = 0; i < n; i++) {
			if (i < A.size()) C.a[i] = (C.a[i] + A.a[i]) % mod;
			if (i < B.size()) C.a[i] = (C.a[i] - B.a[i] + mod) % mod;
		}
		C.normalize();
		return C;
	}
	
	friend Poly operator * (const Poly& A, const Poly& B) {
		if (A.a.empty() || B.a.empty()) return Poly();
		
		int n = A.size(), m = B.size();
		int s = 1;
		while (s < n + m - 1) s <<= 1;
		assert(s <= (1 << 23));
		
		vector <ll> fa(A.a.begin(), A.a.end());
		vector <ll> fb(B.a.begin(), B.a.end());
		fa.resize(s);
		fb.resize(s);
		
		ntt(fa, false); ntt(fb, false);
		for (int i = 0; i < s; i++) {
			fa[i] = fa[i] * fb[i] % mod;
		}
		ntt(fa, true);
		
		Poly C;
		C.a.assign(fa.begin(), fa.begin() + n + m - 1);
		C.normalize();
		return C;
	}
	
	Poly inv() {
		Poly B;
		assert(a[0]);
		B.a = {qpow(a[0], mod - 2)};
		int n = size(), m = 1;
		while(m < n) {
			m <<= 1;
			Poly A, tmp;
			A.a.assign(a.begin(), a.begin() + min(n, m));
			tmp = B * A;
			tmp.a.resize(m);
			for(int i = 0; i < m; i++) {
				tmp.a[i] = (mod - tmp.a[i]) % mod;
			}
			tmp.a[0] = (tmp.a[0] + 2) % mod;
			B = B * tmp;
			B.a.resize(m);
		}
		B.a.resize(n);
		return B;
	}
};